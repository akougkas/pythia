---
case: case_001_xcompact3d_deployment
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: 1b990e1b-8b7a-4b55-b239-fbb93b4bfc0a
duration_ms: 115949
duration_wall_s: 123.0
cost_usd: 0.11172549999999996
num_turns: 6
timestamp: 2026-03-18T00:39:26.667265+00:00
error: None
---

# Plan

# XCompact3D Deployment Plan for Slurm HPC Cluster

## Context

This plan enables deployment of the XCompact3D incompressible Navier-Stokes solver on an HPC cluster managed by Slurm. XCompact3D is a high-performance scientific computing application requiring careful coordination of source code acquisition, dependency management, build compilation, cluster resource assessment, job script creation, and execution monitoring. The plan decomposes this complex task into six sequential and parallel subtasks with clear agent assignments, hardware requirements, and dependencies.

---

## Executive Summary

The deployment consists of 6 major stages organized into two parallel pipelines that merge:

**Pipeline A (Source & Build):**
1. Download source code and identify dependencies
2. Analyze build/configure process
3. Compile and build application

**Pipeline B (Cluster & Job Preparation):**
4. Query and assess Slurm cluster resources
5. Create Slurm batch script with resource requests
6. Submit job and monitor execution

---

## Stage 1: Download Source Code and Dependencies

### Objective
Acquire XCompact3D source code from upstream repository and document all required dependencies (libraries, compilers, runtime requirements).

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Download source code, inspect source tree, identify direct and transitive dependencies

### Hardware Requirements
- **CPU**: 1-2 cores (minimal processing)
- **Memory**: 2-4 GB RAM
- **Storage**: 5-10 GB (source code + dependencies)
- **Network**: Required (GitHub access, package repository access)

### Expected Token Usage
- 5,000-8,000 tokens

### Dependencies
- **Upstream**: None
- **Downstream**: Stage 2, Stage 3

### Exact Commands & Script

```bash
#!/bin/bash
# stage_1_download_source.sh

# Set working directory
WORKDIR="/path/to/xcompact3d/work"
mkdir -p $WORKDIR
cd $WORKDIR

# Clone XCompact3D repository
echo "=== Stage 1: Downloading XCompact3D Source Code ==="
git clone https://github.com/xcompact3d/Incompact3d.git
cd Incompact3d

# Document repository information
echo "Repository Information:"
git remote -v
git log --oneline -10
git describe --tags

# List source tree structure
echo "Source tree structure:"
find . -type f -name "*.f90" -o -name "*.f95" -o -name "*.f03" | head -20
find . -type f -name "Makefile" -o -name "CMakeLists.txt" -o -name "*.mk"

# Identify dependency files
echo "Dependency information files:"
find . -name "requirements*.txt" -o -name "depends.txt" -o -name "INSTALL*" -o -name "README*"

# Create dependency manifest
cat > DEPENDENCY_MANIFEST.txt <<EOF
Source Code Download Information
=================================
Repository: https://github.com/xcompact3d/Incompact3d
Clone location: $WORKDIR/Incompact3d
Date: $(date)
Branch: $(git branch)
Commit: $(git rev-parse HEAD)

Key Dependencies (to be verified):
- Fortran compiler (gfortran or Intel ifort)
- MPI library (OpenMPI or Intel MPI)
- FFTW3 (Fast Fourier Transform library)
- HDF5 (parallel I/O)
- NetCDF (optional, scientific data format)
- LAPACK/BLAS (linear algebra)
- Python 3.x (optional, preprocessing/postprocessing)

Build System:
- Makefile-based or CMake (verify in source)

Documentation:
- See docs/ directory and README files for build instructions
EOF

echo "Manifest created: DEPENDENCY_MANIFEST.txt"
cd $WORKDIR
```

### Output Artifacts
- Cloned source tree in `./Incompact3d/`
- File: `DEPENDENCY_MANIFEST.txt` - Lists all identified dependencies
- File: `SOURCE_STRUCTURE.txt` - Maps source file organization

---

## Stage 2: Analyze Build Process and Source Code

### Objective
Thoroughly analyze the XCompact3D source code structure, read build configuration files, understand compiler requirements, and document the complete build/configure process.

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Parse Makefile/CMake, extract compiler flags, identify build targets, document configure options

### Hardware Requirements
- **CPU**: 2-4 cores (code analysis, text processing)
- **Memory**: 4-8 GB RAM
- **Storage**: 10 GB
- **Network**: Optional (may download build documentation)

### Expected Token Usage
- 8,000-12,000 tokens

### Dependencies
- **Upstream**: Stage 1 (Source code required)
- **Downstream**: Stage 4 (Actual compilation), Stage 5 (Build requirements inform script)

### Exact Commands & Script

```bash
#!/bin/bash
# stage_2_analyze_build.sh

WORKDIR="/path/to/xcompact3d/work"
cd $WORKDIR/Incompact3d

echo "=== Stage 2: Analyzing Build Process ==="

# Step 2.1: Examine build system
echo "--- Build System Files ---"
if [ -f "Makefile" ]; then
    echo "Makefile found. Extracting targets and variables:"
    grep -E "^[A-Za-z_][A-Za-z0-9_]*\s*:" Makefile | head -20
    grep -E "^(FC|CC|CXX|FFLAGS|CFLAGS|CXXFLAGS|LIBS|LDFLAGS)" Makefile
fi

if [ -f "CMakeLists.txt" ]; then
    echo "CMakeLists.txt found. Key cmake directives:"
    grep -E "(project|find_package|add_executable|set.*FLAGS)" CMakeLists.txt | head -30
fi

# Step 2.2: Read README and installation guides
echo "--- Installation Documentation ---"
for doc in README.md README README.txt INSTALL INSTALL.md docs/INSTALL docs/BUILD.md; do
    if [ -f "$doc" ]; then
        echo "Content of $doc:"
        head -100 "$doc"
        echo "---"
    fi
done

# Step 2.3: Extract compiler and library requirements
echo "--- Compiler and Library Requirements ---"
grep -r "gfortran\|ifort\|pgf90\|ftn" . --include="*.sh" --include="Makefile" --include="*.mk" 2>/dev/null
grep -r "OpenMPI\|MPICH\|mpifort\|mpicc" . --include="*.sh" --include="Makefile" --include="*.mk" 2>/dev/null
grep -r "fftw\|FFTW\|hdf5\|HDF5\|netcdf\|NETCDF" . --include="*.sh" --include="Makefile" --include="*.mk" 2>/dev/null

# Step 2.4: Examine source structure
echo "--- Source Code Structure ---"
find . -name "*.f90" -o -name "*.f95" | wc -l
echo "Total Fortran source files found."

# Step 2.5: Look for module dependencies
echo "--- Key Modules (interfaces) ---"
grep -h "^module " *.f90 2>/dev/null | sort -u | head -20

# Step 2.6: Document build options
echo "--- Build Configuration Options ---"
cat > BUILD_ANALYSIS.md <<'DOC'
# XCompact3D Build Analysis

## Build System Type
[Document: Makefile-based / CMake / Other]

## Required Compiler
- Fortran: [gfortran / ifort / pgf90]
- Version requirement: [Extract from docs]

## Required Libraries
### Essential
- MPI Implementation: [OpenMPI/MPICH/Intel MPI]
- FFTW3: [Version requirement, linked library]
- HDF5: [Version requirement, parallel support needed]
- LAPACK/BLAS: [MKL/OPENBLAS/LAPACK]

### Optional
- NetCDF: [if applicable]
- Python: [Version, for preprocessing]

## Typical Build Commands
[Extract from README/INSTALL]

### Configure Step
[Document any configure script invocation]

### Compilation Step
[Document make targets and typical invocation]

### Installation Step
[Document make install or equivalent]

## Compiler Flags (from Makefile)
[Extract FFLAGS, CFLAGS, optimization levels]

## Performance Considerations
[Document: OpenMP support, GPU acceleration options, etc.]

## Known Limitations/Warnings
[Extract from documentation]
DOC

echo "Build analysis complete. See BUILD_ANALYSIS.md"
```

### Output Artifacts
- File: `BUILD_ANALYSIS.md` - Comprehensive build documentation
- File: `MAKEFILE_EXTRACT.txt` - Parsed Makefile targets and variables
- File: `COMPILER_REQUIREMENTS.txt` - Specific compiler/library versions

---

## Stage 3: Query Slurm Cluster Resources (Parallel with Stage 1)

### Objective
Query target HPC cluster to assess available Slurm resources, partitions, node types, GPU availability, interconnect topology, and resource limits. This enables informed resource requests in job script.

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Execute Slurm commands (`sinfo`, `scontrol`, `slurm.conf` inspection), document cluster topology

### Hardware Requirements
- **CPU**: 1-2 cores
- **Memory**: 1-2 GB RAM
- **Storage**: 1 GB
- **Network**: Required (SSH to login node, Slurm daemon access)
- **Location**: Must execute on Slurm login node or cluster-accessible host

### Expected Token Usage
- 5,000-7,000 tokens

### Dependencies
- **Upstream**: None (independent)
- **Downstream**: Stage 5 (Resource info informs batch script)

### Exact Commands & Script

```bash
#!/bin/bash
# stage_3_query_slurm.sh
# NOTE: Execute this on the Slurm cluster login node

echo "=== Stage 3: Querying Slurm Cluster Resources ==="

# Create output file
OUTPUT_FILE="SLURM_CLUSTER_ASSESSMENT.txt"
> $OUTPUT_FILE

echo "Cluster Assessment Report" | tee -a $OUTPUT_FILE
echo "Generated: $(date)" | tee -a $OUTPUT_FILE
echo "===========================================" | tee -a $OUTPUT_FILE

# Step 3.1: Partition information
echo -e "\n--- Available Partitions ---" | tee -a $OUTPUT_FILE
sinfo -e | tee -a $OUTPUT_FILE

echo -e "\n--- Partition Details (extended) ---" | tee -a $OUTPUT_FILE
sinfo -p \* -l | tee -a $OUTPUT_FILE

# Step 3.2: Node information
echo -e "\n--- Node Summary ---" | tee -a $OUTPUT_FILE
sinfo -N -l | tee -a $OUTPUT_FILE

# Step 3.3: GPU information
echo -e "\n--- GPU Availability (if any) ---" | tee -a $OUTPUT_FILE
sinfo -l --Format="Node,Gres" 2>/dev/null || echo "Gres field not available" | tee -a $OUTPUT_FILE
sinfo --Format="NodeList,GresUsed,Gres" 2>/dev/null | tee -a $OUTPUT_FILE

# Step 3.4: Resource limits and constraints
echo -e "\n--- Resource Limits ---" | tee -a $OUTPUT_FILE
scontrol show config | grep -E "(MaxNodes|MaxCpus|MaxMemory|MaxTime|DefMemPerNode)" | tee -a $OUTPUT_FILE

# Step 3.5: Current cluster load
echo -e "\n--- Current Cluster Utilization ---" | tee -a $OUTPUT_FILE
sinfo --summarize 2>/dev/null | tee -a $OUTPUT_FILE

# Step 3.6: Job information (sample running jobs)
echo -e "\n--- Sample Running Jobs (to understand patterns) ---" | tee -a $OUTPUT_FILE
squeue --start | head -20 | tee -a $OUTPUT_FILE

# Step 3.7: Network information (if accessible)
echo -e "\n--- Node Interconnect and Topology ---" | tee -a $OUTPUT_FILE
sinfo --Format="NodeList,CPUs,Memory,Gres,Features,State" | tee -a $OUTPUT_FILE

# Step 3.8: slurm.conf information
echo -e "\n--- Slurm Configuration File Info ---" | tee -a $OUTPUT_FILE
if [ -f "/etc/slurm/slurm.conf" ]; then
    grep -E "(ClusterName|ControlMachine|NodeName|PartitionName|MaxCpusPerNode)" /etc/slurm/slurm.conf | head -20 | tee -a $OUTPUT_FILE
else
    echo "slurm.conf not directly accessible (normal for user)" | tee -a $OUTPUT_FILE
fi

# Step 3.9: Create summary in structured format
cat >> $OUTPUT_FILE <<'SUMMARY'

=== CLUSTER SUMMARY FOR JOB PLANNING ===

Key Parameters to Consider:
1. Recommended Partition: [Choose partition with appropriate resources]
2. Typical Node Count: [Based on problem size]
3. CPU cores per node: [Extract from sinfo output]
4. Memory per node: [Extract from sinfo output]
5. GPU availability: [Note if GPUs present]
6. Max wall-clock time: [Check partition defaults]
7. Network topology: [High-speed interconnect name]

Next Steps:
- Review SLURM_CLUSTER_ASSESSMENT.txt
- Select appropriate partition
- Estimate resources needed for XCompact3D job
- Create job script in Stage 5
SUMMARY

echo "Cluster assessment complete. See $OUTPUT_FILE"
```

### Output Artifacts
- File: `SLURM_CLUSTER_ASSESSMENT.txt` - Full cluster query output and summary
- File: `CLUSTER_TOPOLOGY.txt` - Network and node interconnect information
- File: `PARTITION_RECOMMENDATIONS.txt` - Suitable partitions for compute jobs

---

## Stage 4: Build and Compile XCompact3D

### Objective
Execute the complete build process: install required libraries (if needed), run configure/CMake, compile source code, and create executable.

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Install dependencies, execute build system, resolve compilation errors, create working executable

### Hardware Requirements
- **CPU**: 8-16 cores (parallel compilation with `-j`)
- **Memory**: 16-32 GB RAM (compilation memory overhead)
- **Storage**: 50-100 GB (source + build artifacts)
- **Network**: Optional (dependency downloads)
- **Location**: On cluster or on build node with compatible compiler

### Expected Token Usage
- 10,000-15,000 tokens

### Dependencies
- **Upstream**: Stage 1 (Source code), Stage 2 (Build analysis)
- **Downstream**: Stage 5 (Executable needed for job script)

### Exact Commands & Script

```bash
#!/bin/bash
# stage_4_build_compile.sh

WORKDIR="/path/to/xcompact3d/work"
INSTALL_PREFIX="${WORKDIR}/xcompact3d_install"

cd $WORKDIR/Incompact3d

echo "=== Stage 4: Building XCompact3D ==="

# Step 4.1: Load necessary modules (if using module system)
echo "--- Loading Required Modules ---"
module list
# Example module loads (adjust for your cluster):
# module load gcc/11.2.0
# module load openmpi/4.1.1
# module load fftw3/3.3.10
# module load hdf5/1.12.0

# Step 4.2: Set environment variables
echo "--- Setting Environment Variables ---"
export FC=gfortran              # or ifort, pgf90
export MPI_FC=mpifort
export MPI_CC=mpicc
export FFLAGS="-O3 -march=native -fopenmp"
export LDFLAGS="-L/usr/local/lib"
export CPPFLAGS="-I/usr/local/include"

# Step 4.3: Install dependencies if needed
echo "--- Installing Dependencies (if required) ---"
# Check and install FFTW3
if ! pkg-config --exists fftw3; then
    echo "Installing FFTW3..."
    wget http://www.fftw.org/fftw-3.3.10.tar.gz
    tar xzf fftw-3.3.10.tar.gz
    cd fftw-3.3.10
    ./configure --prefix=$INSTALL_PREFIX --enable-mpi --enable-fortran
    make -j 8
    make install
    cd $WORKDIR/Incompact3d
fi

# Step 4.4: Configure (if CMake-based)
if [ -f "CMakeLists.txt" ]; then
    echo "--- CMake Configuration ---"
    mkdir -p build
    cd build
    cmake .. \
        -DCMAKE_Fortran_COMPILER=$MPI_FC \
        -DCMAKE_C_COMPILER=$MPI_CC \
        -DCMAKE_Fortran_FLAGS="$FFLAGS" \
        -DCMAKE_INSTALL_PREFIX=$INSTALL_PREFIX \
        -DENABLE_MPI=ON \
        -DENABLE_OPENMP=ON
    cd $WORKDIR/Incompact3d
fi

# Step 4.5: Compile
echo "--- Building Executable ---"
if [ -f "Makefile" ]; then
    # Makefile-based build
    echo "Using Makefile..."
    make clean
    make -j 8 2>&1 | tee BUILD.log
elif [ -d "build" ]; then
    # CMake-based build
    echo "Using CMake..."
    cd build
    make -j 8 2>&1 | tee BUILD.log
    cd $WORKDIR/Incompact3d
fi

# Step 4.6: Verify executable
echo "--- Verifying Executable ---"
if [ -f "xcompact3d" ] || [ -f "Incompact3d" ] || [ -f "build/xcompact3d" ]; then
    EXECUTABLE=$(find . -maxdepth 2 -name "xcompact3d" -o -name "Incompact3d" -type f -executable | head -1)
    echo "Executable found: $EXECUTABLE"
    echo "Executable size: $(ls -lh $EXECUTABLE | awk '{print $5}')"
    echo "Executable path (absolute): $(cd $(dirname $EXECUTABLE) && pwd)/$(basename $EXECUTABLE)"

    # Step 4.7: Test executable (basic validation)
    echo "--- Basic Executable Test ---"
    $EXECUTABLE --help 2>&1 | head -20 || echo "Help not available, executable likely valid"
    ldd $EXECUTABLE 2>/dev/null | grep "fftw\|hdf5\|mpi" || echo "Dependency check skipped"

else
    echo "ERROR: Executable not found after build!"
    echo "Check BUILD.log for errors"
    exit 1
fi

# Step 4.8: Document build summary
cat > BUILD_SUMMARY.txt <<EOF
Build Summary
=============
Date: $(date)
Source: $WORKDIR/Incompact3d
Build Status: SUCCESS
Executable: $EXECUTABLE
Executable Size: $(ls -lh $EXECUTABLE | awk '{print $5}')

Compiler: $FC
MPI Compiler: $MPI_FC
Compiler Flags: $FFLAGS

Libraries Linked:
$(ldd $EXECUTABLE 2>/dev/null || echo "Library inspection not available")

Build Log: BUILD.log
EOF

echo "Build complete. See BUILD_SUMMARY.txt and BUILD.log"
```

### Output Artifacts
- Executable: `./Incompact3d` (or equivalent)
- File: `BUILD.log` - Complete build output
- File: `BUILD_SUMMARY.txt` - Build summary and executable metadata
- Directory: `./build/` - Build artifacts (if CMake-based)

---

## Stage 5: Create Slurm Batch Script and Resource Configuration

### Objective
Synthesize information from Stages 2, 3, and 4 to create a production-ready Slurm batch script with appropriate resource requests, module loads, environment setup, and job execution commands.

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Design batch script, specify resource requests, handle I/O, set environment, prepare input files

### Hardware Requirements
- **CPU**: 2-4 cores (script generation, validation)
- **Memory**: 4-8 GB RAM
- **Storage**: 5-10 GB
- **Network**: None required

### Expected Token Usage
- 8,000-12,000 tokens

### Dependencies
- **Upstream**: Stage 2 (Build requirements), Stage 3 (Cluster resources), Stage 4 (Executable path)
- **Downstream**: Stage 6 (Script is submitted in Stage 6)

### Exact Commands & Script

```bash
#!/bin/bash
# stage_5_create_batch_script.sh

WORKDIR="/path/to/xcompact3d/work"
EXECUTABLE="$WORKDIR/Incompact3d/xcompact3d"
INSTALL_PREFIX="$WORKDIR/xcompact3d_install"

echo "=== Stage 5: Creating Slurm Batch Script ==="

# Verify executable exists
if [ ! -f "$EXECUTABLE" ]; then
    echo "ERROR: Executable not found at $EXECUTABLE"
    exit 1
fi

# Create the batch script
cat > submit_xcompact3d.slurm <<'SLURM_SCRIPT'
#!/bin/bash
#SBATCH --job-name=xcompact3d_run
#SBATCH --partition=compute              # Modify based on cluster
#SBATCH --nodes=2                        # Number of compute nodes
#SBATCH --ntasks-per-node=32             # MPI tasks per node
#SBATCH --cpus-per-task=2                # OpenMP threads per task
#SBATCH --time=02:00:00                  # Wall-clock time HH:MM:SS
#SBATCH --mem-per-cpu=2G                 # Memory per CPU
#SBATCH --output=xcompact3d_%j.out       # stdout file
#SBATCH --error=xcompact3d_%j.err        # stderr file
#SBATCH --mail-type=BEGIN,END,FAIL       # Email notifications
#SBATCH --mail-user=your-email@example.com

echo "=== XCompact3D Job Started ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Start time: $(date)"
echo "Hostname: $(hostname)"

# Step 5.1: Load modules
echo "--- Loading Modules ---"
module purge
module load gcc/11.2.0                   # Adjust to cluster modules
module load openmpi/4.1.1
module load fftw3/3.3.10
module load hdf5/1.12.0
module list

# Step 5.2: Set environment
echo "--- Setting Up Environment ---"
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OMP_PROC_BIND=close
export OMP_PLACES=threads
export FFTW_PLAN_MODE=FFTW_MEASURE

# Verify executable
EXEC_PATH="/path/to/xcompact3d/Incompact3d/xcompact3d"
if [ ! -f "$EXEC_PATH" ]; then
    echo "ERROR: Executable not found at $EXEC_PATH"
    exit 1
fi

# Step 5.3: Create run directory and input files
echo "--- Preparing Run Directory ---"
RUN_DIR=$TMPDIR/xcompact3d_run_${SLURM_JOB_ID}
mkdir -p $RUN_DIR
cd $RUN_DIR

echo "Run directory: $RUN_DIR"

# Step 5.4: Copy input files (if needed)
# cp /path/to/input/deck.f90 $RUN_DIR/ 2>/dev/null || true
# cp /path/to/input/parameters.txt $RUN_DIR/ 2>/dev/null || true

# Step 5.5: Verify MPI and environment
echo "--- Verifying Environment ---"
echo "MPI Implementation:"
mpirun --version 2>/dev/null || echo "MPI version check unavailable"
echo "Number of MPI tasks: $((SLURM_NNODES * SLURM_NTASKS_PER_NODE))"
echo "CPUs per task: $SLURM_CPUS_PER_TASK"
echo "OpenMP threads: $OMP_NUM_THREADS"

# Step 5.6: Run application
echo "--- Launching XCompact3D ==="
echo "Command:"
echo "mpirun -n $((SLURM_NNODES * SLURM_NTASKS_PER_NODE)) $EXEC_PATH"

srun $EXEC_PATH 2>&1 | tee xcompact3d_output.log

# Alternative if srun not working:
# mpirun -np $((SLURM_NNODES * SLURM_NTASKS_PER_NODE)) \
#     --bind-to=core:overload-allowed \
#     $EXEC_PATH 2>&1 | tee xcompact3d_output.log

# Step 5.7: Capture output and exit status
JOB_EXIT_CODE=$?

# Step 5.8: Post-processing / output collection
echo "--- Job Completion ---"
echo "Exit code: $JOB_EXIT_CODE"
echo "End time: $(date)"

# Optional: Copy output files to persistent storage
echo "--- Copying Results ---"
# RESULTS_DIR="/home/user/xcompact3d_results/${SLURM_JOB_ID}"
# mkdir -p $RESULTS_DIR
# cp -r $RUN_DIR/* $RESULTS_DIR/ 2>/dev/null || echo "Result copy completed with some files skipped"

# Cleanup temporary directory (optional)
# rm -rf $RUN_DIR

exit $JOB_EXIT_CODE
SLURM_SCRIPT

chmod +x submit_xcompact3d.slurm

# Create resource configuration summary
cat > BATCH_SCRIPT_CONFIG.txt <<'CONFIG'
SLURM Batch Script Configuration
==================================

Job Parameters:
  - Job name: xcompact3d_run
  - Partition: compute
  - Nodes requested: 2
  - Tasks per node: 32
  - CPUs per task (OpenMP threads): 2
  - Total MPI processes: 64
  - Memory per CPU: 2 GB
  - Wall-clock time: 02:00:00

Resource Calculation:
  - Total CPU cores: 2 nodes × 32 cores/node = 64 cores
  - Total memory: 64 tasks × 2 threads × 2 GB = 256 GB
  - Parallel decomposition: 64 MPI processes × 2 OpenMP threads

Module Dependencies:
  - gcc/11.2.0 (compiler)
  - openmpi/4.1.1 (MPI library)
  - fftw3/3.3.10 (FFT library)
  - hdf5/1.12.0 (parallel I/O)

OpenMP Configuration:
  - OMP_NUM_THREADS = $SLURM_CPUS_PER_TASK (2)
  - OMP_PROC_BIND = close (thread affinity)
  - OMP_PLACES = threads (bind to hardware threads)

FFTW Configuration:
  - FFTW_PLAN_MODE = FFTW_MEASURE (balanced planning time/execution)

I/O and Output:
  - stdout: xcompact3d_${SLURM_JOB_ID}.out
  - stderr: xcompact3d_${SLURM_JOB_ID}.err
  - Run directory: $TMPDIR/xcompact3d_run_${SLURM_JOB_ID}
  - Log file: xcompact3d_output.log (in run directory)

Job Notification:
  - Email on BEGIN, END, FAIL events
  - Recipient: your-email@example.com (MODIFY THIS)

Execution Method:
  - Primary: srun (Slurm run command, recommended)
  - Alternative: mpirun (if srun unavailable)

CONFIG

echo "Batch script created: submit_xcompact3d.slurm"
echo "Configuration documented: BATCH_SCRIPT_CONFIG.txt"
echo ""
echo "Next step: Review submit_xcompact3d.slurm and modify:"
echo "  1. Partition name (--partition)"
echo "  2. Node count (--nodes)"
echo "  3. MPI tasks per node (--ntasks-per-node)"
echo "  4. Wall-clock time (--time)"
echo "  5. Module names (module load commands)"
echo "  6. Executable path"
echo "  7. Email address for notifications"
echo "  8. Input/output file paths"
```

### Output Artifacts
- File: `submit_xcompact3d.slurm` - Complete, executable Slurm batch script
- File: `BATCH_SCRIPT_CONFIG.txt` - Resource configuration documentation
- File: `CUSTOMIZE_CHECKLIST.txt` - Required customizations before submission

---

## Stage 6: Submit Job and Monitor Execution

### Objective
Submit the job using `sbatch`, monitor job status with `squeue` and `scontrol`, retrieve logs, validate application startup, and troubleshoot any runtime issues.

### Specialist Agent
- **Type**: `general-purpose`
- **Task**: Execute sbatch, poll job status, retrieve and analyze logs, verify successful startup

### Hardware Requirements
- **CPU**: 1-2 cores
- **Memory**: 2-4 GB RAM
- **Storage**: 5-10 GB (log collection)
- **Network**: Required (Slurm commands on login node)
- **Location**: Must execute on Slurm login node

### Expected Token Usage
- 7,000-10,000 tokens

### Dependencies
- **Upstream**: Stage 5 (Batch script)
- **Downstream**: None (final stage)

### Exact Commands & Script

```bash
#!/bin/bash
# stage_6_submit_and_monitor.sh
# NOTE: Execute this on the Slurm cluster login node

WORKDIR="/path/to/xcompact3d/work"
cd $WORKDIR

echo "=== Stage 6: Submit Job and Monitor Execution ==="

# Step 6.1: Pre-submission validation
echo "--- Pre-submission Checks ---"

if [ ! -f "submit_xcompact3d.slurm" ]; then
    echo "ERROR: submit_xcompact3d.slurm not found!"
    exit 1
fi

echo "Batch script syntax check:"
bash -n submit_xcompact3d.slurm && echo "✓ Script syntax valid" || echo "✗ Script has syntax errors"

echo ""
echo "Batch script content preview:"
head -30 submit_xcompact3d.slurm

# Step 6.2: Submit job
echo -e "\n--- Submitting Job ---"
JOB_ID=$(sbatch submit_xcompact3d.slurm | awk '{print $NF}')

if [ -z "$JOB_ID" ]; then
    echo "ERROR: Job submission failed!"
    exit 1
fi

echo "✓ Job submitted successfully"
echo "Job ID: $JOB_ID"
echo "Submission time: $(date)"

# Create submission record
cat > JOB_SUBMISSION_RECORD.txt <<EOF
Job Submission Record
=====================
Job ID: $JOB_ID
Job name: xcompact3d_run
Batch script: submit_xcompact3d.slurm
Submission time: $(date)
Submitted by: $(whoami)
Working directory: $WORKDIR

Next monitoring commands:
  squeue --job=$JOB_ID                    # Check job status
  scontrol show job $JOB_ID               # Detailed job info
  tail -f xcompact3d_${JOB_ID}.out       # Monitor stdout (once file created)
  tail -f xcompact3d_${JOB_ID}.err       # Monitor stderr (once file created)
  scancel $JOB_ID                         # Cancel job if needed
EOF

echo "Submission record saved: JOB_SUBMISSION_RECORD.txt"

# Step 6.3: Initial status check
echo -e "\n--- Initial Job Status ---"
sleep 2
squeue --job=$JOB_ID
scontrol show job $JOB_ID | head -40

# Step 6.4: Monitoring loop (optional - can be extended)
echo -e "\n--- Job Monitoring ---"

MONITOR_DURATION=300  # Monitor for 5 minutes
INTERVAL=10           # Check every 10 seconds
ELAPSED=0

echo "Monitoring job for ${MONITOR_DURATION}s..."
echo "Time | State | Nodes | CPUs | Memory(MB) | Time Used"
echo "------|-------|-------|------|------------|----------"

while [ $ELAPSED -lt $MONITOR_DURATION ]; do
    JOB_STATE=$(squeue -j $JOB_ID -h -o %T)

    if [ -z "$JOB_STATE" ]; then
        echo "Job no longer in queue. Checking accounting..."
        sacct -j $JOB_ID --format=JobID,JobName,State,Elapsed,ExitCode | head -10
        break
    fi

    TIME_USED=$(squeue -j $JOB_ID -h -o %M)
    NODES=$(squeue -j $JOB_ID -h -o %D)
    CPUS=$(squeue -j $JOB_ID -h -o %C)
    MEM=$(squeue -j $JOB_ID -h -o %m)

    echo "$(printf '%3ds' $ELAPSED) | $JOB_STATE | $NODES | $CPUS | $MEM | $TIME_USED"

    if [ "$JOB_STATE" = "RUNNING" ]; then
        echo "Job is now RUNNING!"

        # Check for output files
        if [ -f "xcompact3d_${JOB_ID}.out" ]; then
            echo "Output log found. Latest entries:"
            tail -5 "xcompact3d_${JOB_ID}.out"
        fi
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

# Step 6.5: Post-submission validation
echo -e "\n--- Post-Submission Validation ---"

if [ -f "xcompact3d_${JOB_ID}.out" ]; then
    echo "Output file created: xcompact3d_${JOB_ID}.out"
    echo "File size: $(ls -lh xcompact3d_${JOB_ID}.out | awk '{print $5}')"
    echo "First 20 lines of output:"
    head -20 "xcompact3d_${JOB_ID}.out"
else
    echo "Output file not yet created (job may still be staging)"
fi

if [ -f "xcompact3d_${JOB_ID}.err" ]; then
    echo ""
    echo "Error file created: xcompact3d_${JOB_ID}.err"
    if [ -s "xcompact3d_${JOB_ID}.err" ]; then
        echo "Errors detected:"
        head -20 "xcompact3d_${JOB_ID}.err"
    else
        echo "Error file is empty (no errors)"
    fi
fi

# Step 6.6: Detailed job information
echo -e "\n--- Detailed Job Information ---"
echo "Full job details:"
scontrol show job $JOB_ID

# Step 6.7: Create monitoring command reference
cat > MONITORING_COMMANDS.txt <<'MONITOR'
Monitoring Commands Reference
=============================

Basic Status:
  squeue --job=<JOB_ID>                 # Quick status check
  scontrol show job <JOB_ID>            # Detailed job information

View Output:
  less xcompact3d_<JOB_ID>.out          # Browse stdout
  less xcompact3d_<JOB_ID>.err          # Browse stderr
  tail -f xcompact3d_<JOB_ID>.out       # Stream stdout (Ctrl+C to stop)
  tail -f xcompact3d_<JOB_ID>.err       # Stream stderr

Statistics:
  sstat -j <JOB_ID> --format=...        # Real-time job statistics
  sstat -j <JOB_ID> --allsteps --format=AveCPU,AvePages,AveRSS,AveVMSize,MaxRSS,MaxVMSize

Job History:
  sacct -j <JOB_ID>                     # Job accounting info (after completion)
  sacct -j <JOB_ID> --format=JobID,JobName,State,Elapsed,ExitCode,MaxRSS,MaxVMSize

Node Information:
  sinfo -n <node_name>                  # Check specific node status
  squeue -w <node_name>                 # See jobs on specific node

Cancel Job:
  scancel <JOB_ID>                      # Cancel running job

Advanced Monitoring:
  watch -n 1 'squeue -j <JOB_ID>'      # Update status every 1 second
  while true; do squeue -j <JOB_ID>; sleep 5; done  # Loop monitoring

Troubleshooting:
  scontrol update JobId=<JOB_ID> Priority=<LEVEL>   # Change priority
  sinfo --deferred                       # Scheduled but not running jobs
  squeue --sort=-Priority               # Show priority order
MONITOR

echo "Monitoring commands saved: MONITORING_COMMANDS.txt"

# Step 6.8: Summary report
cat > EXECUTION_SUMMARY.txt <<EOF
XCompact3D Job Execution Summary
=================================
Job ID: $JOB_ID
Batch script: submit_xcompact3d.slurm
Submission time: $(date)

Output files:
  stdout: xcompact3d_${JOB_ID}.out
  stderr: xcompact3d_${JOB_ID}.err

Key Validation Steps (post-execution):
1. Check output file exists and has content
2. Search for initialization messages
3. Verify no MPI errors in first output section
4. Check final convergence/result messages
5. Compare output format to baseline

Example validation grep patterns:
  grep -i "error\|warning\|fail" xcompact3d_${JOB_ID}.out
  grep -i "initialization\|starting\|ready" xcompact3d_${JOB_ID}.out
  tail -20 xcompact3d_${JOB_ID}.out  # Check final status

Log Analysis Commands:
  wc -l xcompact3d_${JOB_ID}.out                        # Line count
  grep "^[0-9]" xcompact3d_${JOB_ID}.out | wc -l        # Timestep count
  grep -c "MPI" xcompact3d_${JOB_ID}.out                # MPI messages
EOF

echo "Execution summary: EXECUTION_SUMMARY.txt"
echo -e "\n=== Stage 6 Complete ==="
```

### Output Artifacts
- File: `JOB_SUBMISSION_RECORD.txt` - Job ID and submission details
- File: `xcompact3d_<JOB_ID>.out` - Job stdout (created by Slurm)
- File: `xcompact3d_<JOB_ID>.err` - Job stderr (created by Slurm)
- File: `MONITORING_COMMANDS.txt` - Reference for status checking
- File: `EXECUTION_SUMMARY.txt` - Post-execution validation guide

---

## Parallel Execution Strategy

### Timeline and Dependencies Graph

```
START
  │
  ├─→ [Stage 1] Download Source Code (5-8K tokens)
  │     │
  │     ├─→ [Stage 2] Analyze Build Process (8-12K tokens)
  │           │
  │           └─→ [Stage 4] Build & Compile (10-15K tokens)
  │                 └─→ [Stage 5] Create Batch Script (8-12K tokens)
  │                       └─→ [Stage 6] Submit & Monitor (7-10K tokens)
  │
  └─→ [Stage 3] Query Slurm Resources (5-7K tokens)
        └─→ ┘ (merges into Stage 5)

Total Sequential Path: Stages 1→2→4→5→6
Parallel Opportunities: 1 and 3 can run in parallel; 3 outputs feed into 5
```

### Recommended Execution Schedule

| Execution Phase | Stages | Parallelism | Duration | Notes |
|---|---|---|---|---|
| **Phase A (Discovery)** | 1, 3 | 2 agents parallel | ~30 min | Source download and cluster assessment in parallel |
| **Phase B (Analysis & Build)** | 2, 4 | Sequential | ~60 min | Depends on Stage 1 results; Stage 2 informs Stage 4 |
| **Phase C (Submission)** | 5, 6 | Sequential | ~30 min | Merge Stage 2, 3, 4 info; then submit and monitor |
| **Total Elapsed Time** | All 6 | Mixed | ~120 min | Can parallelize 1+3, rest are dependent |
| **Total Token Budget** | All 6 | Sum | 43-64K tokens | Parallel execution reduces wall-clock time |

---

## Critical Files and Checkpoints

### Essential Deliverables

| Stage | Primary Output | Secondary Artifacts | Validation Checkpoint |
|---|---|---|---|
| 1 | `Incompact3d/` source tree | `DEPENDENCY_MANIFEST.txt` | Source tree integrity |
| 2 | `BUILD_ANALYSIS.md` | Makefile/CMake inspection | Build system identified |
| 3 | `SLURM_CLUSTER_ASSESSMENT.txt` | Partition/node info | Cluster resources documented |
| 4 | `xcompact3d` executable | `BUILD.log`, `BUILD_SUMMARY.txt` | Executable runs without errors |
| 5 | `submit_xcompact3d.slurm` | Resource config, checklist | Script is syntactically valid |
| 6 | `xcompact3d_<JOB_ID>.out` | Submission record, logs | Job executed and output logged |

### Error Handling and Rollback

| Stage | Common Failure | Recovery Action |
|---|---|---|
| 1 | Network error cloning repo | Use SSH URL instead of HTTPS, or download ZIP |
| 2 | Missing Makefile/CMake | Inspect docs/ directory or check for build.sh |
| 3 | No Slurm access | Must execute on login node; verify `sinfo` available |
| 4 | Missing MPI/FFTW libraries | Install via module system; consult Stage 3 cluster assessment |
| 4 | Compilation errors | Review `BUILD.log`; adjust compiler flags; rebuild from Stage 4 |
| 5 | Invalid SLURM directives | Validate against cluster's slurm.conf; reduce resource requests |
| 6 | Job submission rejected | Check partition availability from Stage 3; verify resource limits |
| 6 | Job hangs during execution | Check output file in real-time; use `sstat` for memory/CPU usage |

---

## Resource Estimation Summary

### Compute Resources for Agent Execution

| Stage | Agent Type | CPU Cores | RAM | Duration | Network | Notes |
|---|---|---|---|---|---|
| 1 | general-purpose | 1-2 | 2-4 GB | 10-15 min | Required | GitHub access |
| 2 | general-purpose | 2-4 | 4-8 GB | 15-20 min | Optional | Code analysis |
| 3 | general-purpose | 1-2 | 1-2 GB | 5-10 min | Required | Must run on login node |
| 4 | general-purpose | 8-16 | 16-32 GB | 30-60 min | Optional | Compilation overhead |
| 5 | general-purpose | 2-4 | 4-8 GB | 10-15 min | None | Script generation |
| 6 | general-purpose | 1-2 | 2-4 GB | 5-10 min | Required | Slurm command execution |
| **Total** | - | **19-44** | **29-62 GB** | **75-130 min** | Mixed | **Parallel stages 1+3** |

### HPC Job Resource Requests (from Stage 5 script)

| Resource | Value | Justification |
|---|---|---|
| **Nodes** | 2 | Adjust based on problem size; start conservative |
| **Tasks per node** | 32 | Typical node core count; verify with Stage 3 data |
| **CPUs per task** | 2 | OpenMP parallelism; requires 2+ cores per node |
| **Total MPI processes** | 64 (2 × 32) | 64-way parallel decomposition |
| **Memory per CPU** | 2 GB | Adjust based on domain size and Stage 4 profiling |
| **Wall-clock time** | 2 hours | Conservative estimate; reduce after first run |
| **Partition** | compute | Verify with Stage 3 cluster assessment |

---

## Verification and Validation Plan

### Post-Deployment Testing

```bash
# Test 1: Executable functionality (Stage 4)
$EXECUTABLE --help
ldd $EXECUTABLE | grep -E "fftw|hdf5|mpi"

# Test 2: MPI correctness (Stage 6)
grep -i "mpi.*error\|segmentation\|abort" xcompact3d_${JOB_ID}.out
grep -c "rank.*initialized" xcompact3d_${JOB_ID}.out  # Should have 64 ranks

# Test 3: Job completion status (Stage 6)
sacct -j $JOB_ID --format=JobID,State,ExitCode
# Expected: State=COMPLETED, ExitCode=0:0

# Test 4: Output data integrity (Stage 6)
tail -20 xcompact3d_${JOB_ID}.out  # Look for convergence metrics
# Expected: Final timestep summary, convergence data

# Test 5: Performance baseline (Stage 6)
grep "time per step\|elapsed time" xcompact3d_${JOB_ID}.out
# Log performance metrics for future comparison
```

### Success Criteria

1. ✓ Source code downloaded and verified
2. ✓ Build system identified and documented
3. ✓ Cluster resources queried and suitable partition identified
4. ✓ Executable compiled without errors
5. ✓ Batch script created with appropriate resource requests
6. ✓ Job submitted via `sbatch` successfully
7. ✓ Job enters RUNNING state within resource limits
8. ✓ Output file generated with valid XCompact3D output
9. ✓ No MPI errors or segmentation faults in logs
10. ✓ Job completes with exit code 0

---

## Next Steps After Plan Approval

Once this plan is approved:

1. **Execute in parallel**: Launch Stage 1 (download) and Stage 3 (cluster assessment) agents simultaneously
2. **Execute Stage 2**: Analyze build process based on Stage 1 output
3. **Execute Stage 4**: Build and compile using Stage 2 recommendations
4. **Execute Stage 5**: Create batch script synthesizing Stages 2, 3, 4
5. **Execute Stage 6**: Submit job and monitor execution
6. **Document results**: Archive all logs, outputs, and performance metrics for future reference

---

## Conclusion

This plan provides a structured, agent-based approach to deploying XCompact3D on an HPC cluster. By decomposing the task into 6 independent or sequentially-dependent stages, assigning specialist agents, and documenting exact commands and resource requirements, it enables reproducible, scalable scientific computing workflows. Parallel execution of independent stages (1 + 3) reduces total wall-clock time while maintaining dependency integrity.


