---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-opus-4-6
provider: anthropic
session_id: b4f87765-5f24-446c-b4a4-14de0a8d4040
duration_ms: 159448
duration_wall_s: 164.2
cost_usd: 0.3675355
num_turns: 15
timestamp: 2026-03-19T13:45:37.722298+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment Plan — Dispatch Document

## Context

**Objective:** Deploy the XCompact3D (Incompact3d) computational fluid dynamics solver on a Slurm-managed HPC cluster. XCompact3D is a high-order finite-difference framework for simulating incompressible/compressible turbulent flows, written in Fortran 2003+ and parallelized with MPI and a 2D pencil decomposition (via the bundled 2decomp&fft library).

**Working Directory:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`

**Assumptions:**
- The HPC cluster uses Slurm as the workload manager with `module` environment management.
- Standard HPC toolchain is available (GCC/gfortran or Intel compilers, OpenMPI/MPICH, CMake ≥ 3.20).
- FFTW3 is either available via `module load` or will be built from source.
- The user wants a CPU-based deployment (XCompact3D's mainline GPU support is experimental/limited to specific branches).
- A representative test case (e.g., Taylor-Green Vortex — `TGV`) will be used for validation.

---

## Dependency Graph (Gantt-style)

```
Stage 1 (Download)  ──────►  Stage 2 (Build)  ──────►  Stage 4 (Submit Job)  ──►  Stage 5 (Monitor)
                                                              ▲
Stage 3 (Query Cluster)  ─────────────────────────────────────┘
```

- **Stage 1** and **Stage 3** are independent → run **in parallel**.
- **Stage 2** depends on Stage 1.
- **Stage 4** depends on Stages 2 and 3.
- **Stage 5** depends on Stage 4.

---

## Stage 1 — Download Source Code & Dependencies

| Field | Value |
|---|---|
| **Specialist Agent** | `source-fetcher` — a lightweight shell agent that clones repos and verifies checksums |
| **Hardware** | Login node; no GPU needed; 1 CPU core, ~512 MB RAM, ~2 GB disk |
| **Estimated Tokens** | ~4,000 input + ~2,000 output ≈ **6,000 tokens** |
| **Dependencies** | None (can start immediately) |

### Commands

```bash
# 1a. Clone XCompact3D from upstream
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
git clone https://github.com/xcompact3d/Incompact3d.git
cd Incompact3d
git checkout master          # or a specific release tag, e.g. v9.0
git submodule update --init --recursive   # pulls bundled 2decomp&fft if present

# 1b. Verify the clone
ls -la
cat README.md
```

### Expected Output
- Directory `Incompact3d/` with source tree including `src/`, `examples/`, `CMakeLists.txt` (or `Makefile`), and bundled `decomp2d/` or `2decomp-fft/`.

---

## Stage 2 — Read, Understand, Configure & Build

| Field | Value |
|---|---|
| **Specialist Agent** | `build-engineer` — a compiler-aware agent that reads build systems, resolves dependencies, and runs `cmake`/`make` |
| **Hardware** | Login/build node; no GPU; 4 CPU cores (parallel make), ~4 GB RAM, ~1 GB disk |
| **Estimated Tokens** | ~8,000 input + ~6,000 output ≈ **14,000 tokens** |
| **Dependencies** | **Stage 1** (source code must be available) |

### Step 2a — Read & Understand the Source

```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

# Inspect project structure
find . -maxdepth 2 -type f -name "*.f90" | head -30
cat README.md
cat CMakeLists.txt            # or cat Makefile if CMake is absent
ls examples/                  # list available test cases
cat examples/Taylor-Green-Vortex/input.i3d   # examine a sample input file
```

**Key items to identify:**
- Build system type (CMake vs raw Makefile)
- Required external libraries (MPI, FFTW3, ADIOS2, etc.)
- Compiler flags and optimization options
- Input file format (`.i3d` namelist files)

### Step 2b — Install Required Libraries via Modules

```bash
# Load required modules (names vary by cluster — adapt as needed)
module purge
module load cmake/3.24
module load gcc/12.2.0          # or intel/2023.0
module load openmpi/4.1.4       # or mpich, intelmpi
module load fftw/3.3.10         # double-precision, MPI-enabled build

# Verify
which mpifort
mpifort --version
cmake --version
pkg-config --libs fftw3 fftw3_mpi 2>/dev/null || echo "FFTW found via module path"
```

**If FFTW3 is NOT available as a module**, build from source:

```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
wget http://www.fftw.org/fftw-3.3.10.tar.gz
tar xzf fftw-3.3.10.tar.gz && cd fftw-3.3.10
./configure --prefix=$HOME/local/fftw3 --enable-mpi --enable-shared CC=mpicc F77=mpifort
make -j4 && make install
export FFTW_DIR=$HOME/local/fftw3
export LD_LIBRARY_PATH=$FFTW_DIR/lib:$LD_LIBRARY_PATH
export CMAKE_PREFIX_PATH=$FFTW_DIR:$CMAKE_PREFIX_PATH
```

### Step 2c — Configure & Build XCompact3D

**Option A — CMake build (preferred if `CMakeLists.txt` exists):**

```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d
mkdir -p build && cd build

cmake .. \
  -DCMAKE_Fortran_COMPILER=mpifort \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=ON

make -j4
```

**Option B — Makefile build (if no CMake):**

```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

# Edit Makefile to set compiler and flags
# FC = mpifort
# FFLAGS = -O3 -march=native
# FFT = generic   (or fftw3, fftw3_f03)

make clean
make -j4
```

### Expected Output
- Executable binary, typically `xcompact3d` (or `incompact3d`) in `build/bin/` or the project root.

```bash
# Verify
ls -la build/bin/xcompact3d || ls -la ./xcompact3d
./build/bin/xcompact3d --help 2>&1 | head -5   # check it runs
```

---

## Stage 3 — Query Cluster Resources via Slurm

| Field | Value |
|---|---|
| **Specialist Agent** | `cluster-inspector` — a read-only agent that queries Slurm and reports available resources |
| **Hardware** | Login node; 1 CPU core, ~256 MB RAM, no disk |
| **Estimated Tokens** | ~3,000 input + ~3,000 output ≈ **6,000 tokens** |
| **Dependencies** | None (can start **in parallel** with Stage 1) |

### Commands

```bash
# 3a. List all partitions and their state
sinfo -o "%20P %10a %10l %6D %10T %N"

# 3b. Show detailed partition configuration
scontrol show partition

# 3c. Show detailed node information (CPUs, memory, GPUs)
scontrol show nodes | head -100

# 3d. Query GPU availability (if applicable)
sinfo -o "%20P %10G %6D %N" --Format="partition,gres,nodes,nodelist"

# 3e. Check network topology (if InfiniBand)
scontrol show topology 2>/dev/null || echo "Topology info not available"

# 3f. Check current cluster utilization
squeue -u $USER          # own jobs
sinfo -N -l              # node-level summary

# 3g. Check per-node details for a specific partition
sinfo -p <partition_name> -N -l
```

### Information to Collect
- Available partitions and their time limits
- Number of nodes, cores per node, memory per node
- GPU types and counts (if any)
- Network interconnect type (InfiniBand, OmniPath, Ethernet)
- Recommended partition for the job based on time limit and resource availability

---

## Stage 4 — Write & Submit the Slurm Batch Script

| Field | Value |
|---|---|
| **Specialist Agent** | `job-submitter` — an agent that writes Slurm scripts and submits jobs |
| **Hardware** | Login node; 1 CPU core, ~256 MB RAM |
| **Estimated Tokens** | ~6,000 input + ~5,000 output ≈ **11,000 tokens** |
| **Dependencies** | **Stage 2** (binary must be compiled) AND **Stage 3** (cluster resources must be known) |

### Slurm Batch Script

Create file: `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/run_xcompact3d.slurm`

```bash
#!/bin/bash
#SBATCH --job-name=xcompact3d-tgv
#SBATCH --partition=compute            # <-- adjust from Stage 3 findings
#SBATCH --nodes=2                      # <-- adjust based on problem size
#SBATCH --ntasks-per-node=32           # <-- match cores per node from Stage 3
#SBATCH --cpus-per-task=1
#SBATCH --mem=0                        # use all available memory on node
#SBATCH --time=02:00:00                # wall-clock limit
#SBATCH --output=xcompact3d_%j.out
#SBATCH --error=xcompact3d_%j.err
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=jye@example.com    # <-- update email
#SBATCH --exclusive                    # exclusive node access for MPI perf

# ── Environment Setup ──
module purge
module load gcc/12.2.0
module load openmpi/4.1.4
module load fftw/3.3.10

# If FFTW was built locally:
# export LD_LIBRARY_PATH=$HOME/local/fftw3/lib:$LD_LIBRARY_PATH

# ── Working directory ──
WORKDIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
SRCDIR=${WORKDIR}/Incompact3d
RUNDIR=${WORKDIR}/run_tgv

mkdir -p ${RUNDIR}
cd ${RUNDIR}

# Copy input file and executable
cp ${SRCDIR}/examples/Taylor-Green-Vortex/input.i3d .
cp ${SRCDIR}/build/bin/xcompact3d .         # adjust path if needed

# ── Print diagnostics ──
echo "Job ID: ${SLURM_JOB_ID}"
echo "Nodes: ${SLURM_JOB_NODELIST}"
echo "Tasks: ${SLURM_NTASKS}"
echo "Start time: $(date)"
echo "Working dir: $(pwd)"

# ── Run ──
srun ./xcompact3d input.i3d

echo "End time: $(date)"
echo "Exit code: $?"
```

### Submit Command

```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
sbatch run_xcompact3d.slurm
```

### Expected Output
- Slurm prints `Submitted batch job <JOBID>`

---

## Stage 5 — Monitor, Validate & Collect Results

| Field | Value |
|---|---|
| **Specialist Agent** | `job-monitor` — a polling agent that checks job status and validates outputs |
| **Hardware** | Login node; 1 CPU core, ~256 MB RAM |
| **Estimated Tokens** | ~4,000 input + ~3,000 output ≈ **7,000 tokens** |
| **Dependencies** | **Stage 4** (job must be submitted) |

### Commands

```bash
# 5a. Check job status
squeue -j <JOBID> -o "%.18i %.9P %.20j %.8u %.8T %.10M %.6D %R"

# 5b. Detailed job info (pending reason, start time estimate)
scontrol show job <JOBID>

# 5c. Monitor output log in real time
tail -f /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/xcompact3d_<JOBID>.out

# 5d. Check error log
cat /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/xcompact3d_<JOBID>.err

# 5e. After completion — check exit status
sacct -j <JOBID> --format=JobID,JobName,Partition,NNodes,NTasks,State,ExitCode,Elapsed,MaxRSS

# 5f. Validate output files
ls -la /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/run_tgv/
# Expect: data/ directory with snapshot files (ux*.dat, uy*.dat, uz*.dat, pp*.dat)
# and possibly probe files, statistics files

# 5g. Quick sanity check — ensure output files are non-empty and growing
wc -c /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/run_tgv/data/ux0010.dat 2>/dev/null

# 5h. Check for common errors in the log
grep -i -E "error|fail|abort|segfault|nan|infinity" xcompact3d_<JOBID>.out xcompact3d_<JOBID>.err
```

### Validation Criteria
- Job completes with `State = COMPLETED` and `ExitCode = 0:0`
- Output snapshot files exist and are non-zero size
- No `NaN`, `Infinity`, or `segfault` messages in logs
- Time-step information printed in stdout showing CFL numbers remain < 1

---

## Agent Dispatch Summary

| Stage | Agent | Parallel Group | Hardware | Est. Tokens | Depends On |
|-------|-------|---------------|----------|-------------|------------|
| 1 — Download | `source-fetcher` | **Group A** | 1 core, 512 MB, 2 GB disk | 6,000 | — |
| 3 — Query Cluster | `cluster-inspector` | **Group A** | 1 core, 256 MB | 6,000 | — |
| 2 — Build | `build-engineer` | **Group B** | 4 cores, 4 GB, 1 GB disk | 14,000 | Stage 1 |
| 4 — Submit Job | `job-submitter` | **Group C** | 1 core, 256 MB | 11,000 | Stages 2, 3 |
| 5 — Monitor | `job-monitor` | **Group D** | 1 core, 256 MB | 7,000 | Stage 4 |

**Total estimated tokens:** ~44,000

### Parallel Execution Timeline

```
Time ──────────────────────────────────────────────────────────►

Group A  ║ source-fetcher ║ cluster-inspector ║   (parallel)
         ╚════════════════╝ ╚═════════════════╝
                  │                    │
                  ▼                    │
Group B  ║    build-engineer    ║      │           (sequential after Stage 1)
         ╚══════════════════════╝      │
                  │                    │
                  └────────┬───────────┘
                           ▼
Group C           ║  job-submitter  ║               (after Stages 2 & 3)
                  ╚═════════════════╝
                           │
                           ▼
Group D           ║  job-monitor  ║                 (after Stage 4)
                  ╚═══════════════╝
```

---

## Verification Checklist

1. **Source code**: `Incompact3d/` directory exists with Fortran sources
2. **Build**: `xcompact3d` binary exists and is executable
3. **Cluster info**: Partition name, cores/node, and memory/node documented
4. **Job submitted**: `sbatch` returns a valid job ID
5. **Job completes**: `sacct` shows `COMPLETED` with exit code `0:0`
6. **Physics check**: Output files exist; log shows time-stepping without NaN/divergence

