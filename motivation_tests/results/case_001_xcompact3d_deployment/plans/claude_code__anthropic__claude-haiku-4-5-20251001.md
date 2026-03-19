---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: 4a59f9c5-c218-468a-b90f-cdaa90efbd25
duration_ms: 110015
duration_wall_s: 113.3
cost_usd: 0.12369569999999999
num_turns: 5
timestamp: 2026-03-19T13:48:18.297837+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment Plan

## Context

This plan describes the complete deployment of the XCompact3D (Incompact3d) application on an HPC cluster managed by Slurm. XCompact3D is a high-performance, compact finite difference solver for Navier-Stokes equations, commonly used in scientific computing for turbulence simulations. This plan decomposes the deployment into five distinct stages with parallel-capable subtasks, assigns specialist agents to each component, and documents exact commands, scripts, and resource requirements.

---

## Architecture Overview

The deployment follows a sequential pipeline with internal parallelization opportunities:

```
Stage 1: Repository Setup & Dependencies (can parallelize subtasks)
    ↓
Stage 2: Code Analysis & Build Documentation
    ↓
Stage 3: HPC Environment Discovery
    ↓
Stage 4: Slurm Batch Script Preparation
    ↓
Stage 5: Job Submission & Monitoring
```

---

## Stage 1: Download & Dependency Management

### 1.1: Clone XCompact3D Repository

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 2 GB
- Storage: 10 GB free (source code ~500 MB)
- Network: Git access to GitHub required

**Estimated Token Usage:** 1,500-2,000 tokens

**Task Description:**
Download the XCompact3D source code from the upstream repository and document the exact commit/version.

**Commands to Execute:**
```bash
# Navigate to working directory
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

# Clone the repository
git clone https://github.com/xcompact3d/Incompact3d.git
cd Incompact3d

# Document the current state
echo "=== Repository Information ===" > repo_info.txt
git log --oneline -1 >> repo_info.txt
git describe --tags --always >> repo_info.txt
git branch -v >> repo_info.txt
```

**Dependencies:** None (no upstream dependencies for this subtask)

**Output Artifacts:**
- `Incompact3d/` directory with full source tree
- `repo_info.txt` with version information

---

### 1.2: Identify Build Dependencies

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 1 GB
- Storage: 1 GB
- Network: Not required

**Estimated Token Usage:** 2,000-2,500 tokens

**Task Description:**
Analyze XCompact3D source code to identify all build-time and runtime dependencies, check documentation files.

**Commands to Execute:**
```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

# Examine CMakeLists.txt or Makefile
ls -la | grep -i make
cat CMakeLists.txt 2>/dev/null || cat Makefile 2>/dev/null || echo "No build config found"

# Check README for dependencies
cat README.md | head -100

# Look for requirements files
find . -name "requirements*.txt" -o -name "*.yaml" -o -name "*.yml" | head -20

# Examine source for common library imports
grep -r "^use\|^#include\|import" src/ 2>/dev/null | grep -i "mpi\|lapack\|blas\|fftw\|hdf5" | head -20
```

**Dependencies:** Depends on Stage 1.1 (Repository cloning)

**Output Artifacts:**
- `dependency_analysis.txt` with identified libraries and versions
- Notes on compiler requirements (Fortran compiler, likely)

---

### 1.3: Document Installation Commands

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 1 GB
- Storage: 2 GB
- Network: Package manager access required

**Estimated Token Usage:** 2,000-3,000 tokens

**Task Description:**
Create comprehensive instructions for installing all required libraries and build tools on the target HPC cluster.

**Commands to Document:**
```bash
# Typical HPC environment setup (module-based systems)

# Check available modules
module avail

# Load required compilers and libraries (example for common HPC stack)
module load gcc/11.2.0           # or Intel/PGI compiler
module load openmpi/4.1.2        # MPI implementation
module load fftw/3.3.10          # FFT library
module load hdf5/1.12.1          # I/O library
module load lapack/3.10.0        # Linear algebra

# If manual installation needed:
# Install via Spack (HPC package manager)
spack install fftw@3.3.10 %gcc@11.2.0 ~mpi
spack install hdf5@1.12.1 %gcc@11.2.0 +fortran +mpi
spack load fftw hdf5

# Or via apt (if not HPC cluster)
apt-get install libfftw3-dev libhdf5-dev liblapack-dev libblas-dev

# Or via Homebrew (macOS)
brew install fftw hdf5 lapack
```

**Dependencies:** Depends on Stage 1.2 (Dependency identification)

**Output Artifacts:**
- `install_dependencies.sh` - executable script for all installations
- `module_load_commands.txt` - HPC module commands

---

## Stage 2: Code Analysis & Build Documentation

### 2.1: Analyze XCompact3D Source Code Structure

**Specialist Agent:** `Explore` (medium thoroughness)
**Hardware Resources:**
- CPU: 4 cores
- Memory: 4 GB
- Storage: 2 GB
- Network: Not required

**Estimated Token Usage:** 3,000-4,000 tokens

**Task Description:**
Comprehensively explore the XCompact3D source code structure, identify key directories, main entry points, build configuration.

**Agent Instructions:**
```
Search the XCompact3D source directory (Incompact3d/) for:
1. Main source files and entry points (look for main.f90, main.f, program statements)
2. Directory structure and organization (src/, tests/, examples/, doc/)
3. Build configuration files (CMakeLists.txt, Makefile, setup.py, configure)
4. Documentation files (README, docs/build_guide.md, INSTALL)
5. Example scripts or test cases showing how the application is run
6. Module dependencies and interfaces (use statements in Fortran files)

Return a structured summary of:
- Entry point file and main program location
- Build system used (CMake, Make, Autotools, etc.)
- Major code modules and their dependencies
- Compilation flags and optimization options
- Runtime input/output patterns
- Example invocations
```

**Dependencies:** Depends on Stage 1.1 (Repository cloning)

**Output Artifacts:**
- `code_structure_analysis.md` - detailed source code documentation
- File tree with annotations

---

### 2.2: Document Build Commands

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 2 GB
- Storage: 2 GB
- Network: Not required

**Estimated Token Usage:** 2,500-3,500 tokens

**Task Description:**
Create comprehensive build instructions for XCompact3D, including configuration and compilation commands.

**Commands to Document:**

**For CMake-based builds:**
```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

# Create build directory
mkdir -p build && cd build

# Configure with CMake (enable MPI, optimization flags)
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_Fortran_COMPILER=mpif90 \
  -DCMAKE_C_COMPILER=mpicc \
  -DCMAKE_CXX_COMPILER=mpicxx \
  -DENABLE_MPI=ON \
  -DFFTW_DIR=/path/to/fftw \
  -DHDF5_DIR=/path/to/hdf5

# Compile (parallel with -j)
make -j 16

# Install to prefix
make install DESTDIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/xcompact3d_install
```

**For Make-based builds:**
```bash
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

# Copy and edit Makefile if necessary
cp Makefile Makefile.custom

# Build with parallelism
make -f Makefile.custom -j 16 FFLAGS="-O3 -fPIC -march=native"

# Create output directory
mkdir -p ../xcompact3d_install/bin
cp bin/xcompact3d ../xcompact3d_install/bin/
```

**Dependencies:** Depends on Stage 1.3 (Dependency installation) and Stage 2.1 (Code analysis)

**Output Artifacts:**
- `build_instructions.sh` - executable build script
- `build_flags.txt` - optimization and feature flags
- Compiled executable location

---

### 2.3: Document Runtime Configuration

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 1 GB
- Storage: 1 GB
- Network: Not required

**Estimated Token Usage:** 2,000-2,500 tokens

**Task Description:**
Document how XCompact3D is invoked, input file formats, output specifications, and typical runtime configurations.

**Documentation to Create:**
```bash
# Create runtime documentation file
cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/runtime_config.md << 'EOF'
## XCompact3D Runtime Configuration

### Executable Location
/home/jye/publications/cases/case_001_xcompact3d_deployment/xcompact3d_install/bin/xcompact3d

### Invocation Command Structure
mpirun -np <NPROCS> /path/to/xcompact3d <input_file.i3d>

### Input File Format
- Format: .i3d files (Fortran namelist format)
- Location: Required in execution directory
- Key parameters:
  * Domain decomposition (p_row, p_col)
  * Grid parameters (nx, ny, nz)
  * Time stepping parameters (dt, itime)
  * Physics parameters (Reynolds number, etc.)
  * I/O settings (frequency, format)

### Output
- Binary/HDF5 checkpoint files
- Statistics files
- Log output to standard output
- Frequency controlled by input parameters

### Example Invocation
mpirun -np 16 ./xcompact3d input.i3d > xcompact3d.log 2>&1

### Key Environment Variables
- OMP_NUM_THREADS: OpenMP threads per rank (if hybrid MPI+OpenMP)
- I_MPI_FABRICS: InfiniBand fabric selection (Intel MPI)
- FFTW_THREADS: FFTW threading (if multi-threaded FFTW)
EOF
```

**Dependencies:** Depends on Stage 2.1 (Code analysis)

**Output Artifacts:**
- `runtime_config.md` - detailed runtime documentation
- Example input files

---

## Stage 3: HPC Environment Discovery

### 3.1: Query Slurm Cluster Information

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: None required
- Network: SSH access to login node required

**Estimated Token Usage:** 1,500-2,000 tokens

**Task Description:**
Execute Slurm commands on the target HPC cluster to discover available nodes, partitions, GPUs, and network topology.

**Commands to Execute (on HPC login node):**

```bash
# Save to /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_discovery.sh

#!/bin/bash

# Get cluster overview
echo "=== SLURM CLUSTER INFORMATION ===" > slurm_info.txt
sinfo >> slurm_info.txt 2>&1

# Get detailed partition information
echo -e "\n=== PARTITION DETAILS ===" >> slurm_info.txt
sinfo -l >> slurm_info.txt 2>&1

# List available partitions by name
echo -e "\n=== AVAILABLE PARTITIONS ===" >> slurm_info.txt
sinfo --format="%R %a %D %c %m %e %g" >> slurm_info.txt 2>&1

# Get node details
echo -e "\n=== NODE CONFIGURATION ===" >> slurm_info.txt
scontrol show nodes | head -100 >> slurm_info.txt 2>&1

# Get GPU information (if available)
echo -e "\n=== GPU INFORMATION ===" >> slurm_info.txt
sinfo --Format="NodeList,CPUs,GPUs,Memory" >> slurm_info.txt 2>&1

# Get network topology
echo -e "\n=== NETWORK TOPOLOGY ===" >> slurm_info.txt
scontrol show topology 2>/dev/null || echo "Topology info not available" >> slurm_info.txt

# Check job queue status
echo -e "\n=== CURRENT JOB QUEUE ===" >> slurm_info.txt
squeue -l | head -20 >> slurm_info.txt 2>&1

# Get account and QoS information
echo -e "\n=== ACCOUNT & QoS INFO ===" >> slurm_info.txt
sacctmgr show accounts >> slurm_info.txt 2>&1
sacctmgr show qos >> slurm_info.txt 2>&1

echo "Cluster information saved to slurm_info.txt"
```

**Typical Output Fields to Document:**
- NODELIST, NODES (number of compute nodes)
- PARTITION (partition names)
- STATE (node state: alloc, idle, down, etc.)
- CPUS (CPUs per node)
- MEMORY (memory per node)
- GRES (GPU, other generic resources)
- TIME_LIMIT (maximum job time)
- FEATURES (node features/tags)

**Dependencies:** None (requires direct access to HPC system)

**Output Artifacts:**
- `slurm_info.txt` - complete cluster information
- `slurm_commands.txt` - documented Slurm queries

---

### 3.2: Analyze Resource Availability and Constraints

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: 1 GB
- Network: Not required

**Estimated Token Usage:** 1,500-2,000 tokens

**Task Description:**
Parse Slurm cluster information to identify optimal resource requests for XCompact3D job.

**Analysis to Perform:**
```bash
# Create analysis script
cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/analyze_resources.sh << 'EOF'
#!/bin/bash

# Parse slurm_info.txt to extract:
# 1. Available partitions and their time limits
# 2. Number and types of nodes
# 3. CPU/GPU/Memory availability
# 4. Network connectivity (interconnect type: Ethernet, InfiniBand, etc.)

# Recommendations:
# - Use compute nodes with InfiniBand for better MPI performance
# - Request CPUs that are multiples of core counts (2, 4, 8, 16, etc.)
# - Balance job size against queue wait times
# - Typical XCompact3D: 16-128 MPI ranks for modest simulations

echo "Resource Analysis Complete"
echo "See resource_recommendations.txt for optimal job configuration"
EOF
```

**Dependencies:** Depends on Stage 3.1 (Cluster discovery)

**Output Artifacts:**
- `resource_recommendations.txt` - optimal resource configuration
- `node_analysis.txt` - node type and capability summary

---

## Stage 4: Slurm Batch Script Preparation

### 4.1: Create Slurm Batch Script Template

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: 500 MB
- Network: Not required

**Estimated Token Usage:** 2,000-2,500 tokens

**Task Description:**
Create comprehensive Slurm batch script with resource requests, environment setup, and job execution commands.

**Output File: `xcompact3d_job.sh`**

```bash
#!/bin/bash
#SBATCH --job-name=xcompact3d_sim
#SBATCH --output=%x_%j.log
#SBATCH --error=%x_%j.err
#SBATCH --time=01:00:00              # 1 hour (adjust based on simulation)
#SBATCH --nodes=2                    # Number of compute nodes
#SBATCH --ntasks-per-node=16         # MPI ranks per node
#SBATCH --cpus-per-task=1            # CPU cores per rank
#SBATCH --partition=compute          # Partition name (from sinfo)
#SBATCH --account=<YOUR_ACCOUNT>     # Replace with your account
#SBATCH --qos=standard               # Quality of service
#SBATCH --mem-per-cpu=4G             # Memory per CPU

# Optional GPU support (uncomment if using GPUs)
#SBATCH --gres=gpu:1                 # 1 GPU per node

# Optional: Exclusive node allocation for better performance
#SBATCH --exclusive

# Set up environment
module purge                         # Clear default modules
module load gcc/11.2.0              # Compiler
module load openmpi/4.1.2           # MPI library
module load fftw/3.3.10             # FFT library
module load hdf5/1.12.1             # I/O library

# Export MPI-specific environment variables
export OMPI_MCA_btl=openib,self     # Use InfiniBand
export OMP_NUM_THREADS=1            # Disable OpenMP (unless hybrid)
export MPI_PAFFINITY_ALONE=true     # Pin processes to cores

# Set working directory
WORK_DIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
INPUT_DIR=${WORK_DIR}/input_files
OUTPUT_DIR=${WORK_DIR}/output_${SLURM_JOB_ID}
EXEC_DIR=${WORK_DIR}/xcompact3d_install/bin

# Create output directory
mkdir -p ${OUTPUT_DIR}
cd ${OUTPUT_DIR}

# Copy input file to working directory
cp ${INPUT_DIR}/input.i3d .

# Print job information
echo "======================================="
echo "Job Information:"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Nodes: $SLURM_NNODES"
echo "Total Tasks: $SLURM_NTASKS"
echo "CPUs per Task: $SLURM_CPUS_PER_TASK"
echo "Working Directory: $(pwd)"
echo "======================================="

# Show node list
srun hostname | sort | uniq -c

# Run XCompact3D
echo "Starting XCompact3D simulation..."
srun -n $SLURM_NTASKS $EXEC_DIR/xcompact3d input.i3d > xcompact3d.log 2>&1

# Check exit code
EXIT_CODE=$?
echo "XCompact3D exited with code: $EXIT_CODE"

# Verify output files
echo "Checking output files..."
ls -lh | head -20

# Move output to persistent location (optional)
echo "Simulation completed at $(date)"
exit $EXIT_CODE
```

**Alternative Variants to Document:**

**4.1a: GPU-Accelerated Variant**
```bash
#SBATCH --gres=gpu:4                 # 4 GPUs per node
#SBATCH --time=04:00:00              # Longer for GPU-accelerated code

# GPU-specific environment
export CUDA_VISIBLE_DEVICES=0,1,2,3
```

**4.1b: Multi-Node Scaling Variant**
```bash
#SBATCH --nodes=8                    # 8 nodes
#SBATCH --ntasks-per-node=32         # 32 ranks per node (256 total)
#SBATCH --time=02:00:00              # Longer for larger jobs
```

**4.1c: Array Job Variant** (for parameter sweeps)
```bash
#SBATCH --array=0-9                  # 10 simulation variants
#SBATCH --time=01:00:00

# Different input files for each array task
INPUT_FILE="input_${SLURM_ARRAY_TASK_ID}.i3d"
```

**Dependencies:** Depends on Stage 3.2 (Resource analysis) and Stage 2.3 (Runtime config)

**Output Artifacts:**
- `xcompact3d_job.sh` - main batch script
- `xcompact3d_job_gpu.sh` - GPU variant
- `xcompact3d_job_array.sh` - array job variant

---

### 4.2: Prepare Input Files and Test Configuration

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: 1 GB
- Network: Not required

**Estimated Token Usage:** 1,500-2,000 tokens

**Task Description:**
Create example input files and verify batch script syntax.

**Commands to Execute:**

```bash
# Create input files directory
mkdir -p /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/input_files

# Create example input file (Fortran namelist format)
cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/input_files/input.i3d << 'EOF'
&PARAMETERS
  ! Grid parameters
  nx = 256
  ny = 256
  nz = 128

  ! Domain decomposition
  p_row = 4
  p_col = 4

  ! Time stepping
  dt = 0.01
  istep_start = 0
  istep_end = 1000

  ! Physics (Reynolds number = 1/nu)
  nu = 0.001

  ! I/O parameters
  ioutput = 100
  isave = 100

  ! Boundary conditions
  nclx1 = 2        ! periodic/Dirichlet/Neumann
  nclxn = 2
  ncly1 = 2
  nclyn = 2
  nclz1 = 2
  nclzn = 2
/
EOF

# Validate batch script syntax
bash -n /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/xcompact3d_job.sh
echo "Batch script syntax check complete"

# Create README for input files
cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/input_files/README.md << 'EOF'
# Input Files for XCompact3D

## File Format
- Fortran namelist format (.i3d)
- Standard text file with &PARAMETERS ... / blocks

## Key Parameters
- nx, ny, nz: Grid resolution
- p_row, p_col: Domain decomposition (MPI rank layout)
- dt: Time step size
- nu: Kinematic viscosity
- istep_end: Total simulation time steps
- ioutput, isave: Output frequency

## Constraints
- (nx, ny, nz) must be divisible by (p_row, p_col) for balanced decomposition
- Time step dt must satisfy CFL condition for stability
- Memory usage ≈ nx*ny*nz * 16 bytes per MPI rank
EOF
```

**Dependencies:** Depends on Stage 2.3 (Runtime configuration)

**Output Artifacts:**
- `input_files/input.i3d` - example input file
- `input_files/README.md` - input documentation
- Batch script validation report

---

### 4.3: Create Job Submission Wrapper Script

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: 500 MB
- Network: Not required

**Estimated Token Usage:** 1,500-2,000 tokens

**Task Description:**
Create user-friendly wrapper script for job submission with validation and setup.

**Output File: `submit_xcompact3d_job.sh`**

```bash
#!/bin/bash
#
# Submit XCompact3D job to Slurm
# Usage: ./submit_xcompact3d_job.sh [--dry-run] [--nodes N] [--time HH:MM:SS]

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BATCH_SCRIPT="${SCRIPT_DIR}/xcompact3d_job.sh"

# Default parameters
NODES=2
TIME="01:00:00"
DRY_RUN=false
QUEUE_WATCH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --nodes)
      NODES="$2"
      shift 2
      ;;
    --time)
      TIME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --watch)
      QUEUE_WATCH=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate batch script exists
if [[ ! -f "$BATCH_SCRIPT" ]]; then
  echo "ERROR: Batch script not found: $BATCH_SCRIPT"
  exit 1
fi

# Validate input file exists
if [[ ! -f "${SCRIPT_DIR}/input_files/input.i3d" ]]; then
  echo "ERROR: Input file not found: ${SCRIPT_DIR}/input_files/input.i3d"
  exit 1
fi

# Show submission information
echo "========================================"
echo "XCompact3D Job Submission"
echo "========================================"
echo "Batch script: $BATCH_SCRIPT"
echo "Nodes: $NODES"
echo "Time limit: $TIME"
echo "Input file: ${SCRIPT_DIR}/input_files/input.i3d"
echo ""

# Validate Slurm is available
if ! command -v sbatch &> /dev/null; then
  echo "ERROR: Slurm command 'sbatch' not found"
  exit 1
fi

# Dry run option
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would submit with:"
  echo "sbatch --nodes=$NODES --time=$TIME $BATCH_SCRIPT"
  exit 0
fi

# Submit job
echo "Submitting job..."
JOB_ID=$(sbatch --nodes=$NODES --time=$TIME $BATCH_SCRIPT | awk '{print $NF}')
echo "Job submitted successfully!"
echo "Job ID: $JOB_ID"
echo ""
echo "Commands to monitor:"
echo "  squeue -j $JOB_ID                    # Check status"
echo "  scontrol show job $JOB_ID             # Detailed info"
echo "  tail -f xcompact3d_sim_${JOB_ID}.log  # Watch log"
echo "  scancel $JOB_ID                       # Cancel job"
echo ""

# Optional: watch queue
if [ "$QUEUE_WATCH" = true ]; then
  echo "Watching job queue (Ctrl+C to stop)..."
  while true; do
    clear
    echo "Job status: $(date)"
    squeue -j $JOB_ID || echo "Job completed"
    sleep 5
  done
fi
```

**Dependencies:** Depends on Stage 4.2 (Input file preparation)

**Output Artifacts:**
- `submit_xcompact3d_job.sh` - submission wrapper script
- Inline documentation and usage examples

---

## Stage 5: Job Submission & Monitoring

### 5.1: Submit Job and Monitor Execution

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 1 core
- Memory: 512 MB
- Storage: 2 GB (for logs)
- Network: SSH access to HPC cluster

**Estimated Token Usage:** 2,000-2,500 tokens

**Task Description:**
Submit the XCompact3D batch job and monitor its progress with comprehensive commands.

**Commands to Execute:**

```bash
# Navigate to working directory
cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

# Make scripts executable
chmod +x xcompact3d_job.sh submit_xcompact3d_job.sh

# Option 1: Direct sbatch submission
echo "=== SUBMITTING JOB ==="
JOB_ID=$(sbatch xcompact3d_job.sh | tee job_submission.log | awk '{print $NF}')
echo "Job ID: $JOB_ID"
echo "Submission timestamp: $(date)" >> job_submission.log

# Save job ID for reference
echo $JOB_ID > current_job_id.txt

# Option 2: Using wrapper script
# ./submit_xcompact3d_job.sh --nodes 2 --time 01:00:00 --watch

echo ""
echo "=== IMMEDIATE STATUS CHECK ==="
squeue -j $JOB_ID

echo ""
echo "=== CONTINUOUS MONITORING ==="
# Monitor job every 10 seconds for first 2 minutes
for i in {1..12}; do
  echo "Check $i ($(date '+%H:%M:%S'))"
  squeue -j $JOB_ID -o "%.10i %.9P %.8j %.8u %.2t %.10M %.6D %R"

  # Check if job has started running
  STATUS=$(squeue -j $JOB_ID -h -o "%t" 2>/dev/null || echo "")
  if [[ "$STATUS" == "R" ]]; then
    echo "✓ Job is RUNNING"
    break
  elif [[ "$STATUS" == "CD" ]] || [[ "$STATUS" == "CA" ]]; then
    echo "✗ Job COMPLETED or CANCELLED"
    break
  elif [[ -z "$STATUS" ]]; then
    echo "✗ Job not found in queue"
    break
  fi

  sleep 10
done
```

**Monitoring Command Reference:**

```bash
# Watch job status continuously
watch -n 5 "squeue -j <JOB_ID>"

# Get comprehensive job information
scontrol show job <JOB_ID>

# Get job accounting information (after completion)
sacct -j <JOB_ID> --format=JobID,JobName,State,ExitCode,Start,End,CPUTime,MaxRSS

# Stream log output in real-time
tail -f xcompact3d_sim_<JOB_ID>.log

# Check resource usage during execution
sstat -j <JOB_ID> --format=JobID,MaxVMSize,MaxRSS,AveCPU,AveVMSize
```

**Dependencies:** Depends on Stage 4.3 (Job submission wrapper)

**Output Artifacts:**
- `job_submission.log` - submission record
- `current_job_id.txt` - active job ID reference
- Job status monitoring script

---

### 5.2: Validate Application Startup and Output

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 2 cores
- Memory: 2 GB
- Storage: 5 GB (output files)
- Network: Not required

**Estimated Token Usage:** 2,000-2,500 tokens

**Task Description:**
Check job logs, verify application started correctly, validate output file generation.

**Commands to Execute:**

```bash
# Set job ID variable
JOB_ID=$(cat /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/current_job_id.txt)
WORK_DIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

echo "Validating job $JOB_ID"
echo ""

# Wait for job to appear in output directory
OUTPUT_PATTERN="output_${JOB_ID}"
OUTPUT_DIR="${WORK_DIR}/${OUTPUT_PATTERN}"

echo "=== WAITING FOR JOB TO START (max 5 minutes) ==="
for i in {1..30}; do
  if [ -d "$OUTPUT_DIR" ]; then
    echo "✓ Output directory found: $OUTPUT_DIR"
    break
  else
    echo "Waiting... (attempt $i/30)"
    sleep 10
  fi
done

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "✗ Output directory not created. Job may have failed to start."
  echo "Checking Slurm logs..."
  scontrol show job $JOB_ID
  exit 1
fi

echo ""
echo "=== CHECKING LOG FILES ==="
if [ -f "${WORK_DIR}/xcompact3d_sim_${JOB_ID}.log" ]; then
  echo "Job stdout log:"
  head -50 "${WORK_DIR}/xcompact3d_sim_${JOB_ID}.log"
  echo "..."
  tail -20 "${WORK_DIR}/xcompact3d_sim_${JOB_ID}.log"
fi

if [ -f "${WORK_DIR}/xcompact3d_sim_${JOB_ID}.err" ]; then
  echo ""
  echo "Job stderr log:"
  cat "${WORK_DIR}/xcompact3d_sim_${JOB_ID}.err"
fi

echo ""
echo "=== VALIDATING OUTPUT FILES ==="
cd "$OUTPUT_DIR"

# Check for expected output files
echo "Files in output directory:"
ls -lh | tail -20

# Look for XCompact3D output signatures
echo ""
echo "Checking for XCompact3D output signatures..."

# HDF5 checkpoint files
if ls *.h5 &> /dev/null 2>/dev/null; then
  echo "✓ HDF5 checkpoint files found"
  file *.h5 | head -5
fi

# Binary output files
if ls *.bin &> /dev/null 2>/dev/null; then
  echo "✓ Binary output files found"
  ls -lh *.bin | head -5
fi

# Statistics files
if ls *stats* *stat* &> /dev/null 2>/dev/null; then
  echo "✓ Statistics files found"
  ls -lh *stats* *stat* 2>/dev/null | head -5
fi

# Check xcompact3d.log for convergence/errors
if [ -f "xcompact3d.log" ]; then
  echo ""
  echo "Application log (last 30 lines):"
  tail -30 xcompact3d.log

  # Look for error indicators
  if grep -qi "error\|fail\|abort\|segmentation" xcompact3d.log; then
    echo "⚠ WARNING: Errors detected in application log"
    grep -i "error\|fail\|abort\|segmentation" xcompact3d.log | head -10
  fi
fi

echo ""
echo "=== JOB COMPLETION STATUS ==="
scontrol show job $JOB_ID | grep -E "State|ExitCode|End"

echo ""
echo "=== RESOURCE UTILIZATION SUMMARY ==="
sacct -j $JOB_ID --format=JobID,JobName,State,ExitCode,MaxRSS,MaxVMSize,CPUTime,Elapsed
```

**Validation Checklist:**
```
[ ] Output directory created: output_<JOB_ID>/
[ ] Log files present: xcompact3d_sim_<JOB_ID>.log
[ ] Application started: Check for initial message in log
[ ] Output files generated: .h5, .bin, .dat, or expected format
[ ] No errors in logs: Search for "ERROR", "FAILED", "SEGMENTATION"
[ ] Job completed successfully: Exit code 0
[ ] Resource limits not exceeded: Check MaxRSS vs --mem-per-cpu
```

**Dependencies:** Depends on Stage 5.1 (Job submission)

**Output Artifacts:**
- `validation_report.txt` - comprehensive validation results
- Log files from execution
- Verified output directory structure

---

### 5.3: Post-Simulation Analysis and Cleanup

**Specialist Agent:** `general-purpose`
**Hardware Resources:**
- CPU: 4 cores
- Memory: 4 GB
- Storage: 10 GB (for analysis)
- Network: Not required

**Estimated Token Usage:** 2,000-3,000 tokens

**Task Description:**
Perform post-simulation analysis, generate summary reports, and organize output files.

**Commands to Create:**

```bash
#!/bin/bash
# File: analyze_xcompact3d_output.sh

JOB_ID=$(cat /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/current_job_id.txt)
WORK_DIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
OUTPUT_DIR="${WORK_DIR}/output_${JOB_ID}"

echo "=== XCompact3D POST-SIMULATION ANALYSIS ===" | tee analysis_report.txt
echo "Job ID: $JOB_ID" | tee -a analysis_report.txt
echo "Analysis Date: $(date)" | tee -a analysis_report.txt
echo "" | tee -a analysis_report.txt

# File statistics
echo "=== OUTPUT FILE STATISTICS ===" | tee -a analysis_report.txt
cd "$OUTPUT_DIR"

TOTAL_SIZE=$(du -sh . | awk '{print $1}')
FILE_COUNT=$(find . -type f | wc -l)

echo "Total output size: $TOTAL_SIZE" | tee -a analysis_report.txt
echo "Total files: $FILE_COUNT" | tee -a analysis_report.txt
echo "" | tee -a analysis_report.txt

# Timing information
echo "=== EXECUTION TIMING ===" | tee -a analysis_report.txt
if [ -f "xcompact3d.log" ]; then
  grep -i "time\|elapsed\|cpu" xcompact3d.log | head -10 | tee -a analysis_report.txt
fi
echo "" | tee -a analysis_report.txt

# Performance metrics (if available)
echo "=== RESOURCE UTILIZATION ===" | tee -a analysis_report.txt
sacct -j $JOB_ID --format=JobID,JobName,State,ExitCode,MaxRSS,AveCPU,Elapsed,CPUTime 2>/dev/null | tee -a analysis_report.txt
echo "" | tee -a analysis_report.txt

# Check for convergence (application-specific)
echo "=== CONVERGENCE STATUS ===" | tee -a analysis_report.txt
if [ -f "xcompact3d.log" ]; then
  # Look for residual or convergence information
  grep -i "residual\|converge\|energy\|kinetic" xcompact3d.log | tail -10 | tee -a analysis_report.txt
else
  echo "No convergence data available in logs" | tee -a analysis_report.txt
fi
echo "" | tee -a analysis_report.txt

# Create output summary
echo "=== OUTPUT FILES SUMMARY ===" | tee -a analysis_report.txt
echo "Checkpoint files:" | tee -a analysis_report.txt
find . -name "*.h5" -o -name "*.bin" -o -name "*.dat" | xargs ls -lh 2>/dev/null | tee -a analysis_report.txt

# Copy analysis report to work directory
cp analysis_report.txt "${WORK_DIR}/"

echo ""
echo "Analysis complete. Report saved to: ${WORK_DIR}/analysis_report.txt"
```

**Additional Cleanup Scripts:**

```bash
# Archive large output files (optional)
tar -czf xcompact3d_output_${JOB_ID}.tar.gz output_${JOB_ID}/

# Create index of results
cat > results_index.txt << EOF
XCompact3D Simulation Results - Job $JOB_ID
Generated: $(date)

Results Location: /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/output_${JOB_ID}/

Files:
$(ls -lh output_${JOB_ID}/ | tail -20)

For further analysis, use:
- ParaView for visualization of .h5 files
- Python/matplotlib for statistical analysis
- Visit for volume rendering

All logs available in:
- xcompact3d_sim_${JOB_ID}.log (stdout)
- xcompact3d_sim_${JOB_ID}.err (stderr)
EOF
```

**Dependencies:** Depends on Stage 5.2 (Output validation)

**Output Artifacts:**
- `analysis_report.txt` - comprehensive analysis summary
- `results_index.txt` - results directory guide
- Archived output files (optional)

---

## Execution Roadmap

### Phase 1: Parallel Preparation (Stages 1-3)

These substages can execute in parallel since they have no mutual dependencies:

| Substage | Agent | Resources | Tokens | Time Est. | Parallel Group |
|----------|-------|-----------|--------|-----------|----------------|
| 1.1: Clone Repository | general-purpose | 2C/2GB/10GB | 1.5K-2K | 5 min | A |
| 1.2: Identify Dependencies | general-purpose | 2C/1GB/1GB | 2K-2.5K | 3 min | A |
| 1.3: Install Commands | general-purpose | 2C/1GB/2GB | 2K-3K | 2 min | B* |
| 2.1: Code Structure Analysis | Explore | 4C/4GB/2GB | 3K-4K | 10 min | A |
| 2.2: Build Documentation | general-purpose | 2C/2GB/2GB | 2.5K-3.5K | 5 min | B* |
| 2.3: Runtime Configuration | general-purpose | 2C/1GB/1GB | 2K-2.5K | 3 min | B* |
| 3.1: Query Slurm Cluster | general-purpose | 1C/512MB/None | 1.5K-2K | 2 min | C** |
| 3.2: Analyze Resources | general-purpose | 1C/512MB/1GB | 1.5K-2K | 3 min | C** |

**Parallel Execution Groups:**
- **Group A** (can run immediately): 1.1, 1.2, 2.1 → 10 min wall time
- **Group B** (after A completes): 1.3, 2.2, 2.3 → 5 min wall time
- **Group C** (after B completes): 3.1, 3.2 → 5 min wall time (requires HPC cluster access)
- **Total**: ~20 minutes preparation time

### Phase 2: Sequential Batch Script Preparation (Stage 4)

| Substage | Agent | Resources | Tokens | Time Est. | Dependencies |
|----------|-------|-----------|--------|-----------|--------------|
| 4.1: Create Batch Script | general-purpose | 1C/512MB/500MB | 2K-2.5K | 2 min | Stage 3 |
| 4.2: Input Files & Validation | general-purpose | 1C/512MB/1GB | 1.5K-2K | 3 min | Stage 2.3 |
| 4.3: Submission Wrapper | general-purpose | 1C/512MB/500MB | 1.5K-2K | 2 min | Stage 4.2 |

**Total**: ~7 minutes

### Phase 3: Job Execution & Monitoring (Stage 5)

| Substage | Agent | Resources | Tokens | Time Est. | Dependencies | Notes |
|----------|-------|-----------|--------|-----------|--------------|-------|
| 5.1: Submit & Monitor | general-purpose | 1C/512MB/2GB | 2K-2.5K | 10+ min | Stage 4.3 | Wall time depends on job queue |
| 5.2: Validate Output | general-purpose | 2C/2GB/5GB | 2K-2.5K | 5-10 min | Stage 5.1 | Continues during simulation |
| 5.3: Post-Analysis | general-purpose | 4C/4GB/10GB | 2K-3K | 10 min | Stage 5.2 | After job completion |

**Total**: 25+ minutes (including job queue wait and simulation runtime)

---

## Implementation Assumptions

1. **HPC Cluster Access**: Assumes SSH access to Slurm-managed cluster with working `sbatch`, `squeue`, `scontrol` commands.

2. **Compiler Availability**: Assumes availability of Fortran compiler (gfortran/ifort) and C compiler on compute nodes.

3. **Required Libraries**: Assumes package manager or Spack availability for installing FFTW, HDF5, LAPACK, and MPI.

4. **File System**: Assumes shared parallel filesystem (e.g., NFS, Lustre) accessible from all compute nodes.

5. **XCompact3D Version**: Plan targets current main branch; specific version can be locked via git tags if needed.

6. **Module System**: Assumes typical HPC cluster with `module` command for environment management.

7. **Input File Format**: Assumes Fortran namelist format for input configuration; actual format may vary by version.

---

## Risk Mitigation & Troubleshooting

### Common Issues and Resolution Strategies

**Issue: Missing Dependencies**
- Resolution: Run comprehensive dependency scan (Stage 1.2), document exact versions
- Fallback: Use Spack for reproducible builds

**Issue: Job Won't Start (PD state)**
- Resolution: Check QoS limits, account status, partition availability
- Command: `sinfo -R` to see reservation info

**Issue: MPI Rank Mismatch**
- Resolution: Verify domain decomposition parameters (p_row * p_col = ntasks)
- Command: Check input file parameters match job submission

**Issue: Out of Memory**
- Resolution: Reduce grid resolution (nx, ny, nz) or increase --mem-per-cpu
- Command: `sstat -j <JOB_ID> --format=MaxRSS` to monitor

**Issue: Slow Performance**
- Resolution: Check network topology, verify InfiniBand usage
- Command: `scontrol show topology` to inspect node connectivity

---

## Validation & Success Criteria

### End-to-End Validation Checklist

✓ **Build Stage**
- [ ] Source code successfully cloned from GitHub
- [ ] All dependencies installed without errors
- [ ] Compilation completes with no fatal errors
- [ ] Executable file present at installation path

✓ **Configuration Stage**
- [ ] Slurm cluster information successfully queried
- [ ] Batch script validates without syntax errors
- [ ] Resource request aligns with cluster capabilities
- [ ] Input files present and readable

✓ **Execution Stage**
- [ ] Job successfully submitted (receives Job ID)
- [ ] Job transitions from PD (pending) to R (running)
- [ ] Application initializes without errors
- [ ] Output files generated (checkpoint, statistics, logs)

✓ **Completion Stage**
- [ ] Job completes with exit code 0
- [ ] Output directory contains expected files
- [ ] Convergence/error analysis logs available
- [ ] Resource utilization within requested limits

---

## File Structure & Artifact Locations

```
/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/
├── Incompact3d/                          # Source code (Stage 1.1)
├── input_files/
│   ├── input.i3d                         # Example input (Stage 4.2)
│   └── README.md
├── xcompact3d_install/                   # Compiled binary location
│   └── bin/xcompact3d
├── output_<JOB_ID>/                      # Job outputs (Stage 5)
│   ├── xcompact3d.log                    # Application log
│   ├── *.h5                              # Checkpoint files
│   └── *stats*                           # Statistics
├── xcompact3d_job.sh                     # Main batch script (Stage 4.1)
├── xcompact3d_job_gpu.sh                 # GPU variant
├── xcompact3d_job_array.sh               # Array job variant
├── submit_xcompact3d_job.sh              # Submission wrapper (Stage 4.3)
├── repo_info.txt                         # Repository metadata (Stage 1.1)
├── dependency_analysis.txt               # Dependencies (Stage 1.2)
├── code_structure_analysis.md            # Code structure (Stage 2.1)
├── build_instructions.sh                 # Build script (Stage 2.2)
├── runtime_config.md                     # Runtime docs (Stage 2.3)
├── slurm_info.txt                        # Cluster info (Stage 3.1)
├── resource_recommendations.txt          # Resource analysis (Stage 3.2)
├── job_submission.log                    # Submission record (Stage 5.1)
├── current_job_id.txt                    # Active job ID (Stage 5.1)
├── analysis_report.txt                   # Post-analysis (Stage 5.3)
└── results_index.txt                     # Results guide (Stage 5.3)
```

---

## Summary

This deployment plan provides a **complete, step-by-step roadmap** for deploying XCompact3D on an HPC cluster. The plan:

1. **Decomposes** the deployment into 12 distinct, manageable subtasks
2. **Assigns specialist agents** to each task based on required expertise
3. **Documents exact commands** for downloading, building, configuring, and running
4. **Specifies resource requirements** (CPU, memory, storage, network) for each agent
5. **Identifies parallelization opportunities** for efficient execution
6. **Includes validation steps** to ensure successful deployment
7. **Provides fallback strategies** for common issues

The total estimated wall-clock time for full deployment is approximately **32-50 minutes**, depending on job queue wait times and simulation duration. The plan is designed to be followed sequentially by executing the documented commands in each stage, with parallel execution possible within Groups A, B, and C during preparation phases.


