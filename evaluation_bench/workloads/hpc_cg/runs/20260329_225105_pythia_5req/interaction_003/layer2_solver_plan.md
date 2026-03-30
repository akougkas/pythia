# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> #include <mpi.h>
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
>    Use MPI to compute in parallel. Assume MPI has 
> ... (566 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.471
- **Domain**: hpc, mpi
- **Decomposability**: 0.40

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 34130ms (34.1s)

## Reasoning
This is a moderately complex HPC code generation task: implement a parallel closest-pair algorithm using MPI in C++. The problem is well-specified with a clear interface, example I/O, and stated constraints (MPI already initialized, all ranks have full data, result on rank 0). The decomposability is low (0.40) because the core work is sequential code generation, but we benefit from a lightweight planning step to choose the parallel strategy (e.g., naive O(n²) work-distribution vs. divide-and-conquer), followed by heavy code generation, then validation. A reviewer pass ensures MPI correctness and edge cases. Three stages, mostly sequential given data dependencies.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the MPI parallelization strategy for the closest-pair problem
- **Prompt**: Design a parallel strategy for implementing `closestPair` using MPI in C++. The function receives a `std::vector<Point>` where every MPI rank already holds a full copy. The result (minimum distance) must be returned on rank 0. Consider: (1) Work decomposition — how to partition the O(n²) pairs across ranks without redundant computation (e.g., assign each rank a contiguous row-band of the upper triangle of the distance matrix). (2) Local reduction — each rank finds its local minimum. (3) Global reduction — use `MPI_Reduce` with `MPI_DOUBLE` and `MPI_MIN` to collect the global minimum on rank 0. (4) Edge cases: n < 2, n smaller than MPI rank count, rank 0 handling when result is only needed there. Output a concise algorithmic plan (pseudocode-level) that the code_gen agent will implement. Specify exact MPI calls to use.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the MPI closest-pair function in C++ following the planner's strategy
- **Prompt**: Implement the following C++ function using MPI:

cpp
#include <mpi.h>
#include <vector>
#include <cmath>
#include <limits>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x - p1.x, 2) + std::pow(p2.y - p1.y, 2));
}

double closestPair(std::vector<Point> const& points);


Requirements from the planner's strategy:
- MPI is already initialized; do NOT call MPI_Init or MPI_Finalize.
- Every rank has a complete copy of `points`.
- Use `MPI_Comm_rank` / `MPI_Comm_size` to determine each rank's slice of work.
- Partition the upper-triangle pairs (i < j) across ranks: rank r processes pairs where `i % size == rank` (or equivalent contiguous band) to avoid duplicate computation.
- Each rank computes its local minimum distance over its assigned pairs.
- Use `MPI_Reduce(&local_min, &global_min, 1, MPI_DOUBLE, MPI_MIN, 0, MPI_COMM_WORLD)` to collect the result on rank 0.
- Rank 0 returns `global_min`; all other ranks return `0.0` (or any sentinel — only rank 0's return value is used).
- Handle edge cases: if `points.size() < 2`, return `0.0` on all ranks.
- Use only standard C++11 and MPI-2 features. No Boost. No OpenMP.
- Output the complete, compilable function body only (no main, no test harness).
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate correctness and edge-case tests for the MPI closestPair implementation
- **Prompt**: Write a complete MPI test harness in C++ for the `closestPair` function. Include the following test cases, each run with `mpirun -np 4` and verified on rank 0:

1. **Example case**: `[{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}]` → expected `1.41421356...` (distance between {2,3} and {3,4}).
2. **Two points**: `[{0,0},{3,4}]` → expected `5.0`.
3. **All same point**: `[{1,1},{1,1},{1,1}]` → expected `0.0`.
4. **Single point**: `[{5,5}]` → expected `0.0` (edge case, n < 2).
5. **Large random test**: generate 1000 random points, run both the MPI version and a serial O(n²) brute-force, assert `|mpi_result - serial_result| < 1e-9`.
6. **Rank count > n**: use only 2 points but 4 ranks — verify no crash and correct result.

For each test, print PASS/FAIL with expected vs actual values. Structure the harness so rank 0 performs all assertions and prints results. Include the necessary `#include` directives and a `main` with `MPI_Init`/`MPI_Finalize`.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the MPI implementation for correctness, performance, and HPC best practices
- **Prompt**: Review the generated `closestPair` MPI C++ implementation against these criteria and produce a scored report:

1. **MPI Correctness** (0–3 pts): Are MPI calls used correctly? Is `MPI_Reduce` with `MPI_MIN` used properly? Are there any collective call mismatches (all ranks must call the same collectives)? Is there any risk of deadlock?
2. **Work Distribution** (0–2 pts): Is the upper-triangle pair space partitioned without redundancy (i.e., each pair (i,j) with i<j processed exactly once across all ranks)? Is load roughly balanced?
3. **Edge Case Handling** (0–2 pts): Does it handle n<2, n<num_ranks, and identical points correctly?
4. **Memory & Performance** (0–2 pts): Is memory usage O(1) extra per rank? Is there unnecessary communication (e.g., broadcasting points when they're already present)?
5. **Code Quality** (0–1 pt): Readable, standard C++11, no undefined behavior.

For each criterion, cite the specific line(s) of code and explain the score. End with a total score /10 and a list of required fixes (if any) before this code is production-ready.
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
