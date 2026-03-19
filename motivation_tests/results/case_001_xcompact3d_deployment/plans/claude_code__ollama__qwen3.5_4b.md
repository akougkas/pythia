---
case: case_001_xcompact3d_deployment
framework: claude_code
model: qwen3.5:4b
provider: ollama
session_id: 6353befa-617e-4ba0-b7b1-b85248b19c34
duration_ms: 188455
duration_wall_s: 193.6
cost_usd: 3.6172000000000013
num_turns: 6
timestamp: 2026-03-19T13:51:41.479075+00:00
error: None
---

# Plan

# XCompact3D Deployment Plan on HPC Cluster (Slurm)

**Date**: 2026-03-19
**Repository**: https://github.com/xcompact3d/Incompact3d
**Working Directory**: /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

---

## Context

This deployment plan provides a structured approach for deploying the XCompact3D application on an HPC cluster managed by SLURM. The plan decomposes the deployment into distinct stages, assigns specialized agent responsibilities, specifies hardware resource requirements for each stage, and includes detailed command documentation for each subtask.

---

## Stage 1: Source Code Acquisition and Dependency Fetching

### Objective
Download the XCompact3D source code from the upstream repository and fetch all required dependencies.

### Specialist Agent
**Name**: `CodeAcquisitionAgent`
**Description**: Agent responsible for downloading and analyzing source code repositories.

### Hardware Resources
- **CPU**: 2 cores (lightweight operations)
- **Memory**: 4 GB
- **Storage**: 10 GB (for source files and dependencies)
- **Network**: High-bandwidth download capability

### Expected Token Usage
- **1,000-2,000 tokens** for the download and initial analysis phase

### Dependencies
- None (this is the first stage)

### Commands to Execute

#### Step 1.1: Clone the Repository
```bash
# Clone the XCompact3D repository
git clone --depth 1 https://github.com/xcompact3d/Incompact3d.git XCompact3D

# Change to the repository directory
cd XCompact3D
```

#### Step 1.2: Analyze Repository Structure
```bash
# Explore repository structure
find . -type f -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" -o -name "*.txt" -o -name "*.md" | sort

# List directories
ls -la

# View README if available
cat README.md 2>/dev/null || echo "No README found"
```

#### Step 1.3: Fetch Dependencies
```bash
# Check for requirements.txt, package.json, or similar dependency files
find . -name "requirements*.txt" -o -name "package*.json" -o -name "pom.xml" -o -name "setup.py" -o -name "Cargo.toml" 2>/dev/null

# Install Python dependencies (if applicable)
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null

# Install package.json dependencies (if applicable)
npm install 2>/dev/null

# Install C++ dependencies if CMakeLists.txt exists
cmake --help 2>/dev/null
```

### Output
- Repository cloned to `XCompact3D` directory in WorkingDir
- All dependencies installed and documented
- Initial code analysis complete

---

## Stage 2: Code Understanding, Build Configuration, and Compilation

### Objective
Read and understand the XCompact3D source code, configure the build system, install required libraries, and compile the application.

### Specialist Agent
**Name**: `BuildConfigurationAgent`
**Description**: Agent responsible for analyzing build systems, generating build configurations, and handling compilation.

### Hardware Resources
- **CPU**: 4 cores (build and compilation operations)
- **Memory**: 8 GB (for compilation)
- **Storage**: 50 GB (for build artifacts and intermediate files)

### Expected Token Usage
- **2,000-4,000 tokens** for build analysis and configuration

### Dependencies
- **Stage 1**: Source code downloaded and dependencies fetched

### Commands to Execute

#### Step 2.1: Read and Understand Source Code
```bash
# View repository structure
tree -L 3 -I 'build|bin|tmp' .

# List all source files
find . -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" \) | sort

# View build configuration files
ls -la CMakeLists.txt 2>/dev/null
cat CMakeLists.txt 2>/dev/null || echo "No CMakeLists.txt found"

ls -la Makefile 2>/dev/null
cat Makefile 2>/dev/null || echo "No Makefile found"
```

#### Step 2.2: Identify Required Libraries
```bash
# Search for include paths and library references
grep -r "include" --include="*.cmake" --include="Makefile" --include="*.txt" . 2>/dev/null | head -30

# Check for common HPC/Scientific computing libraries
grep -r "omp" . --include="*.cmake" --include="Makefile" 2>/dev/null | head -10
grep -r "Eigen" . --include="*.cmake" --include="Makefile" 2>/dev/null | head -10
grep -r "BLAS" . --include="*.cmake" --include="Makefile" 2>/dev/null | head -10
grep -r "FFT" . --include="*.cmake" --include="Makefile" 2>/dev/null | head -10
grep -r "MPI" . --include="*.cmake" --include="Makefile" 2>/dev/null | head -10
```

#### Step 2.3: Install Required Libraries
```bash
# Install standard scientific computing libraries (examples)

# OpenMPI (if required)
apt-get install -y libopenmpi-dev openmpi-bin

# OpenBLAS (if required)
apt-get install -y libopenblas-dev

# FFTW (if required)
apt-get install -y libfftw3-dev

# CUDA (if GPU support required)
# Follow NVIDIA CUDA installation guide for your distribution

# Boost (if required)
apt-get install -y libboost-all-dev

# Install from system package manager (adjust for distribution)
# Example for Ubuntu/Debian:
apt-get update && apt-get install -y <library-name>

# Verify installations
dpkg -l | grep -E 'openmpi|openblas|fftw|boost|cuda'
```

#### Step 2.4: Configure Build
```bash
# Create a build directory
mkdir -p build && cd build

# Configure CMake build with appropriate options
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DMPI_CXX_FLAGS="-I/usr/include/openmpi" \
  -DMPI_C_FLAGS="-I/usr/include/openmpi" \
  -DENABLE_TESTS=ON \
  -DENABLE_BENCHMARKS=ON

# Alternative: Configure Makefile directly
make config 2>/dev/null || echo "Using default config"
```

#### Step 2.5: Compile the Application
```bash
# Compile with make (or ninja if available)
make -j$(nproc)

# Or compile with CMake
make -j$(nproc)

# Verify compilation success
make clean && make -j$(nproc)
```

### Output
- Source code understood and documented
- Build configuration complete
- All required libraries installed
- Application compiled successfully
- Executable generated in `build/` or `bin/` directory

---

## Stage 3: SLURM Cluster Query and Resource Assessment

### Objective
Query available nodes, partitions, GPUs, and network topology on the HPC cluster to understand resource availability.

### Specialist Agent
**Name**: `ClusterInfoAgent`
**Description**: Agent responsible for querying cluster status and resource availability via SLURM.

### Hardware Resources
- **CPU**: 2 cores (query operations only)
- **Memory**: 4 GB
- **Network**: Read-only access to cluster resources
- **Storage**: Minimal (no local storage needed)

### Expected Token Usage
- **500-1,500 tokens** for SLURM queries and analysis

### Dependencies
- **Stage 2**: Build configuration complete (application compiled)

### Commands to Execute

#### Step 3.1: Query Available Partitions
```bash
# List all available SLURM partitions/schedulers
sinfo --format="%N %n %A %M %P %C %e %T %c %D %u %q"

# Display partition details (all partitions)
sinfo -p '*' -f "%N %N %T %c %D %u %q"

# Query specific partitions (adjust names)
sinfo -p default,cert,highmem -f "%N %n %T %c"
```

#### Step 3.2: Check Node Availability
```bash
# List available nodes in current partition
sinfo -C "CPU" --format="%N %n"

# Check for GPU nodes
sinfo -t "GPU" --format="%N %n %a %d"

# Check for GPU-capable partitions
sinfo --format="%N %n %a %d" | grep -i gpu
```

#### Step 3.3: Query GPU Resources
```bash
# List available GPUs
slurmctl list gpu
sinfo --format="%N %n %a %d" --partition=*

# Check GPU type and capabilities
scontrol show hostname
mpstat -p 1
```

#### Step 3.4: Network Topology Assessment
```bash
# Check cluster topology
scontrol show cluster

# View cluster configuration
cat /etc/slurm/slurm.conf 2>/dev/null || scontrol show config

# Check available networks
sinfo -N "*" --format="%N %n"

# Verify network connectivity between nodes
ping -c 1 <node-1> <node-2> 2>/dev/null || echo "Network test skipped"
```

### Output
- Available partitions identified
- Node availability status
- GPU resources mapped
- Network topology understood

---

## Stage 4: SLURM Batch Script Creation and Submission

### Objective
Create a fully configured SLURM batch script with appropriate resource requests and submit the job.

### Specialist Agent
**Name**: `SLURMBatchScriptAgent`
**Description**: Agent responsible for generating and submitting SLURM batch scripts.

### Hardware Resources
- **CPU**: 2 cores (script generation)
- **Memory**: 4 GB
- **Storage**: 1 GB (for batch scripts)

### Expected Token Usage
- **1,000-2,000 tokens** for script generation and submission

### Dependencies
- **Stage 3**: Cluster information queried and understood

### Commands to Execute

#### Step 4.1: Design Batch Script Template
```bash
# Create batch script directory
mkdir -p scripts && cd scripts

# Initialize batch script with template
cat > run_xcompact3d.slurm << 'EOF'
#!/bin/bash
#SBATCH --job-name=XCompact3D
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --open-mode=append
#SBATCH --output=xcompact3d_%j.out
#SBATCH --error=xcompact3d_%j.err

# Module environment setup
module load openmpi/4.1.4
module load cuda/11.8
module load python/3.10

# Set environment variables
export OMP_NUM_THREADS=4
export OPENMPI_ALLOW_RSH="*.*"

# Source working directory
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

# Source environment if available
source /path/to/your/environment.sh 2>/dev/null || true

# Launch the application
./build/xcompact3d_application [args]
EOF
```

#### Step 4.2: Customize Script Parameters
```bash
# Adjust resource requests based on Stage 3 findings
# Replace with actual partition, nodes, GPU requirements

# Example customization based on cluster info:
sed -i 's/%SBATCH --time=24:00:00/%SBATCH --time=24:00:00/' run_xcompact3d.slurm
sed -i 's/%SBATCH --nodes=1/%SBATCH --nodes=2/' run_xcompact3d.slurm  # Adjusted
```

#### Step 4.3: Submit the Job
```bash
# Validate SLURM syntax
sbatch --dry-run run_xcompact3d.slurm

# Submit the batch job
sbatch run_xcompact3d.slurm

# Capture job ID
echo "Job ID: $SLURM_JOB_ID"
```

### Output
- Customized SLURM batch script saved
- Job submitted successfully
- Job ID captured

---

## Stage 5: Job Monitoring, Log Analysis, and Validation

### Objective
Check job status, analyze logs, and validate that the application started correctly.

### Specialist Agent
**Name**: `JobMonitorAgent`
**Description**: Agent responsible for monitoring job status and analyzing logs.

### Hardware Resources
- **CPU**: 2 cores (log analysis)
- **Memory**: 4 GB
- **Storage**: 10 GB (for log files)

### Expected Token Usage
- **1,000-2,000 tokens** for log analysis and validation

### Dependencies
- **Stage 4**: Job submitted and running

### Commands to Execute

#### Step 5.1: Monitor Job Status
```bash
# Check job status
scontrol show job <job-id>
squeue -j <job-id>

# Watch job status in real-time (non-blocking)
tail -f /path/to/<job-id>.err
watch -n 5 "scontrol show job <job-id>"
```

#### Step 5.2: Analyze Log Output
```bash
# View logs in real-time
tail -f xcompact3d_<job-id>.err

# Search for specific keywords in log
grep -i "error" xcompact3d_<job-id>.err
grep -i "completed" xcompact3d_<job-id>.err
grep -i "started" xcompact3d_<job-id>.err

# Check for successful startup
grep -E "success|started|initialized" xcompact3d_<job-id>.err
```

#### Step 5.3: Validate Application Start
```bash
# Check application output
tail -100 xcompact3d_<job-id>.out

# Validate compilation
if grep -q "successfully compiled" xcompact3d_<job-id>.out; then
    echo "Compilation successful"
else
    echo "Compilation may have issues"
fi

# Validate runtime
if grep -q "runtime started\|application ready" xcompact3d_<job-id>.err; then
    echo "Application started successfully"
else
    echo "Application may not have started correctly"
fi
```

### Output
- Job status monitored and documented
- Logs analyzed
- Application startup validated

---

## Stage 6: Error Handling and Recovery

### Objective
Document procedures for handling common failures and recovering from them.

### Specialist Agent
**Name**: `ErrorHandlingAgent`
**Description**: Agent responsible for handling job failures and implementing recovery procedures.

### Hardware Resources
- **CPU**: 2 cores (analysis)
- **Memory**: 4 GB
- **Storage**: 5 GB (for recovery logs)

### Expected Token Usage
- **500-1,000 tokens** for error handling procedures

### Dependencies
- **Stage 5**: Validation complete (or if validation fails)

### Procedures to Document

#### Step 6.1: Job Timeout Handling
```bash
# If job times out, cancel and requeue
scontrol kill <job-id>
sbatch run_xcompact3d.slurm

# Check if job is abandoned
scontrol show job <job-id>
```

#### Step 6.2: Failed Compilation Handling
```bash
# If compilation fails, clean and rebuild
make clean
rm -rf build/*
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

#### Step 6.3: Memory Limit Exceeded Handling
```bash
# Reduce memory request
# Edit batch script: sedit run_xcompact3d.slurm
# Change: --mem=16G to --mem=8G

# Requeue job
sbatch run_xcompact3d.slurm
```

---

## Specialist Agent Summary

| Stage | Agent Name | Primary Responsibility |
|-------|------------|------------------------|
| 1 | CodeAcquisitionAgent | Download repository, fetch dependencies |
| 2 | BuildConfigurationAgent | Analyze build config, install libraries, compile |
| 3 | ClusterInfoAgent | Query SLURM nodes, partitions, GPUs |
| 4 | SLURMBatchScriptAgent | Create and submit batch script |
| 5 | JobMonitorAgent | Monitor jobs, analyze logs, validate |
| 6 | ErrorHandlingAgent | Handle failures, implement recovery |

---

## Execution Summary

| Stage | Expected Duration | Expected Tokens | Priority |
|-------|-------------------|-----------------|----------|
| 1 | 5-10 minutes | 1,000-2,000 | High |
| 2 | 15-30 minutes | 2,000-4,000 | High |
| 3 | 5-10 minutes | 500-1,500 | Medium |
| 4 | 2-5 minutes | 1,000-2,000 | Medium |
| 5 | 10-30 minutes | 1,000-2,000 | Critical |
| 6 | On-demand | 500-1,000 | High |

**Total Estimated Tokens**: 8,000-12,000 tokens
**Total Estimated Time**: 40-85 minutes (excluding job runtime)

---

## Files to Modify/Copy

| File/Directory | Purpose |
|----------------|---------|
| `XCompact3D/` | Cloned repository directory |
| `XCompact3D/build/` | Compiled artifacts |
| `scripts/run_xcompact3d.slurm` | SLURM batch script |
| `xcompact3d_<job-id>.out` | Job output log |
| `xcompact3d_<job-id>.err` | Job error log |

---

## Verification Steps

1. **Pre-deployment verification**:
   ```bash
   # Verify repository downloaded correctly
   cd XCompact3D && git remote -v

   # Verify dependencies installed
   pip3 --version && cmake --version

   # Verify compilation
   ./build/xcompact3d_application --version
   ```

2. **Post-deployment verification**:
   ```bash
   # Verify job completed successfully
   scontrol show job <job-id>

   # Check output for success indicators
   grep "success\|completed\|ready" xcompact3d_<job-id>.out

   # Validate output files produced
   ls -lh xcompact3d_<job-id>.out
   ```

---

**Document Created**: 2026-03-19
**Prepared by**: Deployment Planning System
**Version**: 1.0

