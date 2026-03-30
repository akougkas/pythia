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
- **Mode**: 2
- **Confidence**: 0.750

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using OpenMP. The complexity is moderate — convex hull algorithms (e.g. Graham scan or Jarvis march) are well-defined, but parallelizing with OpenMP requires care around the hull construction stage (inherently sequential) vs. parallelizable preprocessing (e.g. finding extremes, distance computations). Decomposability is low (0.35), so a lean 2-agent pipeline (planner → code_gen) is appropriate, with no parallel stages needed.

## Pipeline: planner -> code_gen

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Select and outline an OpenMP-friendly convex hull algorithm strategy
- **Prompt**: You are planning the implementation of `convexHullPerimeter` in C++ with OpenMP. The function takes a `std::vector<Point>` and returns the perimeter of the convex hull as a `double`. Analyze the following and produce a concise algorithm plan:
1. Choose an appropriate convex hull algorithm (e.g. Graham scan, Andrew's monotone chain, Jarvis march) — justify which is most amenable to OpenMP parallelism.
2. Identify which steps can be parallelized with OpenMP (e.g. finding min/max points via `#pragma omp parallel for reduction`, distance accumulation) vs. which must remain sequential (hull construction ordering).
3. Note any race conditions or shared-state issues to avoid.
4. Specify how the final perimeter summation over hull edges should be done (sequential loop or parallel reduction).
Output a bullet-point plan (no code), referencing specific OpenMP directives to use at each step.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the parallel convexHullPerimeter function in C++ using OpenMP per the plan
- **Prompt**: Implement the C++ function `convexHullPerimeter` using the algorithm plan provided by the planner. Requirements:
- Signature: `double convexHullPerimeter(std::vector<Point> const& points)`
- Use `#include <omp.h>`, `#include <cmath>`, `#include <vector>`, `#include <algorithm>` as needed
- The `Point` struct and `distance()` function are already defined as:
  cpp
  struct Point { double x, y; };
  double distance(Point const& p1, Point const& p2) { return std::sqrt(std::pow(p2.x-p1.x,2)+std::pow(p2.y-p1.y,2)); }
  
- Use Andrew's Monotone Chain algorithm (O(n log n)) as the hull construction method — it is cache-friendly and its pre-sort + linear scan structure isolates the parallelizable portions cleanly
- Parallelize ONLY safe stages with OpenMP: use `#pragma omp parallel for reduction(min:...) reduction(max:...)` for finding bounding extremes if used, and consider a parallel sort hint; keep the hull-building linear scan sequential to preserve ordering correctness
- After hull construction, compute the perimeter by summing `distance(hull[i], hull[(i+1)%hull.size()])` — this summation loop may use `#pragma omp parallel for reduction(+:perimeter)`
- Handle edge cases: fewer than 3 points (return 0.0 or segment length), collinear points
- Verify mentally against the provided example: input `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]` → expected output `13.4477`
- Return only the completed function body (and any necessary helper lambdas inline), no main(), no test harness
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| **Total** | | | **4500** | |
