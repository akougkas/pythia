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
- **Time**: 30437ms (30.4s)

## Reasoning
This is a focused HPC code generation task: implement a parallel closest-pair algorithm in C++ using MPI + OpenMP. The complexity is medium — the algorithm itself (divide-and-conquer or brute-force with parallel reduction) requires careful thought before coding, and the result needs validation against the provided example. A planner should first decide the parallelization strategy (e.g., partition point pairs across MPI ranks, use OpenMP within each rank, then MPI_Reduce for global minimum), then code_gen implements it, and tester validates correctness and the example output. These three stages are strictly sequential.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the MPI+OpenMP parallel strategy for closest-pair computation
- **Prompt**: Design a parallel closest-pair algorithm for the following C++ function signature:

  double closestPair(std::vector<Point> const& points)

Constraints:
- MPI is already initialized; every rank has a full copy of `points`
- Must use both MPI (inter-rank) and OpenMP (intra-rank) parallelism
- Final minimum distance returned only on rank 0

Decide on:
1. How to partition work across MPI ranks (e.g., divide the O(n²) pair index space — rank r handles pairs where i % num_ranks == r, or a 2D block partition)
2. How OpenMP threads reduce within each rank (parallel for with reduction on local min)
3. How MPI_Reduce combines per-rank minima to rank 0
4. Edge cases: n < 2, single rank, single thread

Output a concise algorithmic plan (pseudocode level) that the code_gen agent will implement exactly.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the closestPair function body using the planner's MPI+OpenMP strategy
- **Prompt**: Implement the body of the following C++ function using MPI + OpenMP as specified by the planner's strategy:

cpp
#include <mpi.h>
#include <omp.h>
#include <vector>
#include <cmath>
#include <limits>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x-p1.x,2) + std::pow(p2.y-p1.y,2));
}

double closestPair(std::vector<Point> const& points) {
    // YOUR IMPLEMENTATION HERE
}


Requirements:
- Follow the planner's partitioning and reduction strategy exactly
- Use `#pragma omp parallel for reduction(min:local_min)` for intra-rank parallelism
- Use `MPI_Reduce` with `MPI_DOUBLE` and `MPI_MIN` to find global minimum on rank 0
- Initialize minimum to `std::numeric_limits<double>::max()`
- Return the global minimum only from rank 0; other ranks may return their local minimum or 0.0
- Handle edge case: if points.size() < 2, return 0.0
- Do NOT call MPI_Init/MPI_Finalize
- Expected output for [{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}] is 1.41421 (distance between {2,3} and {3,4})

Output ONLY the complete, compilable function body (no main, no extra scaffolding).
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Validate the implementation against the provided example and edge cases
- **Prompt**: Given the MPI+OpenMP closestPair implementation produced by code_gen, write a test harness and verify correctness.

Test cases to cover:
1. Provided example: [{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}] → expected 1.41421356... (√2)
2. Two points only: [{0,0},{3,4}] → expected 5.0
3. Duplicate points: [{1,1},{1,1},{5,5}] → expected 0.0
4. Large n stress test (n=1000 random points): result should match a serial brute-force reference

For each test:
- Show the serial brute-force reference answer
- Show how the parallel result should match (within 1e-9 tolerance)
- Flag any race conditions, incorrect MPI reduction, or off-by-one errors in the pair iteration scheme
- Confirm the implementation does NOT call MPI_Init/MPI_Finalize

Output: test harness code + pass/fail assessment for each case + any bugs found with suggested fixes.
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
