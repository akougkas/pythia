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
> /* Return the perimeter of the smallest convex polygon that contains all the points in the vector points.
>    
> ... (641 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.473
- **Domain**: hpc, mpi, openmp
- **Decomposability**: 0.40

## Metadata
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.500

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using OpenMP. The spec is clear, the example is provided, and the complexity is moderate — requiring algorithmic knowledge (convex hull algorithm) plus correct OpenMP parallelization. A planner agent should first decide the algorithm (e.g., Graham scan vs. Jarvis march vs. Andrew's monotone chain) and identify which parts are parallelizable, then a code_gen agent implements it, and a tester validates against the provided example and edge cases. Three agents is appropriate; no stages can run in parallel since each depends on the prior.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Select convex hull algorithm and identify OpenMP parallelization strategy
- **Prompt**: You are designing the implementation strategy for a C++ function `double convexHullPerimeter(std::vector<Point> const& points)` that uses OpenMP. The function must return the perimeter of the convex hull of the input points.

1. Choose the best convex hull algorithm for parallel execution (consider Andrew's Monotone Chain, Graham Scan, Jarvis March). Justify your choice based on parallelizability and correctness guarantees.
2. Identify which phases of the algorithm can be parallelized with OpenMP (e.g., sorting, distance computation, partial hull construction).
3. Note any race conditions or critical sections to avoid.
4. Specify the perimeter computation step (sum of Euclidean distances between consecutive hull vertices, wrapping around).
5. Confirm expected output for the example: points = [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → 13.4477.

Output a concise algorithm plan with pseudocode and annotated parallelism opportunities.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the parallel convex hull perimeter function in C++ with OpenMP
- **Prompt**: Implement the following C++ function using the algorithm plan provided by the planner:

cpp
#include <omp.h>
#include <vector>
#include <cmath>

struct Point { double x, y; };

double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x - p1.x, 2) + std::pow(p2.y - p1.y, 2));
}

double convexHullPerimeter(std::vector<Point> const& points);


Requirements:
- Use Andrew's Monotone Chain (or the algorithm selected by the planner) for correctness.
- Use `#pragma omp parallel for` where appropriate (e.g., parallel sort via `std::sort` with OpenMP-assisted merge, or parallel perimeter summation using `reduction`).
- The perimeter computation MUST use `omp parallel for reduction(+:perimeter)` over hull edges.
- Handle edge cases: fewer than 3 points (return 0.0 or the degenerate distance).
- Do NOT use `std::pow` for squaring in performance-critical loops — use `dx*dx + dy*dy` instead.
- The function must be self-contained (no global state).
- Validate against: input [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → output ≈ 13.4477.

Provide the complete function body only (no main), with inline comments explaining each OpenMP directive.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate test cases and validate the convex hull implementation for correctness and parallelism safety
- **Prompt**: Given the implemented `convexHullPerimeter` function, write a C++ test suite (using assertions or a simple main()) that validates:

1. **Canonical example**: points = [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → expected ≈ 13.4477 (tolerance 1e-3).
2. **Degenerate cases**:
   - Empty vector → 0.0
   - Single point → 0.0
   - Two points → 0.0 (or 2*distance, depending on spec — test both behaviors)
   - All collinear points (e.g., [{0,0},{1,0},{2,0},{3,0}]) → 6.0 (back and forth)
3. **Simple polygon**: Square [{0,0},{1,0},{1,1},{0,1}] → perimeter = 4.0
4. **Thread safety**: Run `convexHullPerimeter` 100 times in parallel using `#pragma omp parallel for` and verify all results match the serial result (no data races).
5. **Performance note**: Assert that with OMP_NUM_THREADS=4, a 10,000-point input completes without deadlock or incorrect result.

For each test, print PASS/FAIL with the computed vs. expected value.
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
