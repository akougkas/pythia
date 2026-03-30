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
- **Time**: 39535ms (39.5s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using OpenMP in C++. The spec is clear (signature, example I/O, helper functions already provided), so complexity is low-medium. The main stages are algorithm design (which convex hull algorithm parallelizes well with OpenMP), implementation, and validation — with review optional. Planner and code_gen are sequential; tester can partially overlap with review since both operate on the generated code.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Select and outline the best convex hull algorithm for OpenMP parallelization
- **Prompt**: You are designing the algorithm strategy for a C++ OpenMP convex hull perimeter function. The function signature is `double convexHullPerimeter(std::vector<Point> const& points)` where Point has double x, y fields. A `distance(Point, Point)` helper is already available.

Your task:
1. Recommend the best convex hull algorithm for OpenMP parallelization (e.g., parallel Graham scan, parallel Jarvis march, or Andrew's monotone chain with parallel pre-sort). Justify the choice based on parallelism granularity and correctness guarantees.
2. Identify which sub-steps can be parallelized with `#pragma omp parallel for` and which must remain serial (e.g., the merge/wrap step).
3. Outline the step-by-step algorithm pseudocode, clearly marking OMP-parallel sections vs. serial sections.
4. Note any race conditions or shared-state hazards to avoid.
5. Specify the expected perimeter for the example input [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] = 13.4477 and which hull points produce it.

Output a concise structured plan (pseudocode + annotations), NOT C++ code.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the parallelized convex hull perimeter function in C++ with OpenMP
- **Prompt**: You are implementing `double convexHullPerimeter(std::vector<Point> const& points)` in C++ using OpenMP, based on the algorithm plan provided.

Context already in scope:
cpp
#include <omp.h>
struct Point { double x, y; };
double distance(Point const& p1, Point const& p2) {
    return std::sqrt(std::pow(p2.x-p1.x, 2) + std::pow(p2.y-p1.y, 2));
}


Requirements:
1. Implement Andrew's monotone chain (or the algorithm recommended by the planner) for convex hull computation.
2. Use `#pragma omp parallel for` with appropriate `reduction`, `ordered`, or `critical` clauses where parallelism is safe — specifically for the perimeter summation over hull edges.
3. The parallel sort pre-step should use a parallel-friendly approach (e.g., `std::sort` is acceptable; note OMP parallel sort if applicable).
4. Handle edge cases: fewer than 3 points (return 0.0 or the degenerate distance), duplicate points, collinear points.
5. The function must be self-contained — no additional headers beyond what is already included (`<omp.h>`, `<cmath>`, `<vector>`, `<algorithm>`).
6. Must produce output ≈ 13.4477 for input [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}].

Return ONLY the complete function implementation (and any necessary static/inline helpers scoped inside or just before the function). No main(), no test harness.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate a C++ test harness validating correctness and OMP parallelism of the implementation
- **Prompt**: You are writing a C++ test harness for `double convexHullPerimeter(std::vector<Point> const& points)`. Assume the function and its dependencies (Point struct, distance helper) are already defined above your test code.

Write a `main()` that tests:
1. **Canonical example**: [{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}] → expect 13.4477 (tolerance ±0.001).
2. **Triangle**: [{0,0},{4,0},{2,3}] → verify perimeter = sum of three side lengths.
3. **Collinear points**: [{0,0},{1,0},{2,0},{3,0}] → expect perimeter ≈ 6.0 (degenerate hull: line segment doubled) or 0.0 per your edge-case policy — document the expected behavior.
4. **Single/two points**: expect graceful return (0.0), no crash.
5. **Large random set** (n=10000 random points in [0,1000]²): run with `OMP_NUM_THREADS=4` and verify the result matches a serial reference run (compute serially by temporarily disabling OMP with `omp_set_num_threads(1)`).
6. **OMP thread count probe**: assert `omp_get_max_threads() > 0` to confirm OMP linkage.

Use simple `assert`-style checks with printed PASS/FAIL messages. Include `<cassert>`, `<cstdlib>`, `<iostream>`, `<random>`. Output should compile with `g++ -fopenmp -O2`.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the generated code for OMP correctness, race conditions, and performance quality
- **Prompt**: You are performing a focused code review of a C++ OpenMP convex hull perimeter implementation. Review the code generated by code_gen against these criteria:

**Correctness (OMP-specific)**:
- Are all `#pragma omp parallel for` loops free of data races? Check for any shared mutable state inside parallel regions.
- Is the `reduction(+:perimeter)` clause (or equivalent) used correctly for the edge-sum loop?
- Are there any false-sharing risks on the hull vector?
- Is the sort step thread-safe (std::sort on a local copy is fine; verify no shared iterator invalidation).

**Algorithmic correctness**:
- Does the convex hull algorithm correctly handle collinear points (strict vs. non-strict cross product)?
- Is the perimeter loop closed (last hull point back to first)?

**Performance**:
- Is the parallelism applied to the highest-complexity sub-step (sort O(n log n) or the hull walk O(n))?
- Are there unnecessary `omp critical` or `omp ordered` sections that serialize too much?

**Code quality**:
- No memory leaks, appropriate use of `const&`, no unnecessary copies of the points vector.

Output a structured review: list each issue found with severity (CRITICAL / WARNING / SUGGESTION) and a one-line fix recommendation. End with an overall score 1–10 and a go/no-go verdict.
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
