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
- **Time**: 35067ms (35.1s)

## Reasoning
This is a focused HPC code generation task: implement a parallel convex hull perimeter function using MPI+OpenMP. The spec is clear (inputs, output, constraints), so complexity is moderate. The natural decomposition is: plan the parallel strategy (which convex hull algorithm parallelizes well with MPI+OpenMP), implement it, then validate against the provided example. Planner and code_gen are sequential; tester can run independently once code is ready, with a final review pass.

## Pipeline: planner -> code_gen -> tester -> review

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the parallel convex hull algorithm strategy for MPI+OpenMP
- **Prompt**: Design a parallel strategy for computing convex hull perimeter using MPI and OpenMP in C++. Given: every MPI rank has a complete copy of `std::vector<Point> points`. The result must be returned on rank 0. Address the following:
1. Which convex hull algorithm is most suitable for parallelization (e.g., parallel Graham scan, divide-and-conquer, or Andrew's monotone chain)? Justify your choice for MPI+OpenMP.
2. How to divide work across MPI ranks (e.g., partition points by x-range, each rank computes a local hull).
3. How OpenMP threads should be used within each rank (e.g., parallel sort, parallel local hull computation).
4. How to merge local convex hulls from all ranks into a global hull on rank 0 (hull-of-hulls approach).
5. Note the `distance()` and `Point` struct are already defined. MPI_Init has already been called.
Output a concise algorithmic plan with data flow and key MPI calls (MPI_Gather or MPI_Gatherv for hull points).
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement convexHullPerimeter using MPI+OpenMP per the planner's strategy
- **Prompt**: Implement the C++ function `double convexHullPerimeter(std::vector<Point> const& points)` using MPI and OpenMP, following the parallel strategy from the planner.

Constraints and context:
- Headers `<mpi.h>` and `<omp.h>` are already included.
- `struct Point { double x, y; }` and `double distance(Point const&, Point const&)` are already defined.
- MPI has already been initialized. Every rank has a full copy of `points`.
- Return the final perimeter on rank 0; other ranks may return 0.0 or any value.
- Use Andrew's monotone chain algorithm (sort by x then y, compute upper+lower hull) as the base — it is simple to parallelize.

Parallel approach to implement:
1. **OMP parallel sort** within each rank (use `std::sort` with OpenMP if possible, or manually parallel-merge-sort).
2. **MPI domain decomposition**: split sorted points into `nranks` contiguous chunks; each rank computes its local convex hull using Andrew's monotone chain on its chunk.
3. **MPI_Gather** local hull point counts to rank 0, then **MPI_Gatherv** the actual local hull points.
4. Rank 0 runs Andrew's monotone chain on the union of all gathered hull points to get the global hull.
5. Rank 0 computes and returns the perimeter by summing `distance()` between consecutive hull vertices (closing the polygon).

Provide the complete function body. Use `MPI_DOUBLE` for point data (send x and y as a flat double array). Include necessary local variables, MPI calls, and OpenMP pragmas. Verify against example: input `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]` should yield perimeter ≈ 13.4477.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate validation tests and verify the example case output
- **Prompt**: Given the implemented `convexHullPerimeter` function using MPI+OpenMP, generate a set of test cases to validate correctness and robustness.

Required test cases:
1. **Provided example**: `[{0,3},{1,1},{2,2},{4,4},{0,0},{1,2},{3,1},{3,3}]` → expected ≈ 13.4477. Show the expected convex hull vertices in order.
2. **Unit square**: `[{0,0},{1,0},{1,1},{0,1}]` → expected perimeter = 4.0.
3. **Collinear points**: `[{0,0},{1,0},{2,0},{3,0}]` → degenerate hull, perimeter = 6.0 (back and forth).
4. **Single point**: `[{2,3}]` → perimeter = 0.0.
5. **Two points**: `[{0,0},{3,4}]` → perimeter = 10.0 (distance 5, doubled).
6. **Regular triangle**: `[{0,0},{1,0},{0.5, 0.866}]` → perimeter ≈ 3.0.
7. **Large random set correctness**: describe how to cross-validate with a serial reference implementation.

For each test, provide: input, expected output, tolerance (use 1e-4), and what property is being tested. Also list at least 2 edge cases specific to the MPI parallelism (e.g., fewer points than ranks, all points on one rank's domain).
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 4. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Review the implementation for correctness, MPI safety, and HPC best practices
- **Prompt**: Review the MPI+OpenMP implementation of `convexHullPerimeter` for the following criteria:

1. **MPI correctness**: Are MPI_Gather/MPI_Gatherv calls correct? Are counts and displacements computed correctly? Is there a risk of deadlock or unbalanced collective calls?
2. **OpenMP correctness**: Are there data races in the parallel sections? Is the sort parallelized safely?
3. **Edge cases**: Does it handle N < nranks (fewer points than MPI ranks)? Collinear points? Single point?
4. **Hull merge correctness**: Does running Andrew's monotone chain on the union of local hulls always produce the correct global hull? (It should — the global hull vertices are a subset of local hull vertices.)
5. **Performance**: Is the MPI communication volume minimized? Are there unnecessary broadcasts or redundant computation?
6. **Memory**: Are there buffer overflows in the flat double array packing of Point structs?

Provide a quality score (0–10) and a short list of required fixes vs. suggested improvements.
- **Tokens**: 2000 | Compute: light
- **Depends on**: code_gen, tester

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [tester]
- Stage 3: [review]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| review | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| **Total** | | | **8000** | |
