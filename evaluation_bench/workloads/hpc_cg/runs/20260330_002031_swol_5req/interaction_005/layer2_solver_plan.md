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
- **Time**: 36514ms (36.5s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using MPI+OpenMP. The algorithm design (which convex hull approach works well with MPI decomposition) must precede code generation, and a tester should validate correctness and parallel behavior. Complexity is medium — the parallel convex hull has non-trivial merge logic but the scope is a single function. Planner and tester are lightweight bookends around the heavy code_gen core.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the parallel convex hull strategy (MPI decomposition + OpenMP threading + merge phase)
- **Prompt**: Design a parallel algorithm for computing the convex hull perimeter of a 2D point set using MPI + OpenMP. Each MPI rank has a full copy of the points vector. Requirements:
1. Choose an appropriate convex hull algorithm (e.g., Graham scan, Andrew's monotone chain, Jarvis march) that parallelizes well.
2. Describe how to partition work across MPI ranks — e.g., split points by index range, compute local hulls, then merge.
3. Describe the OpenMP parallelization within each rank (e.g., parallel sort, parallel local hull construction if applicable).
4. Describe the MPI merge step: how local convex hulls are gathered on rank 0 and combined into the global hull.
5. Note any edge cases: fewer points than ranks, collinear points, single-point or two-point inputs.
Output a concise algorithm outline (pseudocode or bullet steps) that the code_gen agent will implement.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement convexHullPerimeter() in C++ using MPI + OpenMP per the planner's design
- **Prompt**: Implement the following C++ function using the algorithm plan provided by the planner:

cpp
#include <mpi.h>
#include <omp.h>
#include <vector>
#include <cmath>
#include <algorithm>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x-p1.x,2) + std::pow(p2.y-p1.y,2));
}

double convexHullPerimeter(std::vector<Point> const& points);


Requirements:
- Use Andrew's monotone chain (or the algorithm chosen by planner) for correctness and O(n log n) complexity.
- Each MPI rank processes a subset of points to build a local partial hull, then all local hull points are gathered to rank 0 via MPI_Gather or MPI_Gatherv.
- Rank 0 computes the global convex hull from the union of all gathered hull points.
- Use OpenMP (`#pragma omp parallel for`) to parallelize the sorting or the local hull point processing within each rank.
- MPI is already initialized; do NOT call MPI_Init/MPI_Finalize.
- Return the perimeter (sum of Euclidean distances between consecutive hull vertices) only on rank 0; other ranks may return 0.0.
- Handle edge cases: n < 2 points, all collinear, fewer points than ranks.
- Use MPI_Bcast or MPI_Scatter to distribute index ranges; use MPI_Gatherv since local hull sizes differ per rank.
- The function must compile with: `mpicxx -fopenmp -std=c++17`

Provide the complete, compilable implementation with inline comments explaining the MPI and OpenMP logic.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Write correctness and parallel-behavior tests for convexHullPerimeter()
- **Prompt**: Write a test suite for the `convexHullPerimeter` MPI+OpenMP function. Include:

1. **Correctness tests** (run with `mpirun -n 4`):
   - Example from spec: points = {(0,3),(1,1),(2,2),(4,4),(0,0),(1,2),(3,1),(3,3)} → expected perimeter ≈ 13.4477 (tolerance 1e-3)
   - Unit square: {(0,0),(1,0),(1,1),(0,1)} → perimeter = 4.0
   - Collinear points: {(0,0),(1,0),(2,0),(3,0)} → perimeter = 6.0
   - Triangle: {(0,0),(3,0),(0,4)} → perimeter = 12.0
   - Single point: {(1,1)} → perimeter = 0.0
   - Two points: {(0,0),(3,4)} → perimeter = 10.0

2. **Parallel consistency test**: verify the result is identical when run with 1, 2, and 4 MPI ranks.

3. **Edge case**: n_points < n_ranks (e.g., 2 points, 4 ranks) — must not crash.

Provide test code as a self-contained `main()` that calls `convexHullPerimeter`, checks results with assertions, and prints PASS/FAIL per case. Include the MPI boilerplate (MPI_Init/Finalize) in main.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the implementation for correctness, MPI safety, OpenMP race conditions, and performance
- **Prompt**: Review the MPI+OpenMP implementation of `convexHullPerimeter` produced by code_gen. Evaluate:

1. **Correctness**: Does the convex hull algorithm (monotone chain or chosen variant) correctly handle all edge cases (collinear, duplicate points, n<3)? Is the perimeter calculation over the ordered hull vertices correct?
2. **MPI correctness**: Are MPI_Gatherv buffer sizes and displacements computed correctly? Is there a risk of deadlock? Are all ranks synchronized before gather?
3. **OpenMP safety**: Are there any data races in the parallel regions? Are shared vs. private variables correctly scoped?
4. **Performance**: Is the parallelization meaningful — does each rank do O(n/p) work before the merge? Is the OpenMP parallelism applied to a sufficiently large loop?
5. **Robustness**: Does it handle the case where some ranks receive 0 points gracefully?

Score each dimension 1-5 and provide specific fix suggestions for any score below 4.
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
