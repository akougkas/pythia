"""Learner — RL-based adaptive confidence and dispatch optimization (§4).

Implements a contextual bandit formulation that learns from reconciliation
outcomes to improve speculation accuracy over time.

Key components:
- DispatchFingerprint: sliding window of recent dispatch events (§4.1)
- BayesianConfidence: Beta-distribution confidence replacing raw hit rate (§4.1)
- DriftDetector: EMA-based non-stationarity detection with mode regression (§4.3)
- Learner: orchestrates learning, provides confidence_fn to SpeculativeDispatcher

Traceability:
- §4.1: RL formulation (state, action, reward)
- §4.2: Progressive activation (cold start → early learning → mature)
- §4.3: Convergence and adaptation
- §5.1: Learner component in architecture
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from pythia.contracts import (
    DispatchPlan,
    Intent,
    ReconciliationOutcome,
)


# --- Dispatch Fingerprint (§4.1) ---


@dataclass(frozen=True)
class DispatchEvent:
    """Single dispatch event in the fingerprint history.

    Each event is an (intent_key, solver_plan_signature, verdict) triple.
    """

    intent_key: str
    plan_signature: str  # e.g., "planner→code_gen→tester→review@gpu-1,cpu-1"
    verdict: str  # COMMIT | PARTIAL | FLUSH
    reward: float
    confidence_at_dispatch: float
    mode_at_dispatch: int


def _plan_signature(plan: DispatchPlan) -> str:
    """Compact signature of a dispatch plan for fingerprinting."""
    if not plan.assignments:
        return "empty"
    agents = "→".join(a.agent_type for a in plan.assignments)
    members = ",".join(a.fleet_member_id for a in plan.assignments)
    return f"{agents}@{members}"


class DispatchFingerprint:
    """Sliding window of recent dispatch events (§4.1).

    Captures recurring user patterns via a fixed-size deque.
    Provides summary statistics for the Learner's state vector.

    The window size k determines how quickly the fingerprint
    adapts to workload changes (§4.3).
    """

    def __init__(self, window_size: int = 50) -> None:
        self._window: deque[DispatchEvent] = deque(maxlen=window_size)
        self._window_size = window_size

    def record(self, event: DispatchEvent) -> None:
        """Add a dispatch event to the fingerprint."""
        self._window.append(event)

    @property
    def size(self) -> int:
        return len(self._window)

    @property
    def is_cold(self) -> bool:
        """True during cold start phase (< 5 events)."""
        return len(self._window) < 5

    def recent_hit_rate(self, intent_key: str | None = None) -> float:
        """Hit rate over the window, optionally filtered by intent key.

        Returns 0.0 if no matching events in the window.
        """
        if not self._window:
            return 0.0

        if intent_key is not None:
            events = [e for e in self._window if e.intent_key == intent_key]
        else:
            events = list(self._window)

        if not events:
            return 0.0

        hits = sum(1 for e in events if e.verdict in ("COMMIT", "PARTIAL"))
        return hits / len(events)

    def recent_reward_mean(self, intent_key: str | None = None) -> float:
        """Mean reward over the window, optionally filtered."""
        if not self._window:
            return 0.0

        if intent_key is not None:
            events = [e for e in self._window if e.intent_key == intent_key]
        else:
            events = list(self._window)

        if not events:
            return 0.0
        return sum(e.reward for e in events) / len(events)

    def intent_frequency(self) -> dict[str, int]:
        """Count of each intent key in the current window."""
        freq: dict[str, int] = {}
        for e in self._window:
            freq[e.intent_key] = freq.get(e.intent_key, 0) + 1
        return freq

    def mode_distribution(self) -> dict[int, int]:
        """Distribution of modes used in the window."""
        dist: dict[int, int] = {}
        for e in self._window:
            dist[e.mode_at_dispatch] = dist.get(e.mode_at_dispatch, 0) + 1
        return dist

    def summary_vector(self) -> dict[str, float]:
        """Fixed-dimensional summary for state representation.

        Returns a dict of features usable as state vector components.
        """
        n = len(self._window)
        if n == 0:
            return {
                "fill_ratio": 0.0,
                "overall_hit_rate": 0.0,
                "mean_reward": 0.0,
                "mean_confidence": 0.0,
                "unique_intents": 0.0,
                "mode3_fraction": 0.0,
            }

        hits = sum(1 for e in self._window if e.verdict in ("COMMIT", "PARTIAL"))
        modes = self.mode_distribution()
        unique = len(set(e.intent_key for e in self._window))

        return {
            "fill_ratio": n / self._window_size,
            "overall_hit_rate": hits / n,
            "mean_reward": sum(e.reward for e in self._window) / n,
            "mean_confidence": sum(e.confidence_at_dispatch for e in self._window) / n,
            "unique_intents": unique / max(n, 1),
            "mode3_fraction": modes.get(3, 0) / n,
        }


# --- Bayesian Confidence (§4.1) ---


class BayesianConfidence:
    """Beta-distribution confidence tracker per intent key.

    Instead of raw hit rate (hits/total), uses a Beta(α, β) posterior
    to produce calibrated confidence with uncertainty awareness.

    - Prior: Beta(1, 1) = uniform (no prior knowledge)
    - Update: α += 1 on hit, β += 1 on miss
    - Confidence = E[Beta(α, β)] = α / (α + β) (posterior mean)

    For small sample sizes, the posterior mean is pulled toward 0.5
    (uncertainty), which naturally implements conservative cold-start
    behavior described in §4.2.

    The Learner can inject task-specific priors via set_prior().
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._alpha: dict[str, float] = {}
        self._beta: dict[str, float] = {}
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta

    def record_outcome(self, key: str, hit: bool) -> None:
        """Update Beta posterior for this key."""
        if key not in self._alpha:
            self._alpha[key] = self._prior_alpha
            self._beta[key] = self._prior_beta

        if hit:
            self._alpha[key] += 1.0
        else:
            self._beta[key] += 1.0

    def confidence(self, key: str) -> float:
        """Posterior mean: E[Beta(α, β)] = α / (α + β)."""
        alpha = self._alpha.get(key, self._prior_alpha)
        beta = self._beta.get(key, self._prior_beta)
        return alpha / (alpha + beta)

    def confidence_interval(self, key: str, width: float = 0.9) -> tuple[float, float]:
        """Approximate credible interval using normal approximation.

        Returns (lower, upper) bounds for the given credible width.
        """
        alpha = self._alpha.get(key, self._prior_alpha)
        beta = self._beta.get(key, self._prior_beta)
        mean = alpha / (alpha + beta)
        # Variance of Beta distribution
        var = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
        std = math.sqrt(var)
        # Z-score for the given width (e.g., 1.645 for 90%)
        z = 1.645 if width == 0.9 else 1.96
        lower = max(0.0, mean - z * std)
        upper = min(1.0, mean + z * std)
        return lower, upper

    def total_observations(self, key: str) -> int:
        """Total observations for this key (α + β - prior)."""
        alpha = self._alpha.get(key, self._prior_alpha)
        beta = self._beta.get(key, self._prior_beta)
        return int(alpha + beta - self._prior_alpha - self._prior_beta)

    def set_prior(self, key: str, alpha: float, beta: float) -> None:
        """Set task-specific prior (§4.2 Bayesian initialization)."""
        self._alpha[key] = alpha
        self._beta[key] = beta

    def all_keys(self) -> list[str]:
        """Return all tracked intent keys."""
        return list(self._alpha.keys())


# --- Drift Detector (§4.3) ---


class DriftDetector:
    """EMA-based accuracy drift detection with mode regression (§4.3).

    Monitors accuracy via exponentially weighted moving average.
    When accuracy drops below threshold, triggers mode regression
    (Mode 3 → 2 → 1) and increases learning rate.

    This handles non-stationarity: when user patterns change,
    the system quickly falls back to safer modes and re-learns.
    """

    def __init__(
        self,
        smoothing_factor: float = 0.1,
        regression_threshold: float = 0.3,
    ) -> None:
        self._alpha = smoothing_factor
        self._threshold = regression_threshold
        self._ema: dict[str, float] = {}
        self._drift_flags: dict[str, bool] = {}

    def update(self, key: str, hit: bool) -> bool:
        """Update EMA and check for drift.

        Returns True if drift detected (mode regression needed).
        """
        value = 1.0 if hit else 0.0

        if key not in self._ema:
            self._ema[key] = value
        else:
            self._ema[key] = self._alpha * value + (1 - self._alpha) * self._ema[key]

        # Check for sustained accuracy drop
        is_drifting = self._ema[key] < self._threshold
        was_drifting = self._drift_flags.get(key, False)
        self._drift_flags[key] = is_drifting

        # Return True only on NEW drift detection (transition from OK to drifting)
        return is_drifting and not was_drifting

    def is_drifting(self, key: str) -> bool:
        """Check if a key is currently flagged as drifting."""
        return self._drift_flags.get(key, False)

    def current_ema(self, key: str) -> float:
        """Current EMA value for a key."""
        return self._ema.get(key, 0.5)

    def reset(self, key: str) -> None:
        """Reset drift state for a key (after recovery)."""
        self._drift_flags[key] = False


# --- Intent Key Extraction ---


def _intent_key(intent: Intent) -> str:
    """Extract cache key matching speculator._intent_key()."""
    if intent.complexity < 0.3:
        complexity_bucket = "low"
    elif intent.complexity < 0.6:
        complexity_bucket = "med"
    else:
        complexity_bucket = "high"
    primary_tag = sorted(intent.domain_tags)[0] if intent.domain_tags else "general"
    return f"{intent.task_type}:{complexity_bucket}:{primary_tag}"


# --- Learner (§4) ---


@dataclass
class LearnerStats:
    """Observable statistics from the Learner for monitoring."""

    total_interactions: int = 0
    phase: str = "cold_start"  # cold_start | early_learning | mature
    active_drift_keys: list[str] = field(default_factory=list)
    mode_regressions: int = 0
    unique_intent_keys: int = 0
    mean_confidence: float = 0.0


class Learner:
    """Adaptive learning module for speculation optimization (§4).

    Contextual bandit formulation:
    - State: (intent features, fleet state, dispatch fingerprint)
    - Action: speculation mode + draft plan selection
    - Reward: reconciliation outcome (COMMIT=+1, FLUSH=-0.5, PARTIAL=scaled)

    Provides confidence_fn to SpeculativeDispatcher, replacing the
    simple hit-rate tracker with Bayesian confidence + drift awareness.

    Progressive activation phases (§4.2):
    - Cold start (< N1 interactions): Mode 1 only, pure observation
    - Early learning (N1-N2): Mode 2 for high-frequency intents
    - Mature (> N2): Mode 3 for top-k confident intent classes

    Args:
        window_size: Dispatch fingerprint window size k (§4.1)
        n1: Cold start → early learning transition (§4.2)
        n2: Early learning → mature transition (§4.2)
        prior_alpha: Beta prior α (higher = more optimistic start)
        prior_beta: Beta prior β
        drift_smoothing: EMA smoothing factor for drift detection
        drift_threshold: Accuracy below which drift is flagged
    """

    def __init__(
        self,
        window_size: int = 50,
        n1: int = 10,
        n2: int = 50,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        drift_smoothing: float = 0.1,
        drift_threshold: float = 0.3,
    ) -> None:
        self._fingerprint = DispatchFingerprint(window_size=window_size)
        self._confidence = BayesianConfidence(
            prior_alpha=prior_alpha, prior_beta=prior_beta
        )
        self._drift = DriftDetector(
            smoothing_factor=drift_smoothing,
            regression_threshold=drift_threshold,
        )
        self._n1 = n1
        self._n2 = n2
        self._total_interactions = 0
        self._mode_regressions = 0

        # Per-key mode overrides when drift is detected
        self._mode_caps: dict[str, int] = {}

    @property
    def fingerprint(self) -> DispatchFingerprint:
        return self._fingerprint

    @property
    def bayesian_confidence(self) -> BayesianConfidence:
        return self._confidence

    @property
    def drift_detector(self) -> DriftDetector:
        return self._drift

    def confidence_fn(self, intent: Intent) -> float:
        """Confidence function to inject into SpeculativeDispatcher.

        This replaces the simple hit-rate tracker with:
        1. Bayesian posterior mean (calibrated uncertainty)
        2. Phase-aware damping (conservative during cold start)
        3. Drift-aware regression (cap confidence when drifting)

        Returns float in [0, 1].
        """
        key = _intent_key(intent)
        base_confidence = self._confidence.confidence(key)

        # Phase damping (§4.2)
        if self._total_interactions < self._n1:
            # Cold start: cap at 0.3 (Mode 1 only)
            return min(base_confidence, 0.3)
        elif self._total_interactions < self._n2:
            # Early learning: allow Mode 2 but cap before Mode 3
            # Scale confidence by observation count for this key
            obs = self._confidence.total_observations(key)
            if obs < 3:
                return min(base_confidence, 0.3)
            return min(base_confidence, 0.75)

        # Mature: full Bayesian confidence, but check drift
        if self._drift.is_drifting(key):
            # Mode regression: cap confidence to force fallback
            cap = self._mode_caps.get(key, 1)
            if cap <= 1:
                return min(base_confidence, 0.3)  # Force Mode 1
            elif cap <= 2:
                return min(base_confidence, 0.6)  # Force Mode 2
            return base_confidence

        return base_confidence

    def record_outcome(
        self,
        intent: Intent,
        solver_plan: DispatchPlan,
        outcome: ReconciliationOutcome,
    ) -> None:
        """Record a dispatch outcome for learning (§4.1).

        Called after each reconciliation. Updates:
        1. Bayesian confidence (Beta posterior)
        2. Dispatch fingerprint (sliding window)
        3. Drift detector (EMA accuracy)
        4. Phase transitions
        """
        self._total_interactions += 1
        key = _intent_key(intent)
        hit = outcome.verdict in ("COMMIT", "PARTIAL")

        # 1. Update Bayesian confidence
        self._confidence.record_outcome(key, hit)

        # 2. Update dispatch fingerprint
        event = DispatchEvent(
            intent_key=key,
            plan_signature=_plan_signature(solver_plan),
            verdict=outcome.verdict,
            reward=outcome.reward,
            confidence_at_dispatch=outcome.confidence,
            mode_at_dispatch=outcome.speculation_mode,
        )
        self._fingerprint.record(event)

        # 3. Drift detection
        drift_detected = self._drift.update(key, hit)
        if drift_detected:
            self._mode_regressions += 1
            # Regress mode: cap this key at Mode 1 initially
            self._mode_caps[key] = 1

        # 4. Drift recovery: if key was drifting but EMA recovered
        if key in self._mode_caps and not self._drift.is_drifting(key):
            # Gradually restore: 1 → 2 → 3
            current_cap = self._mode_caps[key]
            if current_cap < 3:
                self._mode_caps[key] = current_cap + 1
            else:
                del self._mode_caps[key]

    def get_stats(self) -> LearnerStats:
        """Return observable statistics for monitoring."""
        # Determine phase
        if self._total_interactions < self._n1:
            phase = "cold_start"
        elif self._total_interactions < self._n2:
            phase = "early_learning"
        else:
            phase = "mature"

        # Active drift keys
        active_drifts = [
            key for key in self._confidence.all_keys()
            if self._drift.is_drifting(key)
        ]

        # Mean confidence across all keys
        keys = self._confidence.all_keys()
        mean_conf = (
            sum(self._confidence.confidence(k) for k in keys) / len(keys)
            if keys else 0.0
        )

        return LearnerStats(
            total_interactions=self._total_interactions,
            phase=phase,
            active_drift_keys=active_drifts,
            mode_regressions=self._mode_regressions,
            unique_intent_keys=len(keys),
            mean_confidence=mean_conf,
        )

    def get_convergence_metrics(self) -> dict[str, object]:
        """Return convergence-related metrics for §4.3 evaluation.

        Includes per-key confidence, observation counts, and
        speculation regret approximation.
        """
        keys = self._confidence.all_keys()
        metrics: dict[str, object] = {
            "total_interactions": self._total_interactions,
            "phase": self.get_stats().phase,
            "n_unique_keys": len(keys),
            "per_key": {},
        }

        total_regret = 0.0
        for key in keys:
            obs = self._confidence.total_observations(key)
            conf = self._confidence.confidence(key)
            lower, upper = self._confidence.confidence_interval(key)
            ema = self._drift.current_ema(key)

            # Approximate regret: (1 - confidence) * observations
            # This measures how far from oracle (confidence=1.0) we are
            key_regret = (1.0 - conf) * obs
            total_regret += key_regret

            metrics["per_key"][key] = {  # type: ignore[index]
                "observations": obs,
                "confidence": conf,
                "ci_90": (lower, upper),
                "ema_accuracy": ema,
                "drifting": self._drift.is_drifting(key),
                "regret": key_regret,
            }

        metrics["total_regret"] = total_regret
        metrics["mean_regret_per_interaction"] = (
            total_regret / self._total_interactions
            if self._total_interactions > 0 else 0.0
        )

        return metrics
