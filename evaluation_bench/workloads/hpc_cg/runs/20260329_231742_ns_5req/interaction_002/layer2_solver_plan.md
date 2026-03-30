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
- **Time**: 30167ms (30.2s)

## Reasoning
This is a focused HPC code generation task: implement a parallel closest-pair algorithm using MPI+OpenMP with a clear spec and example. Complexity is moderate — the algorithm itself (divide-and-conquer or brute-force with parallelism) needs careful design before coding, and the result needs validation against the example. Three agents suffice: a planner to choose the parallel strategy (work distribution across MPI ranks + OpenMP threads), a code_gen to write the implementation, and a tester to verify correctness and edge cases. No parallel agent stages are needed since each step depends on the prior.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the MPI+OpenMP parallel strategy for closest-pair computation
- **Prompt**: Design a parallel closest-pair algorithm for the following C++ function signature:

  double closestPair(std::vector<Point> const& points)

Constraints:
- MPI is already initialized; every rank has a full copy of `points`
- Must use both MPI (across ranks) and OpenMP (within each rank)
- Final answer returned only on rank 0

Decide between: (a) brute-force O(n²) with parallel work partitioning, or (b) divide-and-conquer. Given the problem gives no n constraint and the example is small, recommend the approach that is correct, simple, and parallelizable.

Output:
1. Chosen strategy and justification (1 paragraph)
2. MPI work decomposition: how to split the O(n²) pair comparisons across R ranks
3. OpenMP usage: which loop(s) to parallelize, reduction strategy for local minimum
4. MPI reduction: how to collect per-rank minimums to rank 0 (MPI_Reduce with MPI_DOUBLE and MPI_MIN)
5. Edge cases: n=0, n=1, all identical points
6. Pseudocode (10-20 lines)
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the MPI+OpenMP closestPair function in C++
- **Prompt**: Implement the following C++ function using the strategy provided by the planner:

cpp
#include <mpi.h>
#include <omp.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <limits>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x-p1.x,2) + std::pow(p2.y-p1.y,2));
}

double closestPair(std::vector<Point> const& points);


Requirements:
- Partition the n*(n-1)/2 unique pairs across MPI ranks by assigning row ranges of the outer loop (index i) to each rank: rank r handles rows i where i % size == rank, or a contiguous block [i_start, i_end)
- Within each rank, use `#pragma omp parallel for reduction(min:localMin)` over the inner loop (index j > i)
- Initialize local minimum to `std::numeric_limits<double>::max()`
- Use `MPI_Reduce(&localMin, &globalMin, 1, MPI_DOUBLE, MPI_MIN, 0, MPI_COMM_WORLD)` to collect result on rank 0
- Handle edge cases: if points.size() < 2, return 0.0
- Do NOT call MPI_Init or MPI_Finalize
- Return globalMin on rank 0; return value on other ranks is unspecified (may return localMin)

Expected: closestPair([{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}]) == 1.41421 (distance between {2,3} and {3,4})

Provide the complete, compilable function body only.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Write and validate test cases for the closestPair MPI+OpenMP implementation
- **Prompt**: Given the closestPair MPI+OpenMP implementation, write a test harness and test cases.

Test cases to cover:
1. **Given example**: points=[{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}] → expected ≈ 1.41421356 (√2)
2. **Two points**: [{0,0},{3,4}] → expected 5.0
3. **Identical points**: [{1,1},{1,1},{5,5}] → expected 0.0
4. **Single point**: [{1,1}] → expected 0.0 (edge case)
5. **Collinear**: [{0,0},{1,0},{2,0},{3,0}] → expected 1.0
6. **Large distance**: [{0,0},{1000,1000}] → expected √2000000 ≈ 1414.2135

For each test:
- Show expected value
- Show tolerance for floating-point comparison (use epsilon = 1e-4)
- Note that only rank 0's return value is checked

Also identify:
- Any race conditions or MPI correctness issues to watch for in the implementation
- Whether the MPI_Reduce call is correctly placed (all ranks must call it)
- Compilation command: `mpic++ -fopenmp -O2 -o closest closest.cpp`

Format output as a C++ test harness with `assert` or manual epsilon checks, wrapped in a `main()` that calls MPI_Init/MPI_Finalize.
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
