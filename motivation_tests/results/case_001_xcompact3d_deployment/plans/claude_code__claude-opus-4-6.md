---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: 5a6e9e80-fc33-44db-9dc7-7043b77f5873
duration_ms: 347606
duration_wall_s: 364.3
cost_usd: 0.7951644999999999
num_turns: 13
timestamp: 2026-03-18T00:33:37.836713+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment: Multi-Agent Dispatch Plan

## Context

**Goal:** Deploy the XCompact3D (Incompact3d) CFD application on a Slurm-managed HPC cluster, from source acquisition through validated execution.

**Why:** This serves as a concrete case study for the Pythia project, demonstrating how a dispatch planner decomposes a real scientific computing deployment into agent-handled subtasks with explicit resource budgets, dependencies, and parallelism.

**XCompact3D facts:** Fortran-based CFD code, MPI-parallel, built with CMake, depends on MPI + FFTW3 + 2DECOMP&FFT. Runs via `srun ./xcompact3d` with an `input.i3d` configuration file.

---

## Dependency Graph & Parallelism

```
Time -->

 t0                          t1                        t2                          t3
 |                           |                         |                           |
 +-- [S1: Source-Fetch] -----+                         |                           |
 |                           +--> [S2: Build Agent] --+--> [S4: Job-Submission] --+--> [S5: Monitor]
 +-- [S3: Cluster-Probe] ---+                         |                           |
```

- **Parallel at t0:** S1 and S3 (no mutual dependency — launch concurrently)
- **Gate at t1:** S2 requires both S1 (source tree) and S3 (available modules/compilers)
- **Sequential t2-t3:** S4 needs S2 binary; S5 needs S4 job ID

---

## Stage 1: Source Acquisition

| Field | Value |
|---|---|
| **Agent** | Source-Fetch Agent |
| **Hardware** | 1 CPU core, 512 MB RAM, 2 GB disk |
| **Network** | Outbound HTTPS to github.com |
| **Token budget** | ~2,000 tokens |
| **Dependencies** | None (root task) |
| **Outputs** | `$WORK/xcompact3d/` source tree; `source_sha.txt` |

### Commands

```bash
cd "$WORK"
git clone --depth 1 https://github.com/xcompact3d/Incompact3d.git xcompact3d
cd xcompact3d

# Record provenance
git rev-parse HEAD > ../source_sha.txt
git log --oneline -1

# Verify build system entry point
ls CMakeLists.txt
ls -d */ | head -20
```

### Success criteria
- Exit code 0 on `git clone`
- `CMakeLists.txt` exists at repo root
- `source_sha.txt` written

### Failure recovery
- Network failure: retry up to 3 times with 10s backoff
- No `CMakeLists.txt`: escalate `SRC_STRUCTURE_MISMATCH`

---

## Stage 2: Code Understanding & Build

| Field | Value |
|---|---|
| **Agent** | Build Agent |
| **Hardware** | 4 CPU cores, 4 GB RAM, 5 GB disk |
| **Network** | Outbound HTTPS (only if fetching FFTW sources) |
| **Token budget** | ~12,000 tokens |
| **Dependencies** | S1 (source tree), S3 (available modules/compilers) |
| **Outputs** | `$WORK/xcompact3d/build/xcompact3d` binary; `build.log` |

### 2a. Dependency resolution (uses S3 output)

```bash
module purge
module load ${CMAKE_MODULE}      # e.g. cmake/3.24
module load ${COMPILER_MODULE}   # e.g. gcc/12.2.0
module load ${MPI_MODULE}        # e.g. openmpi/4.1.4
module load ${FFTW_MODULE}       # e.g. fftw/3.3.10

which mpifort || which mpif90
mpifort --version
cmake --version
```

### 2b. Read & understand CMake configuration

Agent reads these files to determine build options:
- `$WORK/xcompact3d/CMakeLists.txt` — top-level project definition, option flags
- `$WORK/xcompact3d/cmake/` — custom Find modules (FindFFTW, Find2DECOMP)
- `$WORK/xcompact3d/src/` — Fortran source structure

Key options to identify: `BUILD_TESTING`, 2DECOMP&FFT mode (bundled vs system), precision.

### 2c. Configure and compile

```bash
cd "$WORK/xcompact3d"
mkdir -p build && cd build

cmake .. \
  -DCMAKE_Fortran_COMPILER=mpifort \
  -DCMAKE_BUILD_TYPE=Release \
  -DFFTW_ROOT="$FFTW_DIR" \
  2>&1 | tee cmake_configure.log

[ $? -ne 0 ] && echo "STAGE2_CMAKE_FAIL" && exit 1

make -j4 2>&1 | tee build.log
```

### 2d. Verify binary

```bash
file xcompact3d
ldd xcompact3d | grep -i mpi
ldd xcompact3d | grep -i fftw
```

### Success criteria
- `cmake` configures without error; `make` exit code 0
- Binary links to MPI and FFTW

### Failure recovery
- FFTW not found: set `-DFFTW_ROOT` or build from source
- Compiler errors: switch module combination (gcc ↔ intel)
- 2DECOMP&FFT fails: enable bundled build via cmake flag

---

## Stage 3: Cluster Resource Discovery

| Field | Value |
|---|---|
| **Agent** | Cluster-Probe Agent |
| **Hardware** | 1 CPU core, 256 MB RAM |
| **Network** | None (local Slurm commands) |
| **Token budget** | ~5,000 tokens |
| **Dependencies** | None (root task) |
| **Outputs** | Resource manifest consumed by S2 and S4 |

### Commands

```bash
# Partition and node summary
sinfo --format="%P %a %l %D %c %m %G %f" --noheader

# Detailed node inspection
SAMPLE_NODE=$(sinfo -N --noheader | head -1 | awk '{print $1}')
scontrol show node "$SAMPLE_NODE"

# Partitions with time limits
sinfo -o "%P %l %D %c %m" --noheader

# Queue occupancy
squeue --format="%P %T" --noheader | sort | uniq -c | sort -rn | head -10

# Available software modules
module avail 2>&1 | grep -i -E "cmake|gcc|intel|openmpi|mpich|fftw|fortran"

# Network topology
scontrol show topology 2>/dev/null || echo "NO_TOPOLOGY_INFO"

# Account and QOS limits
sacctmgr show assoc user="$USER" format=Account,Partition,MaxJobs,MaxSubmit,GrpTRES --noheader 2>/dev/null

# GPU availability
sinfo -o "%P %G" --noheader | grep -v "(null)" | head -10
```

### Output manifest

```
cluster_name:       <from hostname or scontrol show config>
best_partition:     <partition with most idle nodes, reasonable time limit>
cores_per_node:     <integer>
memory_per_node_gb: <integer>
nodes_available:    <integer>
max_walltime:       <HH:MM:SS>
mpi_module:         <e.g. openmpi/4.1.4>
compiler_module:    <e.g. gcc/12.2.0>
fftw_module:        <e.g. fftw/3.3.10 or NOT_FOUND>
cmake_module:       <e.g. cmake/3.24>
interconnect:       <e.g. InfiniBand HDR or UNKNOWN>
```

### Success criteria
- `sinfo` returns ≥1 available partition
- MPI module and Fortran compiler found
- `cores_per_node` is a positive integer

---

## Stage 4: Job Submission

| Field | Value |
|---|---|
| **Agent** | Job-Submission Agent |
| **Hardware** | 1 CPU core, 256 MB RAM |
| **Network** | None |
| **Token budget** | ~6,000 tokens |
| **Dependencies** | S2 (binary), S3 (resource manifest) |
| **Outputs** | `$WORK/xcompact3d/run/job.slurm`; job ID in `job_id.txt` |

### 4a. Prepare run directory

```bash
mkdir -p "$WORK/xcompact3d/run"
cd "$WORK/xcompact3d/run"
cp "$WORK/xcompact3d/build/xcompact3d" .

# Find and copy example input (e.g. Taylor-Green Vortex)
find "$WORK/xcompact3d" -name "*.i3d" | head -5
cp "$WORK/xcompact3d/examples/TGV-Taylor-Green-Vortex/input.i3d" . 2>/dev/null \
  || cp "$WORK/xcompact3d/input.i3d" .
```

### 4b. Slurm batch script (`job.slurm`)

```bash
#!/bin/bash
#SBATCH --job-name=xc3d_tgv
#SBATCH --partition=${BEST_PARTITION}
#SBATCH --nodes=${NUM_NODES}
#SBATCH --ntasks-per-node=${CORES_PER_NODE}
#SBATCH --time=${WALLTIME}
#SBATCH --output=xc3d_%j.out
#SBATCH --error=xc3d_%j.err
#SBATCH --exclusive

module purge
module load ${CMAKE_MODULE}
module load ${COMPILER_MODULE}
module load ${MPI_MODULE}
module load ${FFTW_MODULE}

echo "Job ID:     $SLURM_JOB_ID"
echo "Nodes:      $SLURM_JOB_NODELIST"
echo "Tasks:      $SLURM_NTASKS"
echo "Start:      $(date -u +%Y-%m-%dT%H:%M:%SZ)"
hostname

export OMP_NUM_THREADS=1

cd $SLURM_SUBMIT_DIR
srun ./xcompact3d

echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

**Default parameters (2-node TGV test):**

| Parameter | Default | Rationale |
|---|---|---|
| `NUM_NODES` | 2 | Small validation run |
| `CORES_PER_NODE` | from S3 manifest | Fill nodes for MPI |
| `WALLTIME` | 00:30:00 | TGV converges quickly |

### 4c. Submit

```bash
cd "$WORK/xcompact3d/run"
JOB_ID=$(sbatch --parsable job.slurm)
echo "Submitted job: $JOB_ID"
echo "$JOB_ID" > job_id.txt
```

### Success criteria
- `sbatch` returns a numeric job ID
- `squeue -j $JOB_ID` shows PD or R state

---

## Stage 5: Monitoring & Validation

| Field | Value |
|---|---|
| **Agent** | Monitor Agent |
| **Hardware** | 1 CPU core, 256 MB RAM |
| **Network** | None |
| **Token budget** | ~8,000 tokens |
| **Dependencies** | S4 (job ID) |
| **Outputs** | Validation report (pass/fail, metrics, errors) |

### 5a. Poll job status

```bash
JOB_ID=$(cat "$WORK/xcompact3d/run/job_id.txt")

for i in $(seq 1 120); do
  STATE=$(squeue -j "$JOB_ID" -h -o "%T" 2>/dev/null)
  if [ -z "$STATE" ]; then
    echo "Job completed -- checking sacct"
    sacct -j "$JOB_ID" --format=JobID,State,ExitCode,Elapsed,MaxRSS,NCPUS --noheader
    break
  fi
  echo "$(date +%H:%M:%S) Job $JOB_ID state: $STATE"
  sleep 30
done
```

### 5b. Check exit status

```bash
JOB_STATE=$(sacct -j "$JOB_ID" --format=State --noheader | head -1 | tr -d ' ')
EXIT_CODE=$(sacct -j "$JOB_ID" --format=ExitCode --noheader | head -1 | tr -d ' ')
echo "Final state: $JOB_STATE  Exit code: $EXIT_CODE"
```

### 5c. Validate output logs

```bash
cd "$WORK/xcompact3d/run"

tail -100 xc3d_${JOB_ID}.out
wc -l xc3d_${JOB_ID}.err
cat xc3d_${JOB_ID}.err

# XCompact3D-specific checks
grep -c "Time step" xc3d_${JOB_ID}.out
grep -i -E "error|segfault|signal|abort|killed|oom" xc3d_${JOB_ID}.out xc3d_${JOB_ID}.err
grep -i -E "simulation completed|end of simulation|final" xc3d_${JOB_ID}.out
```

### 5d. Collect performance metrics

```bash
sacct -j "$JOB_ID" --format=Elapsed,MaxRSS,AveRSS,NCPUS,NNodes --noheader
find "$WORK/xcompact3d/run" -name "*.bin" -o -name "*.dat" | wc -l
```

### Validation report

```
job_id:           <integer>
final_state:      COMPLETED | FAILED | TIMEOUT | OOM
exit_code:        0:0 (success) or N:M (failure)
wall_time:        HH:MM:SS
num_timesteps:    <count of "Time step" lines>
errors_detected:  <count>
output_files:     <count>
verdict:          PASS | FAIL
failure_reason:   <only if FAIL>
```

### Success criteria
- `COMPLETED` with exit code `0:0`
- ≥1 "Time step" line in stdout
- Zero error/segfault/abort matches
- ≥1 output data file produced

### Failure recovery
- TIMEOUT → increase `--time`, resubmit (back to S4)
- OOM → reduce `ntasks-per-node` or use high-memory partition
- Segfault → compiler/MPI mismatch, return to S2 with different modules

---

## Token Budget Summary

| Stage | Agent | Tokens | Can Parallel With |
|---|---|---|---|
| S1 | Source-Fetch | ~2,000 | S3 |
| S2 | Build | ~12,000 | — |
| S3 | Cluster-Probe | ~5,000 | S1 |
| S4 | Job-Submission | ~6,000 | — |
| S5 | Monitor | ~8,000 | — |
| **Total** | | **~33,000** | |

**Critical path:** max(S1, S3) + S2 + S4 + S5 = 5k + 12k + 6k + 8k = **~31,000 tokens**

---

## Inter-Agent Data Flow

| Producer | Consumer | Artifact |
|---|---|---|
| S1 | S2 | `$WORK/xcompact3d/` source tree, `source_sha.txt` |
| S3 | S2 | Resource manifest (modules, compilers) |
| S3 | S4 | Resource manifest (partition, cores, walltime) |
| S2 | S4 | `$WORK/xcompact3d/build/xcompact3d` binary |
| S4 | S5 | `$WORK/xcompact3d/run/job_id.txt` |

## Error Escalation Protocol

Each agent returns: `COMPLETED`, `RETRY(reason)`, or `FAIL(code, log_path)`.
Max retries per stage: 3. After 3 failures → `PIPELINE_FAIL`.

## Environment Contract

```bash
WORK=/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir
```

All agents share this `$WORK` root. All paths are relative to it.

---

## Verification

1. **S1:** Confirm `$WORK/xcompact3d/CMakeLists.txt` exists and `source_sha.txt` is non-empty
2. **S2:** Run `file $WORK/xcompact3d/build/xcompact3d` and `ldd` to confirm MPI/FFTW linkage
3. **S3:** Verify manifest has non-empty values for partition, cores, modules
4. **S4:** `squeue -j $(cat job_id.txt)` shows PD or R
5. **S5:** Validation report shows `verdict: PASS`

