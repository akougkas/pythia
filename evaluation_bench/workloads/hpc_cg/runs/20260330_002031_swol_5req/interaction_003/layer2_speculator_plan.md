# Dispatch Plan — SPECULATOR (CACHE)

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
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.500

## Reasoning
This is a focused HPC code generation task: implement a parallel closest-pair algorithm using MPI + OpenMP. The spec is clear (brute-force O(n²) or divide-and-conquer, parallel reduction), so complexity is moderate. The main stages are: design the parallel strategy (planner), implement the function (code_gen), and validate correctness + edge cases (tester). These must run sequentially since each stage feeds the next. No data discovery or reporting needed.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the MPI+OpenMP parallel strategy for closest-pair distance computation
- **Prompt**: Design a parallel closest-pair algorithm for the following C++ function signature:

  double closestPair(std::vector<Point> const& points)

Constraints:
- MPI is already initialized; every rank has a full copy of `points`.
- Must use both MPI (inter-process) and OpenMP (intra-process) parallelism.
- Final minimum distance must be returned on rank 0 only.

Produce a concrete strategy covering:
1. How to partition the O(n²) pair comparisons across MPI ranks (e.g., row-striped decomposition of the upper triangle).
2. How OpenMP threads reduce within each rank (parallel for + reduction clause).
3. How MPI_Reduce (MPI_MIN) collects the global minimum onto rank 0.
4. Edge cases: n < 2 (return 0.0 or infinity), single rank, single thread.
5. Whether a brute-force or divide-and-conquer approach is more appropriate given the parallel decomposition — justify briefly.

Output a numbered algorithmic plan (no code), including the index ranges each rank owns.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the closestPair function body in C++ using MPI and OpenMP per the plan
- **Prompt**: Implement the body of the following C++ function using the algorithmic plan provided by the planner:

cpp
#include <mpi.h>
#include <omp.h>
#include <vector>
#include <cmath>
#include <limits>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x - p1.x, 2) + std::pow(p2.y - p1.y, 2));
}

double closestPair(std::vector<Point> const& points) {
    // YOUR IMPLEMENTATION HERE
}


Requirements:
1. Partition the upper-triangle pairs (i < j) across MPI ranks using a contiguous row-striped decomposition: rank r owns rows i where (i % nprocs == r), iterating j from i+1 to n-1.
2. Use `#pragma omp parallel for reduction(min:local_min)` inside the rank's row loop for thread-level parallelism.
3. Use `MPI_Reduce(&local_min, &global_min, 1, MPI_DOUBLE, MPI_MIN, 0, MPI_COMM_WORLD)` to collect the result.
4. Handle edge case: if points.size() < 2, return 0.0.
5. Initialize local_min to `std::numeric_limits<double>::max()`.
6. Only rank 0 returns the true global_min; all other ranks may return local_min (caller contract).
7. Do NOT re-initialize MPI or call MPI_Finalize.
8. Use the provided `distance()` function — do not reimplement it.

Output ONLY the completed function body (the full function including signature), with brief inline comments explaining each parallel region.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Write correctness and edge-case tests for the closestPair MPI+OpenMP implementation
- **Prompt**: Write a test suite for the `closestPair` function produced by code_gen. The function signature and context:

cpp
double closestPair(std::vector<Point> const& points);
// MPI initialized externally; every rank has full copy of points.
// Result returned on rank 0.


Provide:
1. **Unit test scaffold** using a `main()` that calls MPI_Init/MPI_Finalize and runs tests only on rank 0 after the call (using `if (rank == 0) assert(...)`).
2. **Test cases** (at minimum):
   - The provided example: `[{2,3},{12,30},{40,50},{5,1},{12,10},{3,4}]` → expected `1.41421` (within 1e-4 tolerance).
   - Two points: `[{0,0},{3,4}]` → expected `5.0`.
   - All identical points: `[{1,1},{1,1},{1,1}]` → expected `0.0`.
   - Edge case: `n=1` → expected `0.0`.
   - Large random input (n=1000): verify result matches a serial brute-force reference.
3. **Serial reference implementation** (brute-force O(n²), single-threaded) for comparison.
4. Instructions for compiling and running with `mpirun -np 4` and OpenMP threads.

Output complete, compilable C++ test code.
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
