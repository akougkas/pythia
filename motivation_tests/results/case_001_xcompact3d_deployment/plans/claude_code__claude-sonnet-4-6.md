---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-sonnet-4-6
provider: anthropic
session_id: 40952500-032d-4a90-afc7-fa659230c462
duration_ms: 178681
duration_wall_s: 189.1
cost_usd: 0.42557164999999997
num_turns: 12
timestamp: 2026-03-18T00:30:37.120752+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment Plan
**Working Directory:** `/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir`
**Repository:** `https://github.com/xcompact3d/Incompact3d`
**Scheduler:** Slurm

---

## Context

XCompact3D (code-named *Incompact3d*) is a high-order finite-difference CFD solver written in Fortran, designed for DNS/LES on HPC clusters. It requires an MPI-parallel build with FFTW3, and optionally HDF5/ADIOS2 for I/O. This plan describes the full lifecycle: source acquisition → build → cluster inspection → job submission → monitoring. Stages with no mutual dependency are scheduled to run in parallel to reduce wall-clock time.

---

## Dependency Graph

```
Stage 1 (Download)  ──┐
                      ├──► Stage 2 (Build) ──┐
Stage 3 (Cluster)   ──┘ (wait for both)      ├──► Stage 4 (Submit) ──► Stage 5 (Monitor)
  (runs in parallel with Stage 1)            │
                                             ┘
Parallelism: Stage 1 ∥ Stage 3  →  Stage 2  →  Stage 4  →  Stage 5
```

---

## Stage 1 — Source Acquisition

**Specialist Agent:** `Fetcher Agent`
**Runs in parallel with:** Stage 3
**Depends on:** nothing
**Expected tokens:** ~8,000
**Hardware:** Login node (1 CPU, ~256 MB RAM, internet access required)

### Commands

```bash
# Set working directory
WORKDIR=/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir
cd $WORKDIR

# 1a. Clone the repository (shallow clone for speed; omit --depth for full history)
git clone --depth=1 https://github.com/xcompact3d/Incompact3d.git xcompact3d
cd xcompact3d

# 1b. Inspect the top-level structure
ls -lh

# 1c. Initialize and fetch all git submodules (2decomp&fft is a key submodule)
git submodule update --init --recursive

# 1d. Confirm submodule presence
ls -lh lib/

# 1e. Record the exact commit for reproducibility
git log --oneline -1
git submodule status
```

### Expected directory layout after clone
```
xcompact3d/
├── CMakeLists.txt          # Top-level CMake build file
├── src/                    # Fortran source files
├── lib/                    # Submodule: 2decomp-fft (domain decomposition + FFT)
├── examples/               # Example cases (Taylor-Green, Cylinder, etc.)
├── docs/                   # Documentation
└── README.md
```

### Key dependency fetched via submodule
- **2decomp&fft** (`lib/2decomp-fft`) — provides pencil-decomposition and FFT wrappers; XCompact3D delegates all FFT calls to this library.

---

## Stage 3 — Cluster Topology Inspection

**Specialist Agent:** `Cluster Inspector Agent`
**Runs in parallel with:** Stage 1
**Depends on:** nothing
**Expected tokens:** ~6,000
**Hardware:** Login node (1 CPU, ~128 MB RAM, Slurm client tools)

### Commands

```bash
# 3a. List all partitions with state, node count, timelimit
sinfo -o "%.18P %.5a %.10l %.6D %.6t %N"

# 3b. Detailed node list with CPU, memory, GPU, and feature info
scontrol show nodes | grep -E "NodeName|CPUTot|RealMemory|Gres|Features|Partitions|State"

# 3c. GPU-specific query (if GPUs available)
sinfo -o "%.18P %.5a %.10l %.6D %.6t %.10G %N" | grep -i gpu

# 3d. Check available GRES (generic resources: GPUs, etc.)
scontrol show node | grep -i gres

# 3e. Show network topology / switch hierarchy (for MPI locality)
scontrol show topology 2>/dev/null || echo "topology plugin not enabled"

# 3f. Query current cluster load and job queue
squeue -o "%.10i %.9P %.20j %.8u %.8T %.10M %.9l %.6D %R" | head -30

# 3g. Check scheduler configuration (max jobs, default limits)
scontrol show config | grep -E "MaxJobCount|DefMemPerCPU|MaxMemPerCPU|SchedulerType"

# 3h. Check account/QOS limits for the current user
sacctmgr show associations user=$(whoami) format=Account,Partition,QOS,MaxJobs,MaxSubmit -P 2>/dev/null

# 3i. List available modules relevant to XCompact3D build
module avail 2>&1 | grep -iE "fftw|hdf5|openmpi|mpich|intelmpi|gcc|intel|cmake" | head -40
```

### Information to record for Stage 4
- Partition name to target (e.g., `cpu`, `compute`, `normal`)
- Max cores per node (`CPUTot`)
- Max memory per node (`RealMemory`)
- GPU availability and GRES string
- Network topology (infiniband vs ethernet)
- Available MPI/compiler modules

---

## Stage 2 — Source Analysis, Dependency Installation & Build

**Specialist Agent:** `Builder Agent`
**Depends on:** Stage 1 (source present) + Stage 3 results (to select correct MPI module)
**Expected tokens:** ~25,000
**Hardware:** Login node or dedicated build node (4–8 CPUs, ≥4 GB RAM); some clusters provide `salloc` for interactive compilation

### 2a. Read and understand the source

```bash
cd $WORKDIR/xcompact3d

# Read top-level CMake to understand options
cat CMakeLists.txt

# Understand the main solver entry point
head -100 src/xcompact3d.f90

# List available example cases
ls examples/

# Read an example input file (Taylor-Green vortex)
cat examples/Taylor-Green-Vortex/input.i3d
```

**Key source files to understand:**
| File | Purpose |
|------|---------|
| `src/xcompact3d.f90` | Main program entry point |
| `src/parameters.f90` | Global parameters, namelist parsing |
| `src/time_integrators.f90` | RK3 time-stepping |
| `src/navier.f90` | Navier-Stokes RHS |
| `lib/2decomp-fft/` | Pencil decomposition & FFT (submodule) |
| `CMakeLists.txt` | Build system; key CMake options |

**CMake options of interest:**
| Option | Default | Meaning |
|--------|---------|---------|
| `FFTW_ROOT` | auto | Path to FFTW3 install |
| `HDF5_ROOT` | auto | Path to HDF5 (optional) |
| `BUILD_TESTING` | OFF | Build test suite |
| `CMAKE_BUILD_TYPE` | Release | `Release`/`Debug`/`RelWithDebInfo` |

### 2b. Load required environment modules

```bash
# Load compiler and MPI (adjust module names to cluster)
module purge
module load gcc/12.3.0          # or intel/2023.x for ifort/ifx
module load openmpi/4.1.5       # or intelmpi, mpich — match to cluster
module load cmake/3.26.0
module load fftw/3.3.10-mpi     # FFTW3 built with MPI support

# Optional: parallel HDF5 for high-performance I/O
module load hdf5/1.12.2-parallel

# Verify MPI Fortran wrapper is available
which mpif90
mpif90 --version
```

### 2c. Build XCompact3D

```bash
cd $WORKDIR/xcompact3d

# Create out-of-source build directory
mkdir -p build && cd build

# Configure with CMake
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_Fortran_COMPILER=mpif90 \
  -DFFTW_ROOT=$FFTW_DIR \
  -DHDF5_ROOT=$HDF5_DIR \
  -DBUILD_TESTING=OFF 2>&1 | tee cmake_config.log

# Inspect configuration summary
grep -E "FFTW|HDF5|MPI|Compiler|Build type" cmake_config.log

# Compile (use all available login-node cores)
make -j$(nproc) 2>&1 | tee make_build.log

# Verify the binary was produced
ls -lh xcompact3d
file xcompact3d
```

**Expected binary:** `$WORKDIR/xcompact3d/build/xcompact3d` (ELF 64-bit, dynamically linked to MPI and FFTW3 shared libraries)

### 2d. Prepare a run directory with input file

```bash
mkdir -p $WORKDIR/run
cd $WORKDIR/run

# Copy (or link) the binary
cp $WORKDIR/xcompact3d/build/xcompact3d .

# Copy an example input file; edit key parameters
cp $WORKDIR/xcompact3d/examples/Taylor-Green-Vortex/input.i3d .
```

**Minimum parameters to review in `input.i3d` (Fortran namelist format):**
```fortran
&BasicParam
  p_row = 4        ! MPI decomposition rows  (must divide ny)
  p_col = 8        ! MPI decomposition cols  (must divide nz; p_row*p_col = total MPI tasks)
  nx = 128         ! Grid points X
  ny = 128         ! Grid points Y
  nz = 128         ! Grid points Z
  xlx = 6.2832     ! Domain length X (2π for TGV)
  yly = 6.2832     ! Domain length Y
  zlz = 6.2832     ! Domain length Z
  itype = 2        ! Flow type (2 = Taylor-Green Vortex)
  dt = 0.001       ! Time step
  ifirst = 1       ! First time step
  ilast = 1000     ! Last time step
/
```
> ⚠️ `p_row × p_col` **must equal** the total number of MPI tasks requested in the Slurm script.

---

## Stage 4 — Slurm Batch Script & Job Submission

**Specialist Agent:** `Job Scheduler Agent`
**Depends on:** Stage 2 (binary ready, `input.i3d` prepared) + Stage 3 (partition/node info)
**Expected tokens:** ~12,000
**Hardware:** Login node (Slurm client only; actual job runs on compute nodes)

### 4a. Full Slurm batch script

Save as `$WORKDIR/run/submit_xcompact3d.sh`:

```bash
#!/bin/bash
#SBATCH --job-name=xcompact3d_tgv
#SBATCH --account=<YOUR_ACCOUNT>          # fill from sacctmgr output (Stage 3)
#SBATCH --partition=<TARGET_PARTITION>    # fill from sinfo output (Stage 3)
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=8              # → 4×8 = 32 total MPI tasks = p_row×p_col
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=2G
#SBATCH --time=02:00:00                   # wall clock limit HH:MM:SS
#SBATCH --output=%x_%j.out               # stdout: jobname_jobid.out
#SBATCH --error=%x_%j.err                # stderr: jobname_jobid.err
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=<YOUR_EMAIL>

# ── Environment ─────────────────────────────────────────────────────────────
module purge
module load gcc/12.3.0
module load openmpi/4.1.5
module load fftw/3.3.10-mpi
module load hdf5/1.12.2-parallel    # omit if HDF5 not used

# ── Verify resources ─────────────────────────────────────────────────────────
echo "Job ID      : $SLURM_JOB_ID"
echo "Nodes       : $SLURM_JOB_NODELIST"
echo "Tasks total : $SLURM_NTASKS"
echo "CPUs/task   : $SLURM_CPUS_PER_TASK"
echo "Start time  : $(date)"

# Sanity check: MPI tasks must equal p_row * p_col in input.i3d
P_ROW=4; P_COL=8
if [ "$SLURM_NTASKS" -ne $((P_ROW * P_COL)) ]; then
  echo "ERROR: SLURM_NTASKS ($SLURM_NTASKS) != p_row*p_col ($((P_ROW*P_COL)))"
  exit 1
fi

# ── Run ──────────────────────────────────────────────────────────────────────
WORKDIR=/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/run
cd $WORKDIR

srun --mpi=pmix \
     --nodes=$SLURM_JOB_NUM_NODES \
     --ntasks=$SLURM_NTASKS \
     ./xcompact3d input.i3d

echo "End time    : $(date)"
echo "Exit status : $?"
```

> **Notes on `srun` flags:**
> - `--mpi=pmix` — recommended for OpenMPI ≥ 4 on Slurm; use `--mpi=pmi2` for MPICH or older stacks.
> - Replace `srun` with `mpirun -np $SLURM_NTASKS` if the cluster's OpenMPI is not Slurm-aware.

### 4b. Submit the job

```bash
cd $WORKDIR/run

# Dry-run first to validate the script syntax
sbatch --test-only submit_xcompact3d.sh

# Actual submission
sbatch submit_xcompact3d.sh

# Record the returned Job ID
# Example output: "Submitted batch job 1234567"
```

---

## Stage 5 — Job Monitoring & Validation

**Specialist Agent:** `Monitor Agent`
**Depends on:** Stage 4 (job submitted, Job ID known)
**Expected tokens:** ~10,000
**Hardware:** Login node (Slurm client + filesystem access)

### 5a. Check job state

```bash
JOB_ID=<job_id_from_sbatch>

# Live status in the queue
squeue -j $JOB_ID -o "%.10i %.9P %.20j %.8u %.8T %.10M %.9l %.6D %R"

# Full Slurm control record (shows reason if PENDING)
scontrol show job $JOB_ID

# Poll until running (quick loop; Ctrl-C to stop)
watch -n 10 "squeue -j $JOB_ID"
```

### 5b. Read logs during and after run

```bash
cd $WORKDIR/run

# Tail stdout live once the job starts
tail -f xcompact3d_tgv_${JOB_ID}.out

# Check stderr for MPI/library errors
cat xcompact3d_tgv_${JOB_ID}.err

# After job ends: check Slurm accounting for wall time and exit code
sacct -j $JOB_ID \
  --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,NodeList
```

### 5c. Validate correct startup

XCompact3D prints a structured header at startup. Confirm these lines appear in stdout:

```
 ==========================================
      INCOMPACT3D
 ==========================================
  Spatial discretisation: ...
  ...
  Running with   32 MPI tasks
  Domain decomposition:  4 x  8
  Grid:  128 x 128 x 128
  ...
  Time-stepping scheme: RK3
  Starting simulation at t=0.000
```

**Validation checklist:**
| Check | Command | Pass condition |
|-------|---------|----------------|
| Job completed | `sacct -j $JOB_ID --format=State,ExitCode` | `COMPLETED 0:0` |
| No MPI errors | `grep -i "error\|abort\|segfault" *.err` | No output |
| Correct task count | `grep "MPI tasks" *.out` | `32 MPI tasks` |
| Correct decomposition | `grep "decomposition" *.out` | `4 x 8` |
| Output files created | `ls -lh *.dat *.h5 2>/dev/null` | Files present & non-zero |
| First checkpoint written | `grep -i "saving\|checkpoint\|output" *.out` | Present at expected step |

### 5d. Performance diagnostics (optional post-run)

```bash
# Check job efficiency (CPU utilisation vs allocated)
seff $JOB_ID

# Detailed node-level accounting
sacct -j $JOB_ID --format=JobID,NNodes,NCPUS,CPUTime,Elapsed,MaxRSS -p

# If TACC-style job stats are available
job_stats $JOB_ID 2>/dev/null
```

---

## Agent Dispatch Summary Table

| Stage | Agent | Parallel With | Depends On | CPUs | RAM | Est. Tokens |
|-------|-------|--------------|------------|------|-----|-------------|
| 1 – Download | Fetcher Agent | Stage 3 | — | 1 | 256 MB | ~8 K |
| 3 – Cluster Inspect | Cluster Inspector Agent | Stage 1 | — | 1 | 128 MB | ~6 K |
| 2 – Build | Builder Agent | — | Stages 1+3 | 4–8 | 4 GB | ~25 K |
| 4 – Submit | Job Scheduler Agent | — | Stage 2 | 1 | 128 MB | ~12 K |
| 5 – Monitor | Monitor Agent | — | Stage 4 | 1 | 128 MB | ~10 K |

**Total estimated tokens:** ~61,000

---

## Critical Files Modified / Created

| Path | Role |
|------|------|
| `WorkingDir/xcompact3d/` | Cloned source tree |
| `WorkingDir/xcompact3d/build/xcompact3d` | Compiled binary |
| `WorkingDir/run/input.i3d` | Simulation input (namelist) |
| `WorkingDir/run/submit_xcompact3d.sh` | Slurm batch script |
| `WorkingDir/run/xcompact3d_tgv_<JID>.out` | Job stdout / progress log |
| `WorkingDir/run/xcompact3d_tgv_<JID>.err` | Job stderr / error log |

---

## Verification End-to-End

1. **Build verification:** `file xcompact3d` returns `ELF 64-bit LSB executable`; `ldd xcompact3d` shows `libfftw3_mpi.so` and `libmpi_mpifh.so` resolved (no "not found").
2. **Dry-run submission:** `sbatch --test-only submit_xcompact3d.sh` exits 0 with `"Job would be submitted"`.
3. **Runtime validation:** `sacct` shows `COMPLETED 0:0`; stdout contains correct MPI task count and decomposition; output data files are non-empty.
4. **Physics sanity (TGV case):** kinetic energy at t=0 matches analytical value `E₀ = 0.125`; energy dissipation peak occurs near t≈9 (well-known TGV result).

