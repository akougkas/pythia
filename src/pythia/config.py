"""Configuration loading — §5.2.

YAML-based fleet configuration following IOWarp declarative model.

Traceability:
- Fleet configuration: §5.2 (provider constraints as capability vectors)
- DispatchSolver creation from config: §5.1
"""

from __future__ import annotations

from pathlib import Path

import yaml

from pythia.contracts import FleetMember
from pythia.fleet import Fleet
from pythia.solver import AgentSelector, DispatchSolver


def load_fleet_config(config_path: str | Path) -> Fleet:
    """Load fleet from YAML configuration file (§5.2).

    Expected YAML format:
        fleet:
          - member_id: gpu-1
            compute: 100.0
            memory: 64.0
            rate_limit: 5
            token_budget: 50000
            cost_rate: 0.05
            latency: 0.1
            capabilities: [code_gen, analysis]
            affinity_tags: [gpu, local]
    """
    path = Path(config_path)
    with path.open() as f:
        data = yaml.safe_load(f)

    members = []
    for entry in data["fleet"]:
        members.append(
            FleetMember(
                member_id=entry["member_id"],
                compute=float(entry["compute"]),
                memory=float(entry["memory"]),
                rate_limit=int(entry["rate_limit"]),
                token_budget=int(entry["token_budget"]),
                cost_rate=float(entry["cost_rate"]),
                latency=float(entry["latency"]),
                capabilities=entry.get("capabilities", []),
                affinity_tags=entry.get("affinity_tags", []),
            )
        )

    return Fleet(members)


def create_solver_from_config(
    config_path: str | Path, alpha: float = 0.5
) -> DispatchSolver:
    """Create a fully configured DispatchSolver from YAML config."""
    fleet = load_fleet_config(config_path)
    return DispatchSolver(fleet, AgentSelector(), alpha=alpha)
