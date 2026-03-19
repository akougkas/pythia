---
case: case_001_xcompact3d_deployment
framework: claude_code
model: qwen3.5:9b
provider: ollama
session_id: 1b30ae9e-cb7a-43d0-894b-e164fe68c980
duration_ms: 57981
duration_wall_s: 60.7
cost_usd: 0.60415
num_turns: 5
timestamp: 2026-03-19T13:50:09.534683+00:00
error: None
---

# Plan

# XCompact3D HPC Cluster Deployment Plan

## Context

This document provides a comprehensive deployment plan for running the **XCompact3D** application (a 3D induction heating and electromagnetic simulation code) on an HPC cluster managed by **Slurm**. The plan covers all stages from source acquisition through deployment, validation, and job execution.

The working directory for this deployment is:
```
/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
```

---

## Stage 1: Source Code Acquisition and Dependencies

### Specialist Agent: `general-purpose` (Source Code Manager)

### Hardware Resources Required
- **Memory**: 4 GB RAM (for downloading and parsing source files)
- **CPU**: 2 vCPUs
- **Storage**: 50 GB temporary disk space for source extraction

### Token Usage Estimate: ~8,000 tokens

### Subtasks

#### 1.1 Clone XCompact3D from Upstream Repository

**Command:**
```bash
git clone https://github.com/xcompact3d/Incompact3d.git XCompact3d_Source
cd XCompact3d_Source
```

#### 1.2 Fetch Dependencies (Libraries and Tools)

**Required Dependencies:**
- MPI library (OpenMPI or MPICH)
- HDF5 library (≥ v1.8.22)
- HDF-EOS library (for I/O operations)
- NetCDF library
- PnetCDF library
- MPI-IO library
- HDF5 driver libraries
- Standard C/C++ development libraries (gcc/g++, make)

**Install Dependencies Command (RHEL/CentOS/Rocky):**
```bash
# For system packages (RHEL-based systems)
module load opensmpi/4.1.5
module load hdf5/1.12.2
module load hdf-eos3/3.3.0
module load netcdf/4.9.2
module load pnetcdf/1.12.5
module load mpich/4.2.0  # optional alternative

# Or install from source if modules unavailable:
sudo yum install -y \
    gcc gcc-c++ \
    make cmake \
    hdf5-devel hdf5-static \
    hdf-eos3-devel \
    netcdf-devel \
    pnetcdf-devel \
    mpich \
    openmpi-devel
```

---

## Stage 2: Source Code Analysis and Build Configuration

### Specialist Agent: `general-purpose` (Build Engineer)

### Hardware Resources Required
- **Memory**: 8 GB RAM
- **CPU**: 4 vCPUs
- **Storage**: 20 GB for build artifacts

### Token Usage Estimate: ~12,000 tokens

### Dependencies: None (depends on Stage 1 completion)

#### 2.1 Explore XCompact3D Source Structure

**Commands:**
```bash
# Navigate to source directory
cd XCompact3d_Source

# Examine build system files
ls -la
cat build/Makefile.in

# Check available compiler wrappers and build options
cat build/Makefile | head -100

# Review the README for build instructions
cat README | head -200
```

#### 2.2 Build and Configure Commands

**Create Build Directory:**
```bash
mkdir -p build_xcompact3d
cd build_xcompact3d
```

**Configure with Compiler and Options:**
```bash
# Using system compiler wrapper (if available)
../build/setup_compiler_wrapper.sh

# Configure the build with Intel or GCC compiler
../build/configure \
    --prefix=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/install_xcompact3d \
    --enable-openmp \
    --with-mpi=/usr/lib64/openmpi \
    CC=mpicc \
    CXX=mpicxx \
    FC=mpif77 \
    F77=mpif77 \
    FCFLAGS="-O3 -DNDEBUG" \
    CFLAGS="-O3 -DNDEBUG"

# Alternative: configure with specific optimization flags
../build/configure \
    --prefix=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/install_xcompact3d \
    --enable-openmp \
    CFLAGS="-O3 -march=native -ffast-math" \
    CXXFLAGS="-O3 -march=native -ffast-math"
```

**Install Required Libraries (if not using modules):**
```bash
# If libraries need to be installed from source:

# HDF5
mkdir -p ~/hdf5-build && cd ~/hdf5-build
cmake -DHDF5_BUILD_SHARED=OFF \
      -DHDF5_BUILD_STATIC=ON \
      -DCMAKE_INSTALL_PREFIX=/usr/local \
      ../hdf5-source
make -j$(nproc)
sudo make install

# OpenMPI
mkdir -p ~/openmpi-build && cd ~/openmpi-build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local \
      -DOPENMI_ENABLE_PMI_LM=ON \
      ../openmpi-source
make -j$(nproc)
sudo make install

# Re-run configure after libraries are installed
cd XCompact3d_Source/build_xcompact3d
../build/configure \
    --prefix=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/install_xcompact3d \
    --enable-openmp \
    CC=mpicc \
    CXX=mpicxx
```

#### 2.3 Compilation Command

```bash
# Compile with optimized parallel build
make -j$(nproc)
```

**Expected output:**
```
Scanning dependencies of target ...
Building CXX object CMakeFiles/XC3D_EXE.dir/main.cc.o
[... compilation output ...]
Built XC3D_EXE
Built XC3D_TEST
```

#### 2.4 Installation Command

```bash
# Install to the designated prefix
make install
```

**Or for local install (no system-wide installation):**
```bash
make -j$(nproc) PREFIX=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/install_xcompact3d install
```

---

## Stage 3: HPC Cluster Topology Discovery

### Specialist Agent: `statusline-setup` (HPC Operations Agent)

### Hardware Resources Required
- **Memory**: 2 GB RAM
- **CPU**: 1 vCPU
- **Storage**: Minimal storage requirements

### Token Usage Estimate: ~5,000 tokens

### Dependencies: None (can run independently in parallel with other stages)

#### 3.1 Query Available Nodes and Partitions

**Slurm Information Commands:**

```bash
# Check available partitions
sinfo

# Show node details for each partition
scontrol show partition

# Show node details
scontrol show cluster

# List all nodes with their state
scontrol show node

# Show job step environment (useful for debugging)
scontrol show jobstep $SLURM_JOB_STEP_ID
```

#### 3.2 GPU Resources Discovery

```bash
# Check for GPU partitions
sinfo -a -o "%N %T %P %O %t"

# List GPU-enabled nodes
scontrol show node | grep -i "gpu"

# Show detailed GPU node info
scontrol show node <nodename> | grep -i "gpu"

# Check GPU availability on cluster
nvidia-smi  # if available on compute nodes

# List GPU types per node
scontrol show partition | grep -i "gpu"
```

#### 3.3 Network Topology Information

```bash
# Show network topology (if Infiniband or similar)
scontrol show node | grep -i "ib0\|network\|lan"

# Show network bandwidth info
cat /proc/cpuinfo | grep -i "bus\|speed"

# Check for specific network partitions
sinfo | grep -i "fast\|highspeed\|ib"
```

---

## Stage 4: Slurm Batch Script Preparation

### Specialist Agent: `general-purpose` (Job Scheduler Specialist)

### Hardware Resources Required
- **Memory**: 4 GB RAM
- **CPU**: 2 vCPUs
- **Storage**: 5 GB for batch script and submission files

### Token Usage Estimate: ~6,000 tokens

### Dependencies: Stage 1 (dependencies installed), Stage 2 (build completed)

#### 4.1 Create Slurm Batch Script

**File:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/XCompact3D_job.slurm`

```slurm
#!/bin/bash
#
# XCompact3D HPC Job Submission Script
# =====================================
#
#SBATCH --job-name=XCompact3D_simulation
#SBATCH --account=your_account          # Replace with your account/project
#SBATCH --email=user@yourdomain.com     # Job completion email
#SBATCH --mail-type=END,FAIL            # Email on job end/failure
#SBATCH --time=04-00:00:00             # Max walltime: 4 hours
#SBATCH --nodes=1                      # Number of nodes
#SBATCH --ntasks=1                     # Number of MPI tasks
#SBATCH --ntasks-per-node=1            # MPI tasks per node
#SBATCH --cpus-per-task=24            # CPU cores per task
#SBATCH --mem=64G                     # Memory per node
#SBATCH --partition=gpu                # Use GPU partition (adjust if needed)
#SBATCH --gpus=1                      # Number of GPUs to use
#SBATCH --output=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_output/%j.out
#SBATCH --error=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_output/%j.err
#SBATCH --signal=duration@95%         # Job termination at 95% walltime
#SBATCH --cpus-per-task=24

# Load required modules (adjust based on cluster configuration)
module load opensmpi/4.1.5
module load hdf5/1.12.2
module load netcdf/4.9.2
module load hdf-eos3/3.3.0
module load pnetcdf/1.12.5

# Set environment variables
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export OMP_PROC_BIND=TRUE
export OMP_PLACES=threads

# Change to working directory
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

# Set environment for MPI/OpenMP
export XC3D_MPIEXEC=srun
export XC3D_EXE=install_xcompact3d/bin/XC3D_EXE

# Run XCompact3D
# Adjust input file path and arguments as needed
$XC3D_MPIEXEC $XC3D_EXE -i XCompact3d_Source/input_file.dat -o XCompact3d_Source/output_files

echo "XCompact3D completed successfully"
```

**Alternative Script for CPU-only jobs (no GPU):**

```slurm
#!/bin/bash
#
# XCompact3D CPU Job Submission Script
# =====================================
#SBATCH --job-name=XCompact3D_cpu
#SBATCH --account=your_account
#SBATCH --email=user@yourdomain.com
#SBATCH --mail-type=END,FAIL
#SBATCH --time=04-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=24
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --partition=compute
#SBATCH --output=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_output/%j.out
#SBATCH --error=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_output/%j.err

module load opensmpi/4.1.5
module load hdf5/1.12.2
module load netcdf/4.9.2
module load hdf-eos3/3.3.0

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
$XC3D_MPIEXEC install_xcompact3d/bin/XC3D_EXE -i input_file.dat
```

#### 4.2 Create Sample Input File

**File:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/input_file.dat`

```text
* Simulation control
* Time step
0.1
* Number of time steps
100
* Output frequency
10
* Physics
  electromagnetics
* Mesh
  uniform 256 256 256
* Boundary conditions
  x: periodic
  y: periodic
  z: fixed
* Sources
  type: current
  location: center
* Output
  write: solution
  write: field
  format: binary
```

---

## Stage 5: Job Submission and Execution

### Specialist Agent: `general-purpose` (Job Scheduler Specialist)

### Hardware Resources Required
- **Memory**: 2 GB RAM
- **CPU**: 1 vCPU
- **Storage**: Minimal storage

### Token Usage Estimate: ~2,000 tokens

### Dependencies: All stages must be complete

#### 5.1 Submit Job

```bash
# Make batch script executable
chmod +x XCompact3D_job.slurm

# Submit the job
sbatch XCompact3D_job.slurm

# Alternative: submit without running first
# sbatch XCompact3D_job.slurm

# Check the output - should return: "Submitted batch job 12345"
```

**Expected output:**
```
Submitted batch job 12345
```

#### 5.2 Submit CPU-only version (if appropriate)

```bash
# For CPU-only simulations
sbatch XCompact3D_cpu_job.slurm
```

---

## Stage 6: Job Monitoring and Validation

### Specialist Agent: `statusline-setup` (Monitoring Agent)

### Hardware Resources Required
- **Memory**: 2 GB RAM
- **CPU**: 1 vCPU
- **Storage**: Minimal storage

### Token Usage Estimate: ~3,000 tokens

### Dependencies: None (can run in parallel with monitoring tasks)

#### 6.1 Check Job Status

```bash
# Check job status
squeue -u $USER

# Check specific job
squery -j $JOB_ID

# Alternative status check
sacct -j $JOB_ID -o JobID,JobName,State,Elapsed,ExitCode

# Detailed job information
scontrol show job $JOB_ID

# Show job steps
scontrol show jobstep $SLURM_JOB_STEP_ID
```

#### 6.2 Monitor Job Output

```bash
# Tail output file in real-time
tail -f slurm_output/%j.out

# Monitor error output
tail -f slurm_output/%j.err

# View last 50 lines
tail -n 50 slurm_output/%j.out

# View entire job output
cat slurm_output/%j.out

# Search for specific messages
grep -i "error\|warning\|fatal" slurm_output/%j.out

# Check for successful completion
grep -i "completed\|finished\|success" slurm_output/%j.out
```

#### 6.3 Validate Application Startup

```bash
# Check if output files were created
ls -la output_files/

# Check output file sizes (should be non-zero if simulation produced results)
du -sh output_files/*

# Examine output file headers
head -20 output_files/solution.h5

# Check for expected XCompact3D diagnostic messages in output
grep -E "XCompact3D|simulation|time|step" slurm_output/%j.out

# Verify simulation completed without errors
grep -i "ERROR\|FATAL\|failed" slurm_output/%j.out || echo "No errors found"
```

#### 6.4 Check Memory and CPU Usage

```bash
# While job is running (if monitoring node has access)
sacct -j $JOB_ID -o JobID,JobName,MaxRSS,Elapsed

# Check for memory errors in slurmctld
sacct -j $JOB_ID -o JobID,ExitCode
```

#### 6.5 Common Validation Checks

```bash
# 1. Verify job completed successfully
if [ -f slurm_output/%j.out ] && grep -q "completed" slurm_output/%j.out; then
    echo "Job completed successfully"
else
    echo "Job may have issues - check error file"
fi

# 2. Check exit code
sacct -j $JOB_ID -o JobID,ExitCode

# 3. Verify output files exist and have content
for f in output_files/*; do
    if [ -s "$f" ]; then
        echo "$f exists and has content: $(stat -c%s "$f") bytes"
    else
        echo "WARNING: $f is empty or missing"
    fi
done

# 4. List output files
ls -lh output_files/
```

---

## Stage Summary and Parallel Execution

### Stage Dependencies Graph

```
Stage 1 (Source) ┐
                  ├─→ Stage 4 (Batch Script) ─→ Stage 5 (Submit) ─→ Stage 6 (Monitor)
Stage 2 (Build) ─┘

Stage 3 (Topology) ←─ Independent (can run in parallel with all stages)
```

### Parallel Execution Strategy

1. **Stage 1** (Source) and **Stage 2** (Build) should run in parallel if dependencies allow
2. **Stage 3** (Topology) can run independently in parallel with other stages
3. **Stage 4** (Batch Script) depends on completed Stages 1 and 2
4. **Stage 5** (Submit) depends on Stage 4
5. **Stage 6** (Monitor) runs throughout Stages 5-7

### Total Resource Requirements Summary

| Stage | Agent Type | Memory | CPU | Storage | Tokens | Parallelizable |
|-------|------------|--------|-----|---------|--------|----------------|
| 1 | Source Code Manager | 4 GB | 2 vCPU | 50 GB | 8K | Yes |
| 2 | Build Engineer | 8 GB | 4 vCPU | 20 GB | 12K | Yes |
| 3 | HPC Ops Agent | 2 GB | 1 vCPU | Minimal | 5K | Yes |
| 4 | Job Scheduler Specialist | 4 GB | 2 vCPU | 5 GB | 6K | No |
| 5 | Job Scheduler Specialist | 2 GB | 1 vCPU | Minimal | 2K | No |
| 6 | Monitoring Agent | 2 GB | 1 vCPU | Minimal | 3K | Continuous |

**Total estimated tokens:** ~36,000 tokens

---

## Quick Reference Commands

### Source and Build
```bash
git clone https://github.com/xcompact3d/Incompact3d.git
cd Incompact3d
mkdir build_xcompact3d && cd build_xcompact3d
../build/configure --prefix=<install-dir> --enable-openmp
make -j$(nproc)
make install
```

### Slurm Status
```bash
sinfo
scontrol show node
squeue -u $USER
sacct -j <jobid>
```

### Job Monitoring
```bash
sbatch <job_script>
squeue -u $USER
tail -f slurm_output/%j.out
```

---

## Notes and Considerations

1. **Module loading**: Adjust module commands based on your specific HPC cluster's available modules
2. **GPU support**: Ensure GPU drivers are loaded and accessible from Slurm nodes
3. **Memory**: Adjust `--mem` and `--cpus-per-task` based on simulation size
4. **Time**: Adjust `--time` based on expected simulation duration
5. **Account**: Update `--account` with your cluster's project/account identifier
6. **Error handling**: Review `%j.err` for any compilation or runtime errors
7. **Input files**: Customize input file parameters based on your simulation requirements

---

## Appendix: Troubleshooting Checklist

### Common Issues and Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| MPI not found | "cannot find mpi.h" | Load OpenMPI module or install MPI |
| HDF5 errors | "hdf5 library not found" | Load hdf5 module or install from source |
| Memory exceeded | Job killed by SLURM | Increase `--mem` in batch script |
| GPU not detected | "cuda error" | Load CUDA/nvidia modules, verify GPU access |
| OpenMP not found | "omp_get_max_threads" error | Set `export OMP_NUM_THREADS=...` |
| Compilation fail | GCC/MPICH mismatch | Ensure consistent compiler/toolchain |

### Getting Help
```bash
# Ask Slurm administrator
sinfo --help
scontrol --help
sacct --help
```

---

*End of Deployment Plan Document*

