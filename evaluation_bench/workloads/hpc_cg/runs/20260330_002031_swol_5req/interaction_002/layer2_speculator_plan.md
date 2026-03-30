# Dispatch Plan — SPECULATOR (CACHE)

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
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.500

## Reasoning
This is a focused HPC code generation task: implement a parallel closest-pair brute-force search using OpenMP. The spec is clear (brute-force O(n²) with OpenMP reduction), complexity is medium-low — a planner should sketch the parallel reduction strategy first, then code_gen implements it, and tester validates correctness and parallel behavior. No data discovery or research is needed.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the OpenMP parallel reduction strategy for closest-pair brute-force
- **Prompt**: Design the parallel algorithm for `closestPair` using OpenMP. The function receives a `std::vector<Point>` and must return the minimum Euclidean distance between any two distinct points. Outline: (1) why a brute-force O(n²) double loop is appropriate here, (2) how to use `#pragma omp parallel for` with a `reduction(min:...)` clause or a thread-local minimum pattern to avoid race conditions, (3) any edge cases (n<2, identical points). Produce a concise algorithm sketch with pseudocode — no full C++ yet.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the OpenMP closest-pair function in C++
- **Prompt**: Implement `double closestPair(std::vector<Point> const& points)` in C++ using OpenMP, following the strategy from the planner. Requirements: (1) use `#pragma omp parallel for` over the outer loop (i from 0 to n-1, j from i+1 to n-1) with a thread-local `double localMin = DBL_MAX` pattern and a final `#pragma omp critical` or `reduction` to merge — choose whichever avoids false sharing better, (2) call the provided `distance()` helper, (3) handle edge case n < 2 by returning 0.0, (4) include necessary headers (`<vector>`, `<cfloat>`, `<cmath>`). The example: input [{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}] must produce ≈1.41421 (points {2,3} and {3,4}). Return only the completed function body plus any needed includes.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Write and validate unit tests for closestPair covering correctness and parallel edge cases
- **Prompt**: Write C++ test cases for `closestPair` (compatible with a simple main-based harness or Google Test). Cover: (1) the provided example [{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}] → ≈1.41421, (2) two-point input → exact distance, (3) collinear points, (4) duplicate points (distance=0), (5) large n (e.g. 10,000 random points) to stress the OpenMP path and verify result is deterministic across runs, (6) n=1 edge case (expect 0.0 or graceful return). For each test state the expected output and tolerance (use epsilon=1e-5 for floating-point comparisons). Also note any OpenMP-specific pitfalls to check (e.g. setting OMP_NUM_THREADS=1 vs 4 should give identical results).
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the implementation for correctness, race conditions, and OpenMP best practices
- **Prompt**: Review the `closestPair` OpenMP implementation produced by code_gen. Check: (1) absence of data races — verify the reduction/critical pattern is correct, (2) loop bounds correctness (i < n, j starts at i+1 to avoid double-counting and self-comparison), (3) use of `distance()` helper vs inlining — flag if pow/sqrt can be avoided for the comparison step (compare squared distances for speed, converting only the final result), (4) thread safety of `DBL_MAX` initialization per thread, (5) whether `collapse(2)` could improve load balancing for small n, (6) compliance with the given struct/function signatures. Provide a scored assessment (1–10) and a short list of actionable improvements.
- **Tokens**: 2000 | Compute: light
- **Depends on**: code_gen

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [review, tester] (parallel)

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| review | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| **Total** | | | **8000** | |
