# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'Bam': The core contributions of the paper "Batch and match: black-box variational inference with a score-based divergence" have been reproduced. This involves 4 major phases and 1020 total subtasks. The workflow includes: The core variational inference algorithms studie
> ... (469 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.467
- **Domain**: ml, research
- **Decomposability**: 0.45

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 40751ms (40.8s)

## Reasoning
This is a research replication workflow for a variational inference paper ('BAM'), requiring literature understanding, algorithm implementation, and experimental replication across multiple sections. The workflow decomposes into 4 natural phases: (1) literature review and method extraction, (2) algorithm implementation, (3) parallel experimental replication for Section 5.1 and Section 5.2 figures, and (4) result analysis and reporting. Phases 3a and 3b (replicating Section 5.1 vs. Figures 5.3/E.6) are independent and can run in parallel after implementation is ready.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> experiment_runner -> result_analyzer -> reporter

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract core algorithms, divergence formulations, and experimental setup from the BAM paper
- **Prompt**: Carefully read and analyze the paper 'Batch and Match: Black-Box Variational Inference with a Score-Based Divergence'. Extract: (1) the score-based divergence objective (the 'batch and match' loss), including its mathematical formulation; (2) the black-box VI algorithm details — gradient estimators, sample sizes, batch construction; (3) the baseline methods compared against (e.g., ADVI, BBVI variants); (4) the experimental setup for Section 5.1 (model benchmarks, metrics reported) and Section 5.2 (Figure 5.3 and Figure E.6 — what distributions/models are used, what axes are plotted, what the figures demonstrate). Produce a structured extraction document with equations, pseudocode where possible, and a replication checklist.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan mapping paper claims to runnable experiments
- **Prompt**: Given the structured extraction from the BAM paper literature review, design a concrete replication plan. Specify: (1) the software environment (Python, JAX/NumPy/PyTorch, any probabilistic programming libraries); (2) the exact model targets for Section 5.1 benchmarks (e.g., log-normal, Student-t, hierarchical models) with parameter settings matching the paper; (3) the experimental conditions for Figure 5.3 (e.g., varying sample sizes, step sizes, or iteration counts) and Figure E.6 (likely an ablation or convergence plot from Appendix E); (4) evaluation metrics — ELBO, KL divergence, Wasserstein distance, or whatever the paper reports; (5) a mapping of each figure/table to specific code modules. Output a machine-readable experiment config schema (JSON or YAML) and a dependency graph of experiments.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the BAM core algorithm and all baseline VI methods from scratch
- **Prompt**: Implement the full BAM (Batch and Match) black-box variational inference algorithm as described in the paper. Your implementation must include: (1) the score-based divergence loss (the core BAM objective) — implement the batch construction, score function computation, and the matching step; (2) the gradient estimator used in BAM (REINFORCE, reparameterization, or the paper's specific estimator); (3) baseline implementations: ADVI and any other VI baselines compared in Section 5; (4) a modular variational family class (mean-field Gaussian at minimum, full-rank if used); (5) target log-probability interfaces for all benchmark models from Section 5.1; (6) utility functions for ELBO computation and KL divergence metrics. Use JAX or PyTorch (prefer JAX for auto-diff and JIT). Structure as a clean Python package with separation between algorithm, models, and evaluation. Include docstrings and inline comments referencing paper equations by number.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute Section 5.2 experiments to replicate Figure 5.3 and Figure E.6
- **Prompt**: Using the implemented BAM algorithm, replicate Figure 5.3 and Figure E.6 from the paper. For Figure 5.3: identify the exact experimental variable on each axis (e.g., number of samples, batch size, or a hyperparameter sweep), run the grid of conditions specified, and collect the plotted metric at each point. For Figure E.6 (Appendix E): identify whether this is an ablation, sensitivity analysis, or convergence diagnostic — run the corresponding experiment. For both figures: (1) match axis ranges and scales to the paper; (2) save raw data to files; (3) generate matplotlib/seaborn plots that visually match the paper figures; (4) annotate any deviations from the paper's reported curves. Run experiments in parallel across conditions where possible.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. experiment_runner -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Execute Section 5.2 experiments to replicate Figure 5.3 and Figure E.6
- **Prompt**: Using the implemented BAM algorithm, replicate Figure 5.3 and Figure E.6 from the paper. For Figure 5.3: identify the exact experimental variable on each axis (e.g., number of samples, batch size, or a hyperparameter sweep), run the grid of conditions specified, and collect the plotted metric at each point. For Figure E.6 (Appendix E): identify whether this is an ablation, sensitivity analysis, or convergence diagnostic — run the corresponding experiment. For both figures: (1) match axis ranges and scales to the paper; (2) save raw data to files; (3) generate matplotlib/seaborn plots that visually match the paper figures; (4) annotate any deviations from the paper's reported curves. Run experiments in parallel across conditions where possible.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 6. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replicated results against paper claims and score replication fidelity
- **Prompt**: Analyze the outputs from both experiment runners (Section 5.1 benchmarks and Section 5.2 figures) and produce a replication fidelity report. For each paper claim: (1) state the original reported result (number, trend, or qualitative claim); (2) state the replicated result; (3) compute a numerical match score (percentage error for quantitative, qualitative match for trends); (4) classify as: EXACT MATCH (< 1% error), CLOSE MATCH (1-5%), PARTIAL MATCH (5-20%), or DEVIATION (> 20%). Identify any systematic differences and hypothesize causes (hyperparameter sensitivity, stochasticity, implementation ambiguity). Produce a structured JSON replication scorecard and a human-readable summary table.
- **Tokens**: 2000 | Compute: light
- **Depends on**: experiment_runner

### 7. reporter -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Synthesize all findings into a final replication report with figures and conclusions
- **Prompt**: Produce a comprehensive replication report for the BAM paper ('Batch and Match: Black-Box Variational Inference with a Score-Based Divergence'). Structure the report as: (1) Executive Summary — what was replicated, overall fidelity score; (2) Methods — description of implementation choices, deviations from paper, software stack; (3) Section 5.1 Results — replicated table vs. paper table, side-by-side comparison; (4) Section 5.2 Results — replicated Figure 5.3 and Figure E.6 with commentary on visual/numerical match; (5) Replication Scorecard — per-claim fidelity scores from the result analyzer; (6) Discussion — what was easy/hard to replicate, what the paper could clarify, lessons learned. Format as a well-structured Markdown document suitable for inclusion in a research artifact. Embed or reference all generated figures.
- **Tokens**: 1500 | Compute: light
- **Depends on**: result_analyzer

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]
- Stage 5: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| experiment_runner | claude-haiku-cloud | claude-haiku-4-5-20251001 | 3000 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| reporter | claude-haiku-cloud | claude-haiku-4-5-20251001 | 1500 | light |
| **Total** | | | **16000** | |
