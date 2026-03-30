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
> /* Return the perimeter of the smallest convex polygon that contains all the points in the vector points.
>    
> ... (641 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.473
- **Domain**: hpc, mpi, openmp
- **Decomposability**: 0.40

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 28417ms (28.4s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using MPI+OpenMP. The algorithm design (which parallel convex hull strategy to use — e.g., distributed Graham scan or parallel Jarvis march with local hulls merged across ranks) needs to precede code generation. Testing/validation is straightforward but important given the numerical geometry involved. Decomposability is low (0.40) because code_gen depends on the planner's algorithm choice, and tester depends on code_gen — the pipeline is largely sequential.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the parallel convex hull algorithm strategy for MPI+OpenMP
- **Prompt**: Design a parallel algorithm for computing the convex hull perimeter of a 2D point set using MPI + OpenMP. Requirements: (1) Every MPI rank already holds a complete copy of `points`. (2) MPI handles inter-rank parallelism; OpenMP handles intra-rank parallelism. (3) Final perimeter is returned only on rank 0. Recommend an approach: e.g., each rank computes a local convex hull over an OpenMP-parallelized subset of points, then rank 0 merges all local hulls and computes the final hull + perimeter. Specify: (a) how to partition points across ranks, (b) how OpenMP threads accelerate the local hull computation, (c) how local hull vertices are communicated to rank 0 via MPI (e.g., MPI_Gather with variable counts), (d) the sequential merge step on rank 0, (e) which convex hull algorithm to use locally (Andrew's monotone chain recommended for simplicity). Output a concise algorithm specification with data flow, not code.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement convexHullPerimeter in C++ using MPI+OpenMP per the planner's spec
- **Prompt**: Implement the C++ function `double convexHullPerimeter(std::vector<Point> const& points)` using MPI and OpenMP, following the algorithm specification from the planner. Key constraints:
- `#include <mpi.h>` and `#include <omp.h>` are already present; MPI is already initialized.
- `Point` is `struct Point { double x, y; };` and `distance(Point, Point)` is available.
- Each MPI rank holds a full copy of `points`; partition by rank index: rank r processes indices [r * chunk, (r+1) * chunk).
- Use OpenMP `#pragma omp parallel for` to accelerate local hull construction (Andrew's monotone chain: sort points, build lower+upper hull).
- Gather local hull vertices to rank 0 using MPI_Gather / MPI_Gatherv (pack Point as two doubles).
- Rank 0 runs a final convex hull on the union of all local hull vertices, then computes perimeter by summing `distance()` between consecutive hull vertices (wrap-around included).
- All other ranks return 0.0.
- Validate against example: input [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → output ≈ 13.4477.
Produce only the function body (no main). Use standard C++17.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate correctness and edge-case tests for the convex hull implementation
- **Prompt**: Write a test harness for `convexHullPerimeter` (MPI+OpenMP). Include: (1) The provided example: [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → expected ≈ 13.4477 (tolerance 1e-3). (2) Degenerate cases: all collinear points (perimeter = 2 * max distance), single point (perimeter = 0), two points (perimeter = 0 or 2*dist depending on spec — note this). (3) A regular polygon (e.g., square with known perimeter). (4) A large random point set where the convex hull is a subset — verify perimeter > 0 and that interior points don't affect the result. Use MPI_Init/Finalize in main, run assertions only on rank 0 after calling the function. Output a compilable C++ test file.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the MPI+OpenMP implementation for correctness, race conditions, and performance
- **Prompt**: Review the generated `convexHullPerimeter` implementation for: (1) Correctness — does the parallel partitioning + local hull + merge produce the same result as a sequential convex hull? Are all edge cases handled (n < 3, collinear points)? (2) MPI correctness — are MPI_Gatherv counts/displacements computed correctly? Is the Point struct serialized safely as two doubles? Is there any deadlock risk? (3) OpenMP safety — are there data races in the parallel hull construction? Is the sort thread-safe (each thread works on its own subarray)? (4) Performance — is the OpenMP parallelism over a meaningful work unit, or is the overhead likely to dominate for small inputs? Suggest fixes for any issues found. Score overall quality 1-10.
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
