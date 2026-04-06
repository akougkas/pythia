"""Real Agent Runner — executes agent pipelines via Ollama and Claude LLMs.

Each agent role (planner, code_gen, tester, reviewer) gets a role-specific
system prompt and runs against a real LLM. Supports:
- Ollama (local models: qwen2.5:14b, llama3.1:8b, etc.)
- Claude (via Agent SDK, uses current Claude Code session — no API key)

Traceability: §5.1 (agent execution), §6.2 (end-to-end latency)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests as http_requests


# --- Ollama Client ---


class OllamaClient:
    """Minimal Ollama HTTP client for agent execution."""

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:14b"
    ) -> None:
        self._base_url = base_url
        self._model = model
        self.provider = "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> tuple[str, float, dict]:
        """Call Ollama generate API.

        Returns:
            (response_text, elapsed_seconds, usage_info)
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            payload["system"] = system

        t0 = time.perf_counter()
        resp = http_requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=300,
        )
        elapsed = time.perf_counter() - t0
        resp.raise_for_status()

        data = resp.json()
        text = data.get("response", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_duration_ns": data.get("total_duration", 0),
            "eval_duration_ns": data.get("eval_duration", 0),
        }
        return text, elapsed, usage


# --- Claude Client (via Agent SDK) ---


class ClaudeClient:
    """Claude model client via Agent SDK — uses current Claude Code session.

    No API key needed. Leverages the authenticated Claude Code CLI session.
    Supports all Claude tiers: haiku (fast/cheap), sonnet (balanced), opus (best).
    """

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self._model = model
        self.provider = "claude"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> tuple[str, float, dict]:
        """Call Claude via Agent SDK.

        Returns:
            (response_text, elapsed_seconds, usage_info)
        """
        import anyio

        try:
            # Try from_thread first (if already in async context)
            return anyio.from_thread.run(
                self._async_generate, prompt, system, max_tokens
            )
        except RuntimeError:
            # Not in async context, run directly
            return anyio.run(self._async_generate, prompt, system, max_tokens)

    async def _async_generate(
        self, prompt: str, system: str, max_tokens: int
    ) -> tuple[str, float, dict]:
        from claude_agent_sdk import query, AssistantMessage, TextBlock, ClaudeAgentOptions

        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\nUser: {prompt}"

        t0 = time.perf_counter()
        response_text = ""
        async for message in query(
            prompt=full_prompt,
            options=ClaudeAgentOptions(model=self._model),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        elapsed = time.perf_counter() - t0
        usage = {
            "prompt_tokens": 0,  # SDK doesn't expose token counts
            "completion_tokens": len(response_text.split()),  # approximate
            "total_duration_ns": int(elapsed * 1e9),
            "eval_duration_ns": int(elapsed * 1e9),
        }
        return response_text, elapsed, usage


# --- Agent Role Prompts ---

AGENT_PROMPTS: dict[str, str] = {
    # --- HPC-CG agents ---
    "planner": (
        "You are an HPC task planner. Given a code generation request, "
        "produce a brief execution plan:\n"
        "1. Identify the algorithm and parallelism strategy\n"
        "2. List key implementation steps (3-5 bullet points)\n"
        "3. Note potential pitfalls or edge cases\n"
        "Keep your response under 200 words. Be specific and technical."
    ),
    "code_gen": (
        "You are an expert HPC code generator. Given a task description "
        "(and optionally a planner's analysis), write correct, efficient "
        "parallel code.\n"
        "- Use the specified parallelism model (MPI, OpenMP, or MPI+OpenMP)\n"
        "- Include proper initialization, computation, and cleanup\n"
        "- Handle edge cases (empty input, single element, etc.)\n"
        "- Add brief inline comments explaining key parallel sections\n"
        "Output ONLY the code inside a code block. No explanations outside the code."
    ),
    "tester": (
        "You are an HPC code tester. Given generated code, write test cases:\n"
        "1. A basic correctness test with known input/output\n"
        "2. An edge case test (empty input, single element)\n"
        "3. A parallel correctness check (results match serial version)\n"
        "Output test code in a code block. Use simple assertions, not a test framework."
    ),
    "reviewer": (
        "You are an HPC code reviewer. Do NOT rewrite or regenerate the code. "
        "ONLY review the provided code and respond in EXACTLY this format:\n\n"
        "CORRECTNESS: <one sentence about bugs or logic errors>\n"
        "PARALLELISM: <one sentence about parallel strategy>\n"
        "EDGE_CASES: <one sentence about edge case handling>\n"
        "SCORE: <number 1-5>/5\n\n"
        "1=broken, 2=major issues, 3=works but inefficient, 4=good, 5=production-ready.\n"
        "Do NOT write any code. ONLY review."
    ),
    # --- SDP agents (Scientific Data Pipelines) ---
    "data_discovery": (
        "You are a data discovery agent for scientific data pipelines. "
        "Given a data analysis task, identify:\n"
        "1. What data sources are needed and their likely formats\n"
        "2. How to load/access each data source\n"
        "3. Any data quality issues to watch for\n"
        "Keep response under 200 words. Be specific about file formats and tools."
    ),
    "data_wrangler": (
        "You are a data wrangling agent. Given a data analysis task and "
        "discovered data sources, write Python code to:\n"
        "1. Load the data (pandas, geopandas, xarray as appropriate)\n"
        "2. Clean and transform (handle missing values, type conversions)\n"
        "3. Join/merge multiple sources if needed\n"
        "Output ONLY the code inside a code block."
    ),
    "analyst": (
        "You are a scientific data analyst. Given cleaned data and an analysis "
        "question, write Python code to:\n"
        "1. Perform the required computation or statistical analysis\n"
        "2. Produce the answer in the expected format\n"
        "Output ONLY the code inside a code block."
    ),
    "reporter": (
        "You are a results reporter. Given analysis results, provide:\n"
        "ANSWER: <the final answer to the question>\n"
        "METHOD: <one sentence describing the approach>\n"
        "CONFIDENCE: <high/medium/low>\n"
        "Do NOT write code. ONLY report results."
    ),
    # --- RWA agents (Research Workflow Automation) ---
    "literature_reviewer": (
        "You are a research literature reviewer. Given a paper replication task:\n"
        "1. Identify the key contributions and methods of the paper\n"
        "2. List the critical components that must be replicated\n"
        "3. Note any dependencies (datasets, pretrained models, libraries)\n"
        "Keep response under 250 words."
    ),
    "experiment_designer": (
        "You are an experiment designer. Given a paper's methodology, design "
        "the replication experiment:\n"
        "1. List hyperparameters and configurations\n"
        "2. Define evaluation metrics and baselines\n"
        "3. Specify compute requirements\n"
        "Keep response under 200 words."
    ),
    "code_generator": (
        "You are a research code generator. Given an experiment design, write "
        "the implementation code:\n"
        "- Model architecture or algorithm implementation\n"
        "- Training/evaluation loop\n"
        "- Proper logging and checkpointing\n"
        "Output ONLY the code inside a code block."
    ),
    "experiment_runner": (
        "You are an experiment runner. Given implementation code, produce:\n"
        "1. A run script or command to execute the experiment\n"
        "2. Expected runtime and resource requirements\n"
        "3. How to verify the run completed successfully\n"
        "Keep response under 150 words."
    ),
    "result_analyzer": (
        "You are a results analyzer. Given experiment outputs, provide:\n"
        "RESULT: <key metric values>\n"
        "COMPARISON: <how results compare to the original paper>\n"
        "ISSUES: <any discrepancies or problems>\n"
        "SCORE: <number 1-5>/5 for replication quality\n"
        "Do NOT write code. ONLY analyze results."
    ),
}


# --- Agent Execution Results ---


@dataclass
class AgentOutput:
    """Output from a single agent execution."""

    agent_type: str
    output_text: str
    elapsed_seconds: float
    prompt_tokens: int
    completion_tokens: int
    success: bool
    error: str = ""


@dataclass
class PipelineOutput:
    """Output from a full agent pipeline execution."""

    agent_outputs: list[AgentOutput] = field(default_factory=list)
    total_elapsed_seconds: float = 0.0
    total_tokens: int = 0
    final_code: str = ""
    review_score: int = 0

    @property
    def succeeded(self) -> bool:
        return all(a.success for a in self.agent_outputs)


# --- Pipeline Executor ---


class AgentPipelineRunner:
    """Executes agent pipelines via Ollama, following the DAG from Solver.

    Each agent in the pipeline receives context from previous agents,
    simulating real multi-agent coordination.

    Supports per-role model override: heavy agents (code_gen) can use a
    larger model while lighter agents (planner, reviewer) use a faster one.
    """

    def __init__(
        self,
        client: OllamaClient | None = None,
        role_clients: dict[str, OllamaClient] | None = None,
        temperature: float = 0.3,
    ) -> None:
        self._client = client or OllamaClient()
        self._role_clients = role_clients or {}
        self._temperature = temperature

    def execute_pipeline(
        self,
        request_text: str,
        agent_types: list[str],
        execution_order: list[list[str]],
    ) -> PipelineOutput:
        """Execute a full agent pipeline for a request.

        Args:
            request_text: The original NL request
            agent_types: List of agent types to execute
            execution_order: DAG stages from solver

        Returns:
            PipelineOutput with all agent results
        """
        result = PipelineOutput()
        context: dict[str, str] = {"request": request_text}
        t0 = time.perf_counter()

        # Flatten DAG stages into ordered list (sequential for now)
        ordered_agents = []
        for stage in execution_order:
            for agent_type in stage:
                if agent_type in agent_types:
                    ordered_agents.append(agent_type)

        for agent_type in ordered_agents:
            agent_output = self._execute_agent(agent_type, context)
            result.agent_outputs.append(agent_output)

            # Pass output to next agent as context
            context[agent_type] = agent_output.output_text
            result.total_tokens += (
                agent_output.prompt_tokens + agent_output.completion_tokens
            )

            # Extract code from code_gen/code_generator output
            if agent_type in ("code_gen", "code_generator"):
                result.final_code = self._extract_code(agent_output.output_text)

            # Extract review score from reviewer/result_analyzer/reporter
            if agent_type in ("reviewer", "result_analyzer", "reporter"):
                result.review_score = self._extract_score(agent_output.output_text)

        result.total_elapsed_seconds = time.perf_counter() - t0
        return result

    def execute_single_agent(
        self, agent_type: str, request_text: str, context: dict[str, str] | None = None
    ) -> AgentOutput:
        """Execute a single agent (for Mode 3 draft execution)."""
        ctx = {"request": request_text}
        if context:
            ctx.update(context)
        return self._execute_agent(agent_type, ctx)

    def _execute_agent(
        self, agent_type: str, context: dict[str, str]
    ) -> AgentOutput:
        """Execute one agent with its role prompt and accumulated context."""
        system_prompt = AGENT_PROMPTS.get(agent_type, "You are a helpful assistant.")

        # Build user prompt from context
        user_prompt = self._build_prompt(agent_type, context)

        # Use role-specific client if available
        client = self._role_clients.get(agent_type, self._client)

        try:
            text, elapsed, usage = client.generate(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2048 if agent_type == "code_gen" else 512 if agent_type == "reviewer" else 1024,
                temperature=self._temperature,
            )
            return AgentOutput(
                agent_type=agent_type,
                output_text=text,
                elapsed_seconds=elapsed,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                success=True,
            )
        except Exception as e:
            return AgentOutput(
                agent_type=agent_type,
                output_text="",
                elapsed_seconds=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                success=False,
                error=str(e),
            )

    def _build_prompt(self, agent_type: str, context: dict[str, str]) -> str:
        """Build agent-specific prompt from accumulated context."""
        request = context.get("request", "")

        if agent_type == "planner":
            return f"Task request:\n{request}"

        elif agent_type == "code_gen":
            planner_output = context.get("planner", "")
            if planner_output:
                return (
                    f"Task request:\n{request}\n\n"
                    f"Planner's analysis:\n{planner_output}"
                )
            return f"Task request:\n{request}"

        elif agent_type == "tester":
            code = context.get("code_gen", "")
            return (
                f"Task request:\n{request}\n\n"
                f"Generated code:\n{code}"
            )

        elif agent_type == "reviewer":
            code = context.get("code_gen", "")[:2000]  # truncate to avoid overflow
            tests = context.get("tester", "")[:500]
            prompt = f"Task request:\n{request}\n\nGenerated code:\n{code}"
            if tests:
                prompt += f"\n\nTest cases (summary):\n{tests}"
            return prompt

        # --- RWA agents (research workflow) ---
        elif agent_type == "literature_reviewer":
            return f"Research replication task:\n{request}"

        elif agent_type == "experiment_designer":
            lit_review = context.get("literature_reviewer", "")
            if lit_review:
                return (
                    f"Research task:\n{request}\n\n"
                    f"Literature review:\n{lit_review}"
                )
            return f"Research task:\n{request}"

        elif agent_type == "code_generator":
            design = context.get("experiment_designer", "")
            lit_review = context.get("literature_reviewer", "")
            prompt = f"Research task:\n{request}"
            if lit_review:
                prompt += f"\n\nLiterature review:\n{lit_review[:500]}"
            if design:
                prompt += f"\n\nExperiment design:\n{design}"
            return prompt

        elif agent_type == "experiment_runner":
            code = context.get("code_generator", "")
            design = context.get("experiment_designer", "")
            prompt = f"Research task:\n{request}"
            if design:
                prompt += f"\n\nExperiment design:\n{design[:500]}"
            if code:
                prompt += f"\n\nImplementation code:\n{code}"
            return prompt

        elif agent_type == "result_analyzer":
            runner_output = context.get("experiment_runner", "")[:1000]
            code = context.get("code_generator", "")[:500]
            prompt = f"Research task:\n{request}"
            if code:
                prompt += f"\n\nImplementation (summary):\n{code}"
            if runner_output:
                prompt += f"\n\nExperiment output:\n{runner_output}"
            return prompt

        # --- SDP agents (data pipelines) ---
        elif agent_type == "data_discovery":
            return f"Data pipeline task:\n{request}"

        elif agent_type == "data_wrangler":
            discovery = context.get("data_discovery", "")
            if discovery:
                return (
                    f"Data pipeline task:\n{request}\n\n"
                    f"Data sources discovered:\n{discovery}"
                )
            return f"Data pipeline task:\n{request}"

        elif agent_type == "analyst":
            wrangled = context.get("data_wrangler", "")
            discovery = context.get("data_discovery", "")
            prompt = f"Data analysis task:\n{request}"
            if discovery:
                prompt += f"\n\nData sources:\n{discovery[:500]}"
            if wrangled:
                prompt += f"\n\nData wrangling code:\n{wrangled}"
            return prompt

        elif agent_type == "reporter":
            analysis = context.get("analyst", "")
            wrangled = context.get("data_wrangler", "")
            prompt = f"Data pipeline task:\n{request}"
            if wrangled:
                prompt += f"\n\nData processing:\n{wrangled[:500]}"
            if analysis:
                prompt += f"\n\nAnalysis results:\n{analysis}"
            return prompt

        return f"Task:\n{request}"

    @staticmethod
    def _extract_code(text: str) -> str:
        """Extract code from markdown code blocks."""
        import re
        blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        if blocks:
            return blocks[0].strip()
        return text.strip()

    @staticmethod
    def _extract_score(text: str) -> int:
        """Extract numeric score from reviewer output."""
        import re
        # "SCORE: 3/5" or "Score: 4/5"
        match = re.search(r"(?:score|rating)[:\s]*(\d)\s*/\s*5", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # "Score: 4" or "Rating: 3"
        match = re.search(r"(?:score|rating)[:\s]*(\d)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Standalone "4/5" or "3/5"
        match = re.search(r"(\d)\s*/\s*5", text)
        if match:
            return int(match.group(1))
        # "3 out of 5"
        match = re.search(r"(\d)\s*out\s*of\s*5", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0


# --- Output Similarity (for Mode 3 acceptance rate q) ---


def compute_output_similarity(draft_output: str, target_output: str) -> float:
    """Compute similarity between draft and target agent outputs.

    Uses token-level Jaccard similarity as a lightweight proxy.
    For more accurate comparison, a judge model should be used.

    Returns:
        Similarity score in [0, 1]
    """
    if not draft_output or not target_output:
        return 0.0

    draft_tokens = set(draft_output.lower().split())
    target_tokens = set(target_output.lower().split())

    if not draft_tokens or not target_tokens:
        return 0.0

    intersection = draft_tokens & target_tokens
    union = draft_tokens | target_tokens
    return len(intersection) / len(union)


def judge_output_acceptance(
    draft_output: str,
    target_output: str,
    client: OllamaClient,
    threshold: float = 0.7,
) -> tuple[bool, float, str]:
    """Use LLM judge to determine if draft output is acceptable.

    Args:
        draft_output: Output from draft (speculative) agent
        target_output: Output from target (solver) agent
        client: Ollama client for judge calls
        threshold: Minimum score for acceptance

    Returns:
        (accepted, score, explanation)
    """
    judge_prompt = (
        "Compare these two code outputs for the same HPC task.\n\n"
        f"OUTPUT A (draft):\n{draft_output[:1500]}\n\n"
        f"OUTPUT B (target):\n{target_output[:1500]}\n\n"
        "Rate how functionally equivalent they are on a scale of 0.0 to 1.0:\n"
        "- 1.0 = identical functionality, minor style differences\n"
        "- 0.7 = same algorithm, minor implementation differences\n"
        "- 0.3 = different approach but partially correct\n"
        "- 0.0 = completely different or one is wrong\n\n"
        "Respond in exactly this format:\n"
        "SCORE: <number>\n"
        "REASON: <one sentence>"
    )

    try:
        text, _, _ = client.generate(
            prompt=judge_prompt,
            system="You are a code similarity judge. Be precise and concise.",
            max_tokens=100,
            temperature=0.1,
        )

        import re
        match = re.search(r"SCORE:\s*([\d.]+)", text)
        score = float(match.group(1)) if match else 0.0
        score = min(1.0, max(0.0, score))

        reason_match = re.search(r"REASON:\s*(.+)", text)
        reason = reason_match.group(1).strip() if reason_match else text.strip()

        accepted = score >= threshold
        return accepted, score, reason
    except Exception as e:
        return False, 0.0, f"Judge error: {e}"
