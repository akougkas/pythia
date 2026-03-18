---
case: case_001_xcompact3d_deployment
framework: claude_code
model: qwen/qwen3.5-9b
provider: lm_studio
session_id: abffc87e-2637-41ef-9192-828d909fe449
duration_ms: 144908
duration_wall_s: 154.1
cost_usd: 1.2275338999999998
num_turns: 8
timestamp: 2026-03-18T15:16:36.925311+00:00
error: None
---

# Plan

# XCompact3D Deployment Plan on HPC Cluster (Slurm)

## Context

This document provides a comprehensive deployment plan for deploying the XCompact3D application (Incompact3D) on an HPC cluster managed by Slurm. XCompact3D is a parallel computational fluid dynamics (CFD) solver designed for large-scale simulations requiring MPI parallelization and potentially GPU acceleration. The plan covers all stages from source code acquisition through deployment verification, with detailed commands, scripts, and agent resource specifications.

---

## Phase 1: Source Code Acquisition and Dependency Setup

### Specialist Agent
- **Agent Type**: `General-Purpose` (for web browsing and file operations)
- **Hardware Resources**: Standard compute node with curl/git network access (no GPU required)
- **Expected Token Usage**: ~5,000 tokens for parsing repository structure and documentation

### Dependencies on Other Stages
- No dependencies (initial stage)

### Subtasks and Commands

#### 1.1 Download Source Code from GitHub Repository

**Command Sequence:**
```bash
# Clone the XCompact3D (Incompact3D) source code
cd /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir
mkdir -p xcompact3d_source
cd xcompact3d_source

git clone https://github.com/xcompact3d/Incompact3d.git
cd Incompact3d

# Fetch all required dependencies including submodules (if any)
git submodule update --init --recursive

# Optionally, fetch release tags for stable version selection
git fetch --tags
```

**Alternative: Direct Download via wget/curl (if git unavailable):**
```bash
# Find and download latest release tarball from GitHub releases
RELEASE_TAG=$(curl -s https://api.github.com/repos/xcompact3d/Incompact3d/releases/latest \
    | grep '"tag_name"' | sed 's/.*"\([^"]*\)".*/\1/')

wget -O incompact3d-${RELEASE_TAG}.tar.gz \
    "https://github.com/xcompact3d/Incompact3d/archive/${RELEASE_TAG}.tar.gz"
gunzip incompact3d-${RELEASE_TAG}.tar.gz
mv incompact3d-${RELEASE_TAG} xcompact3d_source
```

#### 1.2 Analyze Repository Structure and Documentation

**Files to Examine:**
| Path | Purpose |
|------|---------|
| `README.md` / `INSTALL.md` | Installation instructions |
| `CMakeLists.txt` (root) | Main build configuration entry point |
| `src/CMakeLists.txt` | Source module definitions |
| `cmake/` | Custom CMake modules and platform configs |
| `doc/` or `docs/` | User documentation |
| `LICENSE` | License terms |

**Agent Analysis Tasks:**
1. Read root-level README/INSTALL for high-level setup steps
2. Examine CMakeLists.txt for build options and dependency requirements
3. Document compiler support (GNU GCC, Intel ICC, PGI)
4. Identify MPI library options (OpenMPI, MPICH, Intel MPI)
5. List optional dependencies (FFTW, HDF5, VTK/VisIt)
6. Review environment setup examples in scripts/

#### 1.3 Install Build Dependencies

**Required System Libraries (Debian/Ubuntu/Rocky example):**
```bash
# Core build tools
sudo apt-get update
sudo apt-get install -y build-essential cmake git wget curl \
    python3 python3-pip python3-venv

# MPI Library (choose one: OpenMPI, MPICH, or Intel MPI)
# For OpenMPI:
sudo apt-get install -y openmpi-bin libopenmpi-dev \
    ocl-icd-opencl-dev opencl-headers

# Or for MPICH:
# sudo apt-get install -y mpich libmpich-dev

# BLAS/LAPACK libraries (OpenBLAS or MKL)
sudo apt-get install -y libopenblas-dev liblapack-dev \
    libscotch-dev libhdf5-dev

# Optional but recommended
sudo apt-get install -y fftw3-dev libfftw3-dev \
    libvtk7-dev libhdf5-openmpi-dev

# GPU support (if targeting GPU-enabled builds)
sudo apt-get install -y cuda-toolkit libcurand-dev libcusparse-dev \
    libnccl-dev
```

**Alternative: Using Module System (Slurm clusters):**
```bash
# Typical module load commands for HPC clusters
module purge  # Clear any loaded modules

# Load MPI environment
module load openmpi/4.1.2   # or intel-mpi/2021.4

# Load compiler and CMake
module load gcc/12.3
module load cmake/3.26

# Load GPU libraries if needed
module load cuda/12.2

# Check loaded environment
env | grep -E "^(MPI_|CUDA_|CMAKE_|SLURM_)"
```

---

## Phase 2: Source Code Analysis and Build Configuration

### Specialist Agent
- **Agent Type**: `General-Purpose` (for file reading, analysis, and documentation)
- **Hardware Resources**: Standard compute node with sufficient memory (no GPU required)
- **Expected Token Usage**: ~10,000 tokens for parsing CMake configuration and source structure

### Dependencies on Other Stages
- Depends on Phase 1.3 (build dependencies installed)

### Subtasks and Commands

#### 2.1 Create Build Directory and Configure CMake

**Setup:**
```bash
cd /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/xcompact3d_source/Incompact3d

# Create build directory
mkdir -p build && cd build

# Configure with CMake (example using GCC + OpenMPI)
cmake .. \
    -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_CXX_COMPILER=g++ \
    -DMPI_LIBRARY=openmpi \
    -DENABLE_BENCHMARKING=OFF \
    -DSLRAM_PATH="" \
    -DPYTHON_EXECUTABLE=$(which python3) \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DMPI_C_COMPILER=gcc \
    -DMPI_CXX_COMPILER=g++ \
    -DENABLE_BLIS=OFF \
    -DENABLE_BENCHMARKING=OFF \
    -DENABLE_OPENCL=OFF

# For GPU-enabled build (if desired):
# cmake .. -DENABLE_CUDA=ON -DCUDA_EXECUTABLE=/usr/bin/nvcc
```

**Build Options Reference:**
| Variable | Description | Typical Values |
|----------|-------------|----------------|
| `MPI_LIBRARY` | MPI implementation | `openmpi`, `mpich`, `intelmpi` |
| `BLAS_LIBRARY` | BLAS library | `OpenBLAS`, `MKL`, `BLIS` |
| `CMAKE_BUILD_TYPE` | Build optimization | `Debug`, `Release`, `RelWithDebInfo` |
| `ENABLE_CUDA` | CUDA support | `ON`/`OFF` (requires NVIDIA GPU) |
| `ENABLE_OPENCL` | OpenCL acceleration | `ON`/`OFF` |
| `BUILD_SHARED_LIBS` | Shared library build | `ON`/`OFF` |

#### 2.2 Compile the Application

**Compile Commands:**
```bash
cd build

# Single-threaded compile (slower, useful for debugging)
cmake --build . -j1

# Multi-threaded compile with all available cores
cmake --build . -j$(nproc)

# Or with specific parallelism:
cmake --build . -j8

# Show progress during build:
cmake --build . -j$(nproc) --verbose
```

**Expected Output Files:**
| File/Executable | Purpose |
|-----------------|---------|
| `incompact3d` | Main application executable (if compiled standalone) |
| `incompact3d.exe` | Windows-compatible if cross-compiled |
| `libxcompact*.so/.a` | Shared/archive libraries (BUILD_SHARED_LIBS=ON/OFF) |

#### 2.3 Build Verification

**Quick Smoke Test:**
```bash
# Verify executable was created
ls -lh incompact3d

# Check executable is runnable (with minimal arguments)
./incompact3d --help
./incompact3d --info

# Or check for help/usage:
./incompact3d 2>&1 | head -20
```

---

## Phase 3: Slurm Cluster Resource Discovery and Configuration

### Specialist Agent
- **Agent Type**: `General-Purpose` (for executing shell commands and parsing cluster info)
- **Hardware Resources**: Login node with Slurm access (standard CPUs, no GPU required)
- **Expected Token Usage**: ~3,000 tokens for parsing sinfo/scontrol output

### Dependencies on Other Stages
- No build dependencies; can run in parallel with Phase 1.2 if resources available

### Subtasks and Commands

#### 3.1 Query Available Nodes (`sinfo`)

**Basic Node Overview:**
```bash
# List all nodes with status
sinfo

# Detailed node information (full columns)
sinfo -l

# Show only compute partitions
sinfo -o "%5Name %10Partition %16State %-8TimeLeft %3NNodes" | grep Up

# Count active nodes per partition
for partition in $(sinfo -p); do
    echo "$partition: $(sinfo -p $partition | wc -l) nodes available"
done
```

**Node Information for Job Planning:**
```bash
# Show node names, cores, memory, and state
sinfo -o "%10Name %-25Partition %3State %-6TimeLeft %8Nodes %4Cores %2Memory"

# Identify GPU nodes if available
echo "=== GPU Nodes ==="
sinfo -o "%N %T %C %M" 2>/dev/null | grep -i "gpu\|accelerator" || echo "No GPU nodes detected via name"

# Check InfiniBand-enabled nodes (for high-speed MPI)
sinfo -o "%N %-30Address %16RMT_Address"
```

#### 3.2 Query Partitions and System Configuration (`scontrol`)

**Partition Configuration:**
```bash
# Show all partitions with their configurations
scontrol show partition

# Detailed view of each partition
echo "=== Partitions ==="
sinfo -p -l

# For a specific partition (if known):
scontrol show partition compute
scontrol show partnode compute  # Nodes in compute partition
```

**Node Allocation Status:**
```bash
# Show allocated nodes and time remaining
scontrol show cpunode --format="%N %T" | grep -i "allocat.*yes\|allocat=1"

# Check system-wide node allocation
sinfo -n -o "%N %-25Part %6State %8TimeLeft"
```

#### 3.3 GPU Resource Discovery (if applicable)

**Check for GPU Accelerators:**
```bash
# List nodes with GPUs
echo "=== GPU-Enabled Nodes ==="
sinfo -o "%10Name %-10Partition %15State %-6Nodes" | grep -i gpu || \
sinfo -o "%10Name %-10Partition %3State %-8TimeLeft" | head -20

# scontrol for GPU partition details (if exists)
scontrol show partition gpu 2>/dev/null || echo "No GPU partition found"

# Check CUDA availability on login node:
nvidia-smi 2>/dev/null || echo "nvidia-smi not available (expected on login nodes)"
```

#### 3.4 Network Topology Inspection

**InfiniBand/RDMA Network Information:**
```bash
# Show network configuration for compute partitions
scontrol show config | grep "^Network" -A 5

# Check per-node addresses and networks
sinfo -o "%N %-20Address %16RMT_Address %3State"

# Alternative: show detailed node info including networks
sinfo -l -o "%N %T %C %M %B %c %h %t %n" 2>/dev/null | head -30
```

#### 3.5 Check Available Slurm Versions and Features

```bash
# Show Slurm version and features
sinfo --version

# Show all available resources
scontrol show config

# Check partition-specific limits (useful for memory requests)
for p in $(sinfo -p); do
    echo "=== Partition: $p ==="
    scontrol show partition "$p" 2>/dev/null | head -15
done
```

---

## Phase 4: Slurm Batch Script Creation and Job Submission

### Specialist Agent
- **Agent Type**: `General-Purpose` (for script generation and sbatch execution)
- **Hardware Resources**: Login node with write access to WorkingDir (no GPU required for submission)
- **Expected Token Usage**: ~2,500 tokens for script generation

### Dependencies on Other Stages
- Depends on Phase 1.3 (dependencies installed) and Phase 2.2 (application built)
- Can run in parallel with Phase 3 since it only requires read access to cluster info

### Subtasks and Commands

#### 4.1 Create the Slurm Batch Script

**Location**: `/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/scripts/xcompact3d_slurm.sh`

```bash
#!/usr/bin/env bash
#
# XCompact3D HPC Job Script for Slurm Cluster
# ============================================
#
# This batch script deploys and runs XCompact3D (Incompact3D)
# on an HPC cluster using Slurm workload manager.
#
# Resource Requirements:
#   - Nodes: [CONFIGURE AS NEEDED]
#   - CPUs per node: [CONFIGURE AS NEEDED]
#   - Memory per node: [CONFIGURE AS NEEDED]
#   - Walltime: [CONFIGURE AS NEEDED]
#
# Usage: sbatch scripts/xcompact3d_slurm.sh [config_file]
#

#SBATCH --job-name=xcompact3d_run
#SBATCH --output=logs/%x_%j.out        # Standard output (%j = job ID)
#SBATCH --error=logs/%x_%j.err         # Error output
#SBATCH --append-rm                    # Append RM to error files
#SBATCH --partition=compute            # Use compute partition (or 'gpu' if needed)
#SBATCH --nodes=4                      # Number of compute nodes
#SBATCH --ntasks-per-node=8           # MPI ranks per node (32 total for 4x8)
#SBATCH --cpus-per-task=4             # CPUs per MPI rank (for data prep/OpenMP)
#SBATCH --mem=64g                     # 64 GB memory per compute node
#SBATCH --time=7-00:00:00             # 7-day walltime for long CFD runs

# Array job support if running parameter sweeps:
# @array=1-10                        # Uncomment for array job (10 cases)

# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------

# Change to working directory (SLURM_SUBMIT_DIR is set by Slurm)
WORKING_DIR="${SLURM_SUBMIT_DIR:-$HOME/xcompact3d_source/Incompact3d/build}"
cd "$WORKING_DIR" || exit 1

echo "Working directory: $(pwd)" >&2

# Set MPI environment for CUDA/MPI compatibility (if using GPU)
export OMP_NUM_THREADS=1              # One thread per rank for hybrid MPI/CUDA
export CUDA_VISIBLE_DEVICES=""        # Let application handle GPU selection

# -----------------------------------------------------------------------------
# Load Required Modules (Adjust to your cluster's module system)
# -----------------------------------------------------------------------------
module purge                          # Clear any loaded modules

# Example: Load MPI and compiler environment
# Use 'module avail' on your cluster to find exact module paths
module load openmpi/4.1.2             # MPI library (modify as needed)
module load gcc/12.3                  # C/C++ compiler
module load cmake/3.26                # CMake build system

# For GPU-enabled builds:
# module load cuda/12.2
# module load nvcc-wrapper

# If using Intel compilers (common on HPC):
# module load intel/2021.4

# -----------------------------------------------------------------------------
# Application Execution
# -----------------------------------------------------------------------------

# Display job environment information
echo "" >&2
echo "========== XCompact3D Job Information ==========" >&2
echo "Job ID: $SLURM_JOB_ID" >&2
echo "Array Index: ${SLURM_ARRAY_TASK_ID:-N/A}" >&2
echo "Partition: $SLURM_PARTITION_NAME" >&2
echo "Nodes allocated: $SLURM_JOB_NUM_NODES" >&2
echo "Time limit: $SLURM_TIME_LIMIT" >&2

# Check MPI installation
echo "" >&2
echo "========== MPI Check ==========" >&2
which mpich || which mpiexec || echo "Standard MPI command not found; using srun" >&2

# Execute XCompact3D application
# -----------------------------------------------------------------------------
# Option 1: Standalone executable (after building with BUILD_STANDALONE_EXECUTABLE=ON)
if [ -f "./incompact3d" ]; then
    echo "" >&2
    echo "========== Running incompact3d ==========" >&2

    # Run the application with default config or user-specified file
    if [ "$#" -gt 0 ]; then
        ./incompact3d "$@"
    else
        # Try to find default input file(s)
        if [ -f "input.inp" ] || [ -f "case.dat" ]; then
            ./incompact3d < "$(basename $1 input.inp 2>/dev/null)$(basename $1 case.dat)" \
                && echo "Case completed successfully." >&2 \
                || echo "Case failed with errors." >&2
        elif [ -f "config.yaml" ]; then
            ./incompact3d --config=config.yaml
        else
            # Run without arguments (may show help/usage)
            ./incompact3d 2>&1 | head -30
        fi
    fi
fi

# -----------------------------------------------------------------------------
# Alternative: Using srun for MPI execution (if not built as standalone)
# -----------------------------------------------------------------------------
# Option 2: Run via mpiexec/srun (for library-based builds or MPI-only modes)
# Uncomment and modify if needed:
# -----------------------------------------------------------------------------
# mpiexec -n $SLURM_JOB_NUM_TASKS ./incompact3d --config=config.yaml || \
# srun --cpu-bind=cores ./incompact3d --config=config.yaml

# Or using Intel MPI wrapper (if available):
# icxmpiexec -n $SLURM_JOB_NUM_TASKS ./incompact3d --config=config.yaml

# -----------------------------------------------------------------------------
# Post-execution Diagnostics
# -----------------------------------------------------------------------------

# Check for output files generated by the application
echo "" >&2
echo "========== Output Files Generated ==========" >&2
ls -lh results/ 2>/dev/null || ls -lh *.dat *.out 2>/dev/null || \
    echo "No obvious output files found." >&2

# Final status report
if [ $? -eq 0 ]; then
    echo "" >&2
    echo "========== Job Completed Successfully ==========" >&2
else
    echo "" >&2
    echo "========== Job May Have Failed ==========" >&2
fi

# -----------------------------------------------------------------------------
# End of batch script
# -----------------------------------------------------------------------------
```

**Save Script:**
```bash
cat > /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/scripts/xcompact3d_slurm.sh << 'SCRIPT_EOF'
(Insert the batch script content from above)
SCRIPT_EOF

chmod +x /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/scripts/xcompact3d_slurm.sh
```

#### 4.2 Submit the Job (`sbatch`)

**Basic Submission:**
```bash
cd /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir

# Submit batch script (use relative path or absolute path)
sbatch scripts/xcompact3d_slurm.sh

# Specify a particular input file:
sbatch scripts/xcompact3d_slurm.sh config.yaml

# Check the output job ID from the sbatch output:
# Output will contain lines like: Submitted batch job 12345
```

**Expected sbatch Output:**
```bash
Submitted batch job 12345
```

**Alternative: Array Job Submission (for parameter sweeps):**
```bash
# Modify script to enable array jobs, then submit with array flag
sbatch --array=1-10 scripts/xcompact3d_slurm.sh config_case_1.yaml

# Or submit individual array job:
sbatch -a 5 scripts/xcompact3d_slurm.sh config_case_5.yaml
```

#### 4.3 Resource Request Guidelines (Adjust to Cluster Policies)

| Job Type | Nodes | CPUs/node | Memory/node | Time | Partition | Use Case |
|----------|-------|-----------|-------------|------|-----------|----------|
| Debug/Quick test | 1 | 8-16 | 32-64G | 0:15:00 - 1:00:00 | compute/debug | Verify compilation, short runs |
| Medium case | 2-4 | 8-16 | 64G | 1-3 days | compute | Standard CFD simulations |
| Large production | 8-16+ | 16-32 | 128G+ | 5-7 days | compute/long | High-resolution or multi-phase cases |
| GPU-accelerated | 2-4 | 8-16 | 64-128G | Variable | gpu/gpu_long | If GPU-enabled build used |

**GPU-Specific Directives (if applicable):**
```bash
# Request specific number of GPUs per node
#SBATCH --partition=gpu
#SBATCH --gres=gpu:2          # 2 GPUs per node
#SBATCH --mem=64g             # Plus host memory for CUDA contexts

# For multi-GPU per rank (advanced):
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=8   # Total MPI ranks
#SBATCH --cpus-per-task=16    # For each rank to prepare data + GPU ops
```

---

## Phase 5: Job Monitoring, Log Analysis, and Validation

### Specialist Agent
- **Agent Type**: `General-Purpose` (for job status queries and log parsing)
- **Hardware Resources**: Login node with Slurm access (no GPU required for monitoring)
- **Expected Token Usage**: ~2,000 tokens for status checks and log analysis

### Dependencies on Other Stages
- No build dependencies; can run anytime after Phase 4.2 (job submission)

### Subtasks and Commands

#### 5.1 Check Job Status (`squeue`)

**Basic Status Check:**
```bash
# Show all jobs in the system (including your jobs)
squeue -u $USER

# Or show all jobs with detailed format:
squeue -o "%25JobID %-8User %-8Group %6NCPUS %20JobName %10Partition %8State"

# Check specific job(s):
squeue -j <JOBID>
```

**Status Interpretation:**
| Status Code | Meaning | Action |
|-------------|---------|--------|
| R | Running | Job is executing on allocated resources |
| PD | Pending | Job is waiting for resource allocation (e.g., partition availability) |
| CG | Completing | Job finished but tasks are still cleaning up |
| CD | Caching | Job finished and output being cached |
| CF | Completed | Job completed successfully |
| CA | Cancelled | Job was cancelled by user or system |
| CG/CANCELLED | Cancelled | Job was cancelled |

#### 5.2 View Job Logs (`tail`, `less`)

**Standard Output:**
```bash
# View latest lines from job standard output (follow like 'tail -f')
tail -f slurm-<JOBID>.out
tail -n 100 slurm-<JOBID>.out   # Show last 100 lines
less slurm-<JOBID>.out           # Page through log

# If job script redirect output to custom location:
cat logs/xcompact3d_<JOBID>.out | tail -100
```

**Standard Error (often contains MPI errors, compilation errors, etc.):**
```bash
tail -f slurm-<JOBID>.err
tail -n 50 slurm-<JOBID>.err
less slurm-<JOBID>.err

# Filter for error patterns:
grep -i "error\|fatal\|abort\|fail" slurm-<JOBID>.err | head -20
```

**Combined output (if append-rm was used in script):**
```bash
tail -f $(ls -t logs/*.out | head -1) 2>/dev/null || \
    tail -f slurm-<JOBID>.out
```

#### 5.3 Job Statistics (`sstat`)

**Resource Usage Statistics:**
```bash
# Show job statistics (elapsed time, total run time, CPU hours, etc.)
sstat -j <JOBID>

# Detailed output format:
sstat -j <JOBID> -o "%6JobID %-10User %8Elapsed%15Total_time %9RealElapsed"

# For array jobs (show per-task):
sstat -J <JOBID>
```

#### 5.4 Validation Checklist

**Post-Run Validation Commands:**

| Check | Command | Expected Outcome |
|-------|---------|------------------|
| **Executable runs** | `./incompact3d --help` | Shows usage/help text |
| **Output files created** | `ls -lh results/` or `ls -lh *.out` | Non-zero size files in expected directory |
| **MPI working correctly** | Check for MPI errors in `.err` log | No "error communicating with rank" messages |
| **Input file consumed** | Check output for input processing confirmation | Logs show config/input being read |
| **No segmentation faults** | `grep -i "segfault\|core dump\|abort" slurm-*.err` | No fatal errors found |
| **Simulation convergence** (if applicable) | Examine output plots/values | Physical quantities reasonable (check with domain knowledge) |

**Validation Script:**
```bash
#!/usr/bin/env bash
# validation.sh - Post-run verification for XCompact3D job

JOB_ID=${1:-$(squeue -u $USER | grep xcompact3d | awk '{print $1}') || echo "N/A"}
OUTPUT_FILE="slurm-${JOB_ID}.out"
ERROR_FILE="slurm-${JOB_ID}.err"

echo "========== XCompact3D Job Validation =========="
echo "Job ID: $JOB_ID"
echo ""

# Check job is completed or running
echo "=== Job Status ==="
squeue -j $JOB_ID

# Check output file exists and has content
if [ -f "$OUTPUT_FILE" ]; then
    echo "" >&2
    echo "=== Output File Info ===" >&2
    ls -lh "$OUTPUT_FILE"
    echo "Last 30 lines of output:" >&2
    tail -n 30 "$OUTPUT_FILE"
else
    echo "" >&2
    echo "WARNING: Standard output file not found!" >&2
fi

# Check for critical errors in stderr
echo "" >&2
echo "=== Error Analysis ===" >&2
if [ -f "$ERROR_FILE" ]; then
    ERROR_COUNT=$(grep -ci "error\|fatal\|fail" "$ERROR_FILE")
    echo "Error keywords found: $ERROR_COUNT"

    if [ $ERROR_COUNT -gt 0 ]; then
        echo "" >&2
        echo "Top error lines:" >&2
        grep -i "error\|fatal\|fail" "$ERROR_FILE" | head -15
    else
        echo "No critical errors found in stderr."
    fi
else
    echo "Standard error file not found (may be redirected elsewhere)."
fi

# Check for output data
echo "" >&2
echo "=== Output Data Check ===" >&2
ls -lh results/ 2>/dev/null | head -5 || \
    ls -lh *.dat *.out 2>/dev/null | head -5 || \
    echo "No obvious output files found."

# Summary
echo "" >&2
echo "========== Validation Summary ==========" >&2
if [ $ERROR_COUNT -eq 0 ]; then
    echo "Status: PASSED (no critical errors detected)"
else
    echo "Status: REVIEW NEEDED ($ERROR_COUNT error keywords found)"
fi
```

#### 5.5 Common Issues and Troubleshooting

**Issue 1: MPI Initialization Errors**
```bash
# Symptom: "error communicating with rank", "MPI initialization failed"
# Solutions:
1. Check that OpenMPI is loaded: which mpich
2. Verify MPI environment: export I_MPI_DEBUG=4 (for Intel MPI)
3. Try different MPI library in CMake configuration: -DMPI_LIBRARY=openmpi
```

**Issue 2: Memory Allocation Failures**
```bash
# Symptom: "Cannot allocate memory", out-of-memory errors
# Solutions:
1. Increase --mem directive in sbatch script
2. Request more nodes with --nodes=N --mem=64g (adds ~256GB total)
3. Check if application needs --mem-per-cpu instead of --mem
```

**Issue 3: GPU Not Detected (if applicable)**
```bash
# Symptom: "CUDA driver not found", "no devices"
# Solutions:
1. Request gpu partition: sbatch -p gpu scripts/xcompact3d_slurm.sh
2. Use correct gres directive: --gres=gpu:2 (or --gpus-per-node=2)
3. Check CUDA_VISIBLE_DEVICES is empty or set correctly
```

**Issue 4: Job Pending/Resource Not Available**
```bash
# Symptom: Job remains in PD state for extended time
# Solutions:
1. Try smaller node count first
2. Try different partition (e.g., 'compute' instead of 'gpu')
3. Check if requested GPUs are unavailable (nvidia-smi on compute nodes)
```

---

## Deployment Summary

| Stage | Specialist Agent | Hardware Required | Token Budget | Dependencies | Duration (est.) |
|-------|-----------------|-------------------|--------------|--------------|-----------------|
| Phase 1: Source Acquisition | General-Purpose | Standard node + network | ~5,000 | None | 30-60 min |
| Phase 2: Build Config & Compile | General-Purpose | Standard node with build tools | ~10,000 | Phase 1.3 | 1-4 hours (depends on case size) |
| Phase 3: Slurm Discovery | General-Purpose | Login node | ~3,000 | None (parallelizable) | 5-10 min |
| Phase 4: Script Generation & Submit | General-Purpose | Login node + write access | ~2,500 | Phases 1.3, 2.2 | 5-10 min |
| Phase 5: Monitoring & Validation | General-Purpose | Login node | ~2,000 | After job submission | Ongoing during job run |

**Total Estimated Token Usage**: ~22,500 tokens (excluding actual simulation computation)

**Critical Files Produced:**
1. `/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/xcompact3d_source/Incompact3d/build/incompact3d` - Main executable
2. `/home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir/scripts/xcompact3d_slurm.sh` - Slurm batch script
3. Output logs in `logs/` directory

**Key Environment Variables:**
| Variable | Purpose | Recommended Value |
|----------|---------|-------------------|
| `OMP_NUM_THREADS` | OpenMP threading per MPI rank | 1 (for hybrid MPI/CUDA) |
| `CUDA_VISIBLE_DEVICES` | GPU visibility to application | Empty string or specific device IDs |
| `MPI_LIBRARY` | MPI implementation used in build | openmpi, mpich, or intelmpi |

---

## Appendix: Quick Start Commands

### Complete Deployment Pipeline (Sequential):
```bash
# Phase 1: Download source code
cd /home/jye/publications/pythia/motivation_tests/cases/case_001_xcompact3d_deployment/WorkingDir
git clone https://github.com/xcompact3d/Incompact3d.git

# Phase 1.2: Install dependencies (if on cluster with modules)
module purge
module load openmpi/4.1.2 gcc/12.3 cmake/3.26
cmake -S .. -B build -DCMAKE_BUILD_TYPE=Release

# Phase 2: Build application
cd build && cmake --build . -j$(nproc)
cd ..

# Phase 3 & 4: Create and run batch job (script shown in main document)
sbatch scripts/xcompact3d_slurm.sh

# Phase 5: Monitor job status
squeue -u $USER
tail -f slurm-*.out
```

### Parallel Execution Note:
Phases 1, 2, and 3 are independent and can be parallelized if multiple agents are available. Phases 4 and 5 require completion of prior phases.

---

*Plan generated for XCompact3D deployment on Slurm-managed HPC cluster.*
*Document version: 1.0 - Deployment Guide for Scientific Computing Orchestration System*

