# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
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
>    Use OpenMP to com
> ... (490 chars total)

## Intent
- **Task type**: hpc_code_gen
- **Complexity**: 0.424
- **Domain**: hpc, openmp
- **Decomposability**: 0.35

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 23640ms (23.6s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using OpenMP. The spec is clear, the example is given, and the helper `distance` function already exists. Complexity is moderate — the algorithm design (which convex hull variant parallelizes well) should inform the implementation, and a tester should validate the provided example. Three agents in a linear chain is appropriate; no parallel stages needed since each depends on the prior.

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Select and outline a convex hull algorithm suitable for OpenMP parallelization
- **Prompt**: We need to implement `convexHullPerimeter` in C++ using OpenMP. The function receives a `std::vector<Point>` and must return the perimeter of the convex hull as a `double`. A `distance(Point, Point)` helper is already available.

Your job:
1. Recommend a convex hull algorithm that has parallelizable stages (e.g., Andrew's monotone chain, Jarvis march, or divide-and-conquer). Justify why it suits OpenMP.
2. Identify which steps can use `#pragma omp parallel for` with reductions (e.g., finding min/max x for anchor points).
3. Note any thread-safety concerns (e.g., shared hull vector, reduction variables).
4. Outline the step-by-step algorithm so the code_gen agent can implement it directly.

Keep output concise — a numbered outline with brief notes on parallelism per step.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the parallel convexHullPerimeter function in C++ with OpenMP
- **Prompt**: Using the algorithm plan provided, implement the following C++ function:

cpp
#include <omp.h>
struct Point { double x, y; };
double distance(Point const& p1, Point const& p2);

double convexHullPerimeter(std::vector<Point> const& points);


Requirements:
- Use OpenMP (`#pragma omp parallel for` with reductions) for any embarrassingly parallel steps (e.g., finding leftmost/rightmost points, computing cross products across a range).
- The final hull traversal for perimeter summation may also use a parallel reduction.
- Handle edge cases: fewer than 3 points (return 0.0 or the segment/point distance), duplicate points.
- Verify correctness against the provided example:
  - Input:  `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]`
  - Expected output: `13.4477`
- Do NOT use external geometry libraries — implement the hull algorithm from scratch.
- Return only the compilable function body (and any necessary helpers), with inline comments explaining each OpenMP pragma.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Write and run validation tests for convexHullPerimeter including the given example
- **Prompt**: Given the implemented `convexHullPerimeter` function, write a C++ test suite (using assertions or a simple test harness — no external frameworks required) that validates:

1. **Provided example**: `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]` → expected `13.4477` (tolerance ±0.001).
2. **Degenerate cases**:
   - All collinear points (e.g., `[{0,0},{1,0},{2,0}]`) → perimeter = 4.0 (line back and forth is degenerate; clarify expected behavior).
   - Single point → 0.0.
   - Two points → 2 × distance.
3. **Known convex polygon**: A square `[{0,0},{1,0},{1,1},{0,1}]` → perimeter = 4.0.
4. **Thread-safety check**: Run the function 100× in parallel (`#pragma omp parallel for`) and assert all results match the serial result.

For each test, print PASS/FAIL with the computed vs. expected value. Also note any compilation flags needed (e.g., `-fopenmp -O2`).
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
