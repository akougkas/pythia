# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> #include <mpi.h>
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
> /* Return the distance between the closest two points in the vector points.
>    Use MPI and OpenMP to compute 
> ... (594 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.475
- **Domain**: hpc, mpi, openmp
- **Decomposability**: 0.40

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 22771ms (22.8s)

## Reasoning
This is a focused HPC code generation task: implement a parallel closest-pair algorithm using MPI+OpenMP given a clear spec, signature, and example. The complexity is moderate — the algorithm itself (divide-and-conquer or brute-force with parallel reduction) requires careful parallel design, but the scope is a single function. A planner should decide the parallel strategy first (work decomposition, MPI reduction pattern), then code_gen implements it, and a reviewer validates correctness and parallel hygiene. No data pipeline or experiment stages needed.

## Pipeline: planner -> code_gen -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the MPI+OpenMP parallel strategy for closest-pair computation
- **Prompt**: Design a parallel algorithm for `closestPair(std::vector<Point> const& points)` using MPI + OpenMP. Every MPI rank holds the full points vector. Decide: (1) How to partition the O(n^2) brute-force pair comparisons across MPI ranks using rank/size striding. (2) How to parallelize each rank's local loop chunk with OpenMP (thread-private minimums + reduction). (3) How to perform the final MPI_Reduce to collect the global minimum on rank 0. Output a concise strategy document covering: work decomposition formula, OpenMP reduction pattern, MPI reduction call, and any edge cases (n < 2, single rank, single thread).
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the closestPair function body using the planned MPI+OpenMP strategy
- **Prompt**: Implement the body of `double closestPair(std::vector<Point> const& points)` in C++ using MPI and OpenMP, following the strategy provided by the planner. Requirements:
- Use MPI_Comm_rank / MPI_Comm_size to distribute the outer loop (index i) across ranks via strided partitioning (rank 0 takes i=0,P,2P,...; rank 1 takes i=1,P+1,...)
- For each rank's assigned i values, iterate j from i+1 to n-1 to compute all relevant pairs
- Use `#pragma omp parallel for reduction(min: local_min)` over the inner or outer assigned indices
- Use `MPI_Reduce(&local_min, &global_min, 1, MPI_DOUBLE, MPI_MIN, 0, MPI_COMM_WORLD)` to collect the result
- Return global_min on rank 0; return local_min (or 0.0) on other ranks
- Use the provided `distance(p1, p2)` helper
- Handle edge case: if points.size() < 2, return 0.0
- Do NOT call MPI_Init/MPI_Finalize (already initialized)
- Include necessary headers if any beyond mpi.h and omp.h
Output ONLY the function body (the code inside the braces), ready to paste.
- **Tokens**: 4000 | Compute: medium
- **Depends on**: planner

### 3. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Validate correctness, parallel safety, and MPI reduction semantics of the implementation
- **Prompt**: Review the `closestPair` MPI+OpenMP implementation produced by code_gen. Check for: (1) Correctness — does the work partitioning cover all unique pairs (i,j) with i<j exactly once across all ranks? (2) OpenMP safety — are reductions correctly scoped, no data races on the minimum variable? (3) MPI correctness — is MPI_Reduce called on ALL ranks (collective), correct datatype MPI_DOUBLE, correct root=0? (4) Return value — does rank 0 return global_min, do other ranks behave acceptably? (5) Edge cases — n<2 handled? (6) Verify against the example: points={{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}}, expected output 1.41421 (distance between {2,3} and {3,4}). Flag any bugs and suggest fixes.
- **Tokens**: 2000 | Compute: light
- **Depends on**: code_gen

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [review]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | medium |
| review | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| **Total** | | | **6500** | |
