---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: b6768d95-b874-4900-b1d7-fe8123d59651
duration_ms: 223633
duration_wall_s: 229.8
cost_usd: 0.49740475
num_turns: 10
timestamp: 2026-03-19T13:41:52.796373+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment Plan
**Case:** `case_001_xcompact3d_deployment`
**Working Directory:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`
**Date:** 2026-03-19
**Objective:** Deploy XCompact3D (Incompact3d) on a Slurm-managed HPC cluster, covering source acquisition, build, cluster profiling, job submission, and validation.

---

## Context

XCompact3D (repo: `https://github.com/xcompact3d/Incompact3d`) is a high-order Fortran-based CFD solver for Direct Numerical Simulation (DNS) of turbulent flows. It relies on MPI domain decomposition (via the `2decomp-fft` submodule), FFTW3 for spectral transforms, and optionally HDF5/ADIOS2 for I/O. Deployment on an HPC cluster requires coordinating source acquisition, dependency installation, CMake-based compilation, Slurm resource discovery, job script authoring, submission, and runtime validation — several of which can be parallelised.

**Key assumptions (stated explicitly):**
- The target cluster uses **Linux**, **Environment Modules** (`module` command), and a **Slurm** scheduler.
- Available compilers include either **GCC ≥ 9** + **OpenMPI ≥ 4** or **Intel oneAPI** (ifort/ifx + Intel MPI).
- FFTW3 and HDF5 are available as modules (or will be installed into a user prefix).
- The user runs a **Taylor-Green Vortex (TGV)** benchmark case as the validation workload (example ships with the repo).
- Internet access is available on login nodes for cloning from GitHub.

---

## Agent Roster

| Agent ID | Specialist Role | Description |
|----------|----------------|-------------|
| `A1` | **Source Acquisition Agent** | Downloads source code and all dependencies |
| `A2` | **Code Intelligence Agent** | Reads and documents the source; produces build recipe |
| `A3` | **Dependency & Build Agent** | Installs libraries and compiles XCompact3D |
| `A4` | **Cluster Topology Agent** | Queries Slurm for nodes, partitions, GPUs, network |
| `A5` | **Job Authoring Agent** | Writes and submits the Slurm batch script |
| `A6` | **Monitoring & Validation Agent** | Checks job status, reads logs, validates output |

---

## Execution DAG

```
A1 (source) ──┐
              ├──► A2 (read code) ──► A3 (build) ──┐
              │                                      ├──► A5 (submit) ──► A6 (validate)
A4 (cluster) ─────────────────────────────────────--┘
```

**Parallel opportunities:**
- `A1` and `A4` run **in parallel** (no mutual dependency).
- `A2` starts after `A1` completes.
- `A3` starts after `A2` completes (needs the build recipe) — `A4` can still run concurrently.
- `A5` starts only after **both** `A3` (binary ready) and `A4` (resource info known) finish.
- `A6` starts after `A5` (job has been submitted).

---

## Stage 1 — Source Code Acquisition (`A1`)

**Agent:** Source Acquisition Agent (`A1`)
**Depends on:** None (can start immediately)
**Parallelisable with:** `A4`
**Hardware resources:** Login node CPU, 1 core, ~2 GB RAM, network I/O
**Expected tokens:** ~8,000

### Commands

```bash
# 1. Navigate to the working directory
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

# 2. Clone the upstream repository (shallow clone to save bandwidth, then fetch full if needed)
git clone --recurse-submodules https://github.com/xcompact3d/Incompact3d.git xcompact3d
cd xcompact3d

# If submodules were not fetched automatically (e.g., older git):
git submodule update --init --recursive

# 3. Confirm what submodules were fetched
git submodule status
# Expected output includes:  decomp2d/  (the 2decomp-fft domain-decomposition library)

# 4. Inspect top-level directory structure
ls -lh
# Expected: CMakeLists.txt  src/  examples/  docs/  decomp2d/  ...

# 5. Capture the exact commit hash for reproducibility
git rev-parse HEAD > ../SOURCE_REVISION.txt
git submodule foreach --recursive 'git rev-parse HEAD' >> ../SOURCE_REVISION.txt
cat ../SOURCE_REVISION.txt
```

**Deliverable:** Directory `WorkingDir/xcompact3d/` fully populated with source and submodule `decomp2d/`.

---

## Stage 2 — Source Code Reading & Build Recipe (`A2`)

**Agent:** Code Intelligence Agent (`A2`)
**Depends on:** `A1` (source must exist)
**Parallelisable with:** `A4`
**Hardware resources:** Login node CPU, 1 core, ~2 GB RAM
**Expected tokens:** ~25,000 (reads multiple Fortran source files, CMakeLists, docs)

### Tasks

1. Read and summarise `CMakeLists.txt` (top-level and `decomp2d/CMakeLists.txt`).
2. Read `src/xcompact3d.f90` and key modules (`src/module_param.f90`, `src/BC-*.f90`).
3. Read `examples/Taylor-Green-Vortex/input.i3d` for input file format.
4. Read `docs/` for any installation guides.
5. Produce the **build recipe** (CMake flags, module loads).

### Key Commands to Document

```bash
# Inspect CMake options
cd WorkingDir/xcompact3d
grep -E "option\(|set\(CMAKE" CMakeLists.txt | head -60

# Read the top-level CMakeLists for required packages
cat CMakeLists.txt

# Read the 2decomp-fft submodule CMakeLists
cat decomp2d/CMakeLists.txt

# Inspect example input file
cat examples/Taylor-Green-Vortex/input.i3d

# Identify Fortran source entry point
head -100 src/xcompact3d.f90
```

**Deliverable:** A structured build recipe document `WorkingDir/BUILD_RECIPE.md` containing:
- Required modules to load
- CMake configure command with all flags
- `make` invocation
- Run command syntax

---

## Stage 3 — Dependency Installation & Compilation (`A3`)

**Agent:** Dependency & Build Agent (`A3`)
**Depends on:** `A2` (build recipe)
**Parallelisable with:** `A4`
**Hardware resources:** Login or compile node, 8–16 cores (for parallel make), ~8 GB RAM
**Expected tokens:** ~15,000

### 3a. Load Environment Modules

```bash
# List available modules to identify compiler and MPI stacks
module avail 2>&1 | grep -iE "gcc|intel|openmpi|mpich|fftw|hdf5|cmake"

# --- Option A: GCC + OpenMPI stack ---
module purge
module load gcc/12.3.0          # or latest available
module load openmpi/4.1.5       # MPI implementation
module load fftw/3.3.10         # FFTW3 (double precision)
module load hdf5/1.14.0         # HDF5 parallel build (optional but recommended)
module load cmake/3.26.0        # CMake >= 3.14 required

# --- Option B: Intel oneAPI stack ---
# module purge
# module load intel-oneapi-compilers/2024.0
# module load intel-oneapi-mpi/2021.11
# module load fftw/3.3.10-intel
# module load hdf5/1.14.0-intel
# module load cmake/3.26.0

# Verify compiler and MPI wrappers are reachable
which mpif90 && mpif90 --version
which mpicc  && mpicc  --version
cmake --version
```

### 3b. Install FFTW3 from Source (if not available as module)

```bash
# Only required if no fftw module exists on the cluster
FFTW_VERSION=3.3.10
FFTW_PREFIX=$HOME/local/fftw3

wget https://fftw.org/fftw-${FFTW_VERSION}.tar.gz
tar -xzf fftw-${FFTW_VERSION}.tar.gz
cd fftw-${FFTW_VERSION}

./configure --prefix=${FFTW_PREFIX} \
            --enable-mpi \
            --enable-openmp \
            --enable-shared \
            --enable-double \
            F77=mpif90 CC=mpicc

make -j 8
make install
cd ..

export FFTW_ROOT=${FFTW_PREFIX}
```

### 3c. Install HDF5 from Source (if not available as module)

```bash
# Only required if no hdf5 module exists
HDF5_VERSION=1.14.3
HDF5_PREFIX=$HOME/local/hdf5

wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-1.14/hdf5-${HDF5_VERSION}/src/hdf5-${HDF5_VERSION}.tar.gz
tar -xzf hdf5-${HDF5_VERSION}.tar.gz
cd hdf5-${HDF5_VERSION}

./configure --prefix=${HDF5_PREFIX} \
            --enable-parallel \
            --enable-fortran \
            CC=mpicc FC=mpif90

make -j 8
make install
cd ..

export HDF5_ROOT=${HDF5_PREFIX}
```

### 3d. Configure XCompact3D with CMake

```bash
cd WorkingDir/xcompact3d
mkdir -p build && cd build

# Core CMake configure command
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_Fortran_COMPILER=mpif90 \
  -DCMAKE_C_COMPILER=mpicc \
  -DFFTW_ROOT=${FFTW_ROOT:-$(dirname $(dirname $(which fftw-wisdom)))} \
  -DHDF5_ROOT=${HDF5_ROOT:-$(h5pcc -show 2>/dev/null | awk '{print $1}' | sed 's|/bin/h5pcc||')} \
  -DDOUBLE_PREC=ON \
  -DSAVE_SNAPSHOT=ON \
  2>&1 | tee cmake_configure.log

# Inspect what CMake found
cat cmake_configure.log | grep -E "Found|ERROR|Warning|FFTW|HDF5|MPI"
```

**Common CMake options for XCompact3D:**

| CMake Flag | Description | Recommended Value |
|---|---|---|
| `CMAKE_BUILD_TYPE` | Optimisation level | `Release` |
| `DOUBLE_PREC` | Double-precision arithmetic | `ON` |
| `FFTW_ROOT` | Path to FFTW3 installation | module path |
| `HDF5_ROOT` | Path to parallel HDF5 | module path |
| `SAVE_SNAPSHOT` | Enable checkpoint/restart | `ON` |
| `USE_COLOR` | Coloured terminal output | `OFF` (batch) |

### 3e. Compile

```bash
# Build with all available cores on the compile node
make -j $(nproc) 2>&1 | tee build.log

# Check the binary was produced
ls -lh bin/xcompact3d
file bin/xcompact3d
# Expected: ELF 64-bit LSB executable, x86-64, dynamically linked

# Verify it links against MPI and FFTW
ldd bin/xcompact3d | grep -E "mpi|fftw|hdf5"
```

**Deliverable:** `WorkingDir/xcompact3d/build/bin/xcompact3d` executable.

---

## Stage 4 — Cluster Topology Discovery (`A4`)

**Agent:** Cluster Topology Agent (`A4`)
**Depends on:** None (can start immediately, runs in parallel with `A1`–`A3`)
**Parallelisable with:** `A1`, `A2`, `A3`
**Hardware resources:** Login node CPU, 1 core, negligible RAM
**Expected tokens:** ~10,000

### 4a. Query Partitions and Node Availability

```bash
# Summary of all partitions and their state
sinfo -o "%P %a %l %D %T %N" | column -t

# Detailed partition info including max CPUs, memory, GPU
sinfo -o "%20P %5a %10l %6D %6t %8c %8m %25f %N" | column -t

# Show all nodes with their resources in long format
sinfo -N -l

# Show only idle or mix nodes (suitable for immediate job)
sinfo -t idle,mix -o "%20N %8c %8m %25f %G %P" | column -t
```

### 4b. Query Individual Node Details

```bash
# Get full details for a specific node (replace 'node001' with actual name)
scontrol show node node001

# Key fields to note:
#   CfgTRES=cpu=48,mem=192G,billing=48
#   Gres=gpu:a100:4   (or similar GPU spec)
#   OS=Linux 5.15.0
#   NodeAddr, NodeHostName

# Query all nodes matching a feature (e.g., infiniband, gpu)
scontrol show nodes | grep -E "NodeName|CfgTRES|Gres|Features|NetWork" | paste - - - - -

# List all nodes with GPU resources
sinfo -o "%N %G" | grep -v "null" | grep gpu
```

### 4c. Query GPU Resources

```bash
# Show GPU availability per partition
sinfo -o "%P %G %D %N" | grep -v "null"

# GRES (Generic Resource) details for GPU nodes
scontrol show nodes | grep -A2 "Gres=gpu"

# If DCGM or nvidia-smi is available via an interactive job:
srun --partition=gpu --gres=gpu:1 --pty nvidia-smi
```

### 4d. Query Network Topology (InfiniBand / Omni-Path)

```bash
# Slurm topology plugin info
scontrol show topology 2>/dev/null || echo "Topology plugin not configured"

# Network switch groupings
sinfo -o "%N %e" --Node | head -20

# If ibutils/rdma-core available on login node:
ibstat 2>/dev/null | grep -E "State|Rate|Link"

# Check node features for network type
scontrol show nodes | grep Features | sort -u | head -20
```

### 4e. Query Scheduler Limits & Account

```bash
# Show your Slurm account(s) and QOS limits
sacctmgr show user $(whoami) withassoc format=User,Account,Partition,QOS -P

# Show QOS limits (max wall time, max jobs, etc.)
sacctmgr show qos format=Name,MaxWall,MaxTRES,GrpTRES -P

# Check current queue state
squeue -u $(whoami) -o "%i %j %P %T %M %l %D %R" | column -t

# Pending/running jobs for the partitions of interest
squeue -p <partition_name> --state=RUNNING -o "%i %j %u %P %T %M %l %D %C %R" | column -t
```

**Deliverable:** A file `WorkingDir/CLUSTER_PROFILE.txt` containing:
- List of partitions and their limits
- GPU nodes and GPU type/count
- Network interconnect type and bandwidth
- Account/QOS limits (max walltime, max cores)
- Recommended partition and node count for the TGV benchmark

---

## Stage 5 — Slurm Batch Script & Job Submission (`A5`)

**Agent:** Job Authoring Agent (`A5`)
**Depends on:** `A3` (binary exists) **AND** `A4` (cluster profile known)
**Hardware resources:** Login node CPU, 1 core, negligible RAM
**Expected tokens:** ~12,000

### 5a. Prepare the Input File

```bash
cd WorkingDir/xcompact3d

# Copy the Taylor-Green Vortex example input
mkdir -p run/tgv_benchmark
cp examples/Taylor-Green-Vortex/input.i3d run/tgv_benchmark/
cp build/bin/xcompact3d run/tgv_benchmark/

# Review / customise the input file
cat run/tgv_benchmark/input.i3d
```

**Key parameters in `input.i3d` to adjust:**

```fortran
&BasicParam
 nx = 256, ny = 256, nz = 256   ! Grid resolution (must be factors of 2decomp decomposition)
 xlx = 2*pi, yly = 2*pi, zlz = 2*pi  ! Domain size
 nclx1 = 0, nclxn = 0           ! Boundary conditions (0=periodic)
 ncly1 = 0, nclyn = 0
 nclz1 = 0, nclzn = 0
 itype = 2                       ! Flow type (2 = Taylor-Green Vortex)
 iin = 1                         ! Initial condition flag
 re = 1600.0                     ! Reynolds number
 dt = 0.002                      ! Time step
 ifirst = 1, ilast = 2000        ! Time step range
 ioutput = 100                   ! Output frequency
/
&NumOptions
 p_row = 0, p_col = 0            ! 2D decomposition (0,0 = auto-detect)
 ilesmodel = 0                   ! 0 = DNS, 1 = LES
/
```

> **Note:** `p_row` and `p_col` define the 2D MPI decomposition grid. Setting both to 0 lets 2decomp-fft auto-select. For `N` MPI ranks, common layouts are powers of 2 (e.g., 8×4, 16×8, 32×16). Ensure `nx`, `ny`, `nz` are divisible by the chosen decomposition.

### 5b. Slurm Batch Script

Save as `WorkingDir/xcompact3d/run/tgv_benchmark/submit_tgv.sh`:

```bash
#!/bin/bash
#------------------------------------------------------------
# XCompact3D – Taylor-Green Vortex Benchmark
# Cluster:  <CLUSTER_NAME>
# Partition: cpu (or gpu — adjust per CLUSTER_PROFILE.txt)
#------------------------------------------------------------

#SBATCH --job-name=xc3d_tgv
#SBATCH --output=logs/xc3d_tgv_%j.out
#SBATCH --error=logs/xc3d_tgv_%j.err
#SBATCH --partition=cpu                    # <-- from CLUSTER_PROFILE.txt
#SBATCH --nodes=4                          # <-- 4 nodes × 32 MPI ranks = 128 total
#SBATCH --ntasks-per-node=32              # <-- match physical cores per node
#SBATCH --cpus-per-task=1                 # <-- 1 thread per MPI rank (pure MPI)
#SBATCH --mem=64G                         # <-- memory per node (check cluster max)
#SBATCH --time=02:00:00                   # <-- walltime HH:MM:SS
#SBATCH --account=<YOUR_ACCOUNT>          # <-- from sacctmgr output
#SBATCH --qos=<YOUR_QOS>                  # <-- from sacctmgr output
##SBATCH --constraint=infiniband          # <-- uncomment if InfiniBand required
##SBATCH --exclusive                      # <-- uncomment for dedicated nodes

# Optional: GPU partition example (uncomment if using GPU-accelerated build)
##SBATCH --partition=gpu
##SBATCH --gres=gpu:a100:4
##SBATCH --ntasks-per-node=4

#------------------------------------------------------------
# Environment setup
#------------------------------------------------------------
echo "===== JOB ENVIRONMENT ====="
echo "Job ID       : $SLURM_JOB_ID"
echo "Node list    : $SLURM_JOB_NODELIST"
echo "Num nodes    : $SLURM_NNODES"
echo "Tasks/node   : $SLURM_NTASKS_PER_NODE"
echo "Total tasks  : $SLURM_NTASKS"
echo "Working dir  : $SLURM_SUBMIT_DIR"
echo "Start time   : $(date)"
echo "==========================="

# Reproduce the exact module environment used at build time
module purge
module load gcc/12.3.0
module load openmpi/4.1.5
module load fftw/3.3.10
module load hdf5/1.14.0
# Add user-installed libraries if needed:
# export LD_LIBRARY_PATH=$HOME/local/fftw3/lib:$HOME/local/hdf5/lib:$LD_LIBRARY_PATH

#------------------------------------------------------------
# Change to run directory
#------------------------------------------------------------
cd $SLURM_SUBMIT_DIR
mkdir -p logs

# Verify binary is present and executable
if [ ! -x ./xcompact3d ]; then
    echo "ERROR: xcompact3d binary not found or not executable" >&2
    exit 1
fi

# Verify input file is present
if [ ! -f ./input.i3d ]; then
    echo "ERROR: input.i3d not found" >&2
    exit 1
fi

echo "Binary:    $(ls -lh xcompact3d)"
echo "Input:     $(ls -lh input.i3d)"
echo "MPI ranks: $SLURM_NTASKS"

#------------------------------------------------------------
# Run XCompact3D
#------------------------------------------------------------
echo "===== STARTING SIMULATION ====="

srun --mpi=pmix \
     --ntasks=$SLURM_NTASKS \
     --ntasks-per-node=$SLURM_NTASKS_PER_NODE \
     ./xcompact3d input.i3d \
     2>&1 | tee logs/xc3d_stdout_${SLURM_JOB_ID}.log

EXIT_CODE=$?

echo "===== SIMULATION FINISHED ====="
echo "End time  : $(date)"
echo "Exit code : $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: xcompact3d exited with non-zero status $EXIT_CODE" >&2
fi

exit $EXIT_CODE
```

### 5c. Submit the Job

```bash
cd WorkingDir/xcompact3d/run/tgv_benchmark

# Dry-run: validate the script without submitting
sbatch --test-only submit_tgv.sh

# Actual submission
sbatch submit_tgv.sh
# Output: Submitted batch job 12345678   <-- record the JOB_ID

# Save the job ID to a file for reference
sbatch submit_tgv.sh | tee JOBID.txt
JOB_ID=$(cat JOBID.txt | awk '{print $NF}')
echo "Job submitted: $JOB_ID"
```

**Deliverable:** Job submitted; `$JOB_ID` recorded in `JOBID.txt`.

---

## Stage 6 — Job Monitoring & Validation (`A6`)

**Agent:** Monitoring & Validation Agent (`A6`)
**Depends on:** `A5` (job must be submitted)
**Hardware resources:** Login node CPU, 1 core, negligible RAM
**Expected tokens:** ~10,000

### 6a. Check Job Status

```bash
JOB_ID=$(cat WorkingDir/xcompact3d/run/tgv_benchmark/JOBID.txt | awk '{print $NF}')

# Real-time job status
squeue -j $JOB_ID -o "%i %j %u %P %T %M %l %D %R" | column -t

# Detailed job info (shows start time, allocated nodes, reason if pending)
scontrol show job $JOB_ID

# Watch status every 30 seconds (press Ctrl-C to stop)
watch -n 30 "squeue -j $JOB_ID -o '%i %j %P %T %M %l %D %R' | column -t"

# Job state transitions to monitor:
#   PENDING  → waiting in queue
#   RUNNING  → executing
#   COMPLETED → success
#   FAILED   → non-zero exit
#   CANCELLED → user/admin cancelled
#   TIMEOUT  → exceeded walltime
```

### 6b. Read Logs During and After Execution

```bash
cd WorkingDir/xcompact3d/run/tgv_benchmark

# Tail the SLURM stdout log in real time
tail -f logs/xc3d_tgv_${JOB_ID}.out

# Tail the SLURM stderr log
tail -f logs/xc3d_tgv_${JOB_ID}.err

# After completion: view full output
cat logs/xc3d_tgv_${JOB_ID}.out | head -100

# Check for common XCompact3D startup messages:
#   - "Decomposition layout" (from 2decomp-fft)
#   - "Reynolds number"
#   - "Time step" counter lines
grep -E "decomp|Reynolds|Time-step|ERROR|WARNING|STOP" logs/xc3d_tgv_${JOB_ID}.out | head -50
```

### 6c. Validate Correct Application Startup

```bash
# 1. Confirm the MPI decomposition was reported
grep -i "decomp\|p_row\|p_col" logs/xc3d_tgv_${JOB_ID}.out | head -10

# 2. Confirm Reynolds number and grid were read correctly
grep -E "Re =|nx =|ny =|nz =" logs/xc3d_tgv_${JOB_ID}.out | head -10

# 3. Check time-stepping has begun (at least step 1 completed)
grep -E "Time-step|it =|step" logs/xc3d_tgv_${JOB_ID}.out | head -20

# 4. Check output files were written
ls -lh *.h5 2>/dev/null || ls -lh *.dat 2>/dev/null || ls -lh data/ 2>/dev/null
# HDF5 output files (snapshot_XXXXXXXX.h5) should appear at ioutput intervals

# 5. Check performance metrics (if printed by XCompact3D)
grep -iE "wall.?time|time/step|Mflop|seconds" logs/xc3d_tgv_${JOB_ID}.out | tail -20

# 6. Verify job accounting after completion
sacct -j $JOB_ID \
      --format=JobID,JobName,Partition,AllocCPUS,State,ExitCode,Elapsed,MaxRSS \
      --units=G

# 7. Check final exit code
sacct -j $JOB_ID --format=State,ExitCode --noheader
# Target: State=COMPLETED, ExitCode=0:0
```

### 6d. Diagnostics for Common Failures

| Symptom | Likely Cause | Diagnostic Command |
|---|---|---|
| Job stuck `PENDING` | No free nodes, insufficient resources | `squeue -j $JOB_ID -o "%R"` (shows reason) |
| `FAILED` exit code | Segfault, input error, OOM | `cat logs/xc3d_tgv_${JOB_ID}.err` |
| `ERROR: MPI_Init` | Module mismatch build vs run | `ldd xcompact3d` vs `module list` |
| `FFTW: plan failed` | FFTW not found or wrong precision | `ldd xcompact3d \| grep fftw` |
| `Segmentation fault` | Grid too large for memory | Reduce `nx,ny,nz` or add more nodes |
| `TIMEOUT` | Simulation too long | Reduce `ilast` or request more walltime |
| Empty output files | Wrong `ioutput` or path issue | Check `input.i3d` `ioutput` & write permissions |

---

## Summary: Agent Schedule & Resource Table

| Agent | Stage | Depends On | Parallel With | CPU Cores | RAM | Walltime | Tokens |
|-------|-------|------------|---------------|-----------|-----|----------|--------|
| `A1` Source Acquisition | 1 | — | `A4` | 1 (login) | 2 GB | ~5 min | ~8,000 |
| `A2` Code Intelligence | 2 | `A1` | `A4` | 1 (login) | 2 GB | ~10 min | ~25,000 |
| `A3` Dependency & Build | 3 | `A2` | `A4` | 8–16 (compile node) | 8 GB | ~20 min | ~15,000 |
| `A4` Cluster Topology | 4 | — | `A1`, `A2`, `A3` | 1 (login) | 1 GB | ~5 min | ~10,000 |
| `A5` Job Authoring | 5 | `A3` + `A4` | — | 1 (login) | 1 GB | ~5 min | ~12,000 |
| `A6` Monitoring & Validation | 6 | `A5` | — | 1 (login) | 1 GB | ~30 min | ~10,000 |
| **Total** | | | | | | **~75 min** | **~80,000** |

---

## Verification Checklist

- [ ] `WorkingDir/xcompact3d/` directory populated with source and `decomp2d/` submodule
- [ ] `WorkingDir/SOURCE_REVISION.txt` contains reproducible git commit hashes
- [ ] `cmake ..` completes without errors; FFTW and MPI found
- [ ] `make -j` produces `build/bin/xcompact3d`
- [ ] `ldd build/bin/xcompact3d` shows correct FFTW, MPI, and HDF5 shared libraries
- [ ] `WorkingDir/CLUSTER_PROFILE.txt` documents partitions, GPU types, and QOS limits
- [ ] `submit_tgv.sh` passes `sbatch --test-only` without errors
- [ ] `sbatch submit_tgv.sh` returns a job ID
- [ ] `squeue -j $JOB_ID` shows `RUNNING` state
- [ ] Logs contain 2decomp-fft decomposition layout message
- [ ] Logs show time-stepping progressing (step 1, 2, …)
- [ ] HDF5 snapshot files (`*.h5`) or data directory appear on disk at `ioutput` intervals
- [ ] `sacct -j $JOB_ID` shows `COMPLETED` with `ExitCode=0:0`

