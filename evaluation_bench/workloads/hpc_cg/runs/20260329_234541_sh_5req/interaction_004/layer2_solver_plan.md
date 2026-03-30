# Dispatch Plan — SOLVER (RULE-BASED)

## Request
> #include <omp.h>
> 
> struct Point {
> 	double x, y;
> };
> 
> double distance(Point const& p1, Point const& p2) {
> 	return std::sqrt(std::pow(p2.x-p1.x, 2) + std::pow(p2.y-p1.y, 2));
> }
> 
> /* Return the perimeter of the smallest convex polygon that contains all the points in the vector points.
>    Use OpenMP to com
> ... (490 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.424
- **Domain**: hpc, openmp
- **Decomposability**: 0.35

## Metadata
- **Source**: Solver (rule-based)
- **Time**: 0ms (0.0s)

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute planner task
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Prompt**: [stub] Execute code_gen task
- **Tokens**: 4000 | Compute: medium
- **Depends on**: (none)

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Prompt**: [stub] Execute tester task
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute review task
- **Tokens**: 2000 | Compute: medium
- **Depends on**: (none)

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [tester]
- Stage 3: [review]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | medium |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| review | llama3.1-8b-gpu | llama3.1:8b | 2000 | medium |
| **Total** | | | **8000** | |
