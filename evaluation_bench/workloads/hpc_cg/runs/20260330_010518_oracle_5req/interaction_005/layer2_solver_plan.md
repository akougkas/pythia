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
- **Time**: 31511ms (31.5s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using MPI+OpenMP. The algorithm design (choosing a hull algorithm suitable for parallelization, e.g. parallel Graham scan or distributed Jarvis march) must precede code generation, and a tester should validate correctness against the provided example. Complexity is moderate — the parallelization strategy is non-trivial but the scope is a single function, so 3 agents suffice with planner→code_gen→tester as a linear pipeline.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design a parallel convex hull algorithm strategy using MPI + OpenMP suitable for a single-function implementation
- **Prompt**: Design the parallel algorithm for computing a convex hull perimeter over a distributed point set using MPI + OpenMP. The function signature is `double convexHullPerimeter(std::vector<Point> const& points)`. Every MPI rank holds a full copy of the points. The final perimeter must be returned on rank 0.

Your plan must specify:
1. Which convex hull algorithm to use (e.g. Andrew's monotone chain, Graham scan, Jarvis march) and why it parallelizes well in this MPI+OpenMP context.
2. How to partition work across MPI ranks (e.g. split point array into chunks, each rank computes a local hull).
3. How OpenMP is used within each rank (e.g. parallel sort, parallel local hull construction, or parallel distance accumulation).
4. How local hulls from all ranks are merged on rank 0 (e.g. gather all local hull points, run a final sequential hull on the merged set).
5. How the perimeter is computed from the final hull point sequence.
6. Any edge cases: fewer points than ranks, collinear points, duplicate points.

Output a concise step-by-step algorithm plan (pseudocode level) that the code_gen agent can implement directly.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the MPI+OpenMP parallel convex hull perimeter function in C++ following the planner's algorithm
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
- MPI is already initialized. Do NOT call MPI_Init/MPI_Finalize.
- Every rank receives a complete copy of `points`.
- Use MPI to distribute hull computation across ranks (split points into chunks by rank, each rank computes local convex hull of its chunk).
- Use OpenMP (`#pragma omp parallel`) within each rank for the local sort or hull computation step.
- Rank 0 gathers all local hull points via MPI_Gather or MPI_Gatherv, then computes the final global convex hull and its perimeter.
- Only rank 0 returns the correct perimeter; other ranks may return 0.0.
- Use Andrew's monotone chain algorithm (O(n log n)) for hull computation — it is straightforward to parallelize the sort with OpenMP.
- Handle edge cases: 0 or 1 points (return 0.0), 2 points (return 2*distance), collinear points.
- The example: input `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]` must produce perimeter ≈ 13.4477.
- Provide the complete, compilable function body. Include all necessary headers used inside the function.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Validate the implementation against the provided example and edge cases, and review MPI/OpenMP correctness
- **Prompt**: Review and test the convex hull perimeter implementation produced by code_gen.

1. **Correctness check against the given example:**
   - Input: `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]`
   - Expected output: `13.4477` (±0.001 tolerance)
   - Manually trace or verify the hull points: expected hull is `{0,0},{3,1},{4,4},{0,3}` (counterclockwise) — verify the perimeter math.

2. **Edge case validation:**
   - 0 points → 0.0
   - 1 point → 0.0
   - 2 points → 2 * distance
   - All collinear points (e.g. `{0,0},{1,1},{2,2}`) → correct degenerate hull perimeter
   - Single rank execution (MPI size = 1) → still correct

3. **MPI correctness review:**
   - Confirm MPI_Init/MPI_Finalize are NOT called inside the function.
   - Confirm MPI_Gatherv (or equivalent) is used correctly for variable-length local hulls.
   - Confirm no MPI deadlock risk (all ranks participate in collective calls).

4. **OpenMP correctness review:**
   - Confirm no data races in the parallel section.
   - Confirm thread-safe use of `std::sort` or equivalent.

5. **Output:** A bullet-point test report: PASS/FAIL per check, and any bugs found with suggested fixes.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [tester]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| **Total** | | | **6000** | |
