---
case: case_001_xcompact3d_deployment
framework: agents_sdk
model: qwen3.5:9b
provider: ollama
session_id: None
duration_ms: 39190
duration_wall_s: 39.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:05:58.686294+00:00
error: None
---

# Plan

# Deployment Plan: XCompact3D on Slurm HPC Cluster

| Document Version | 1.0 |
| :--- | :--- |
| **Target Cluster** | Slurm-Managed HPC Cluster |
| **Working Directory** | `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir` |
| **Application** | XCompact3D (Incompact3D) |
| **Status** | Planning (No Execution) |

---

## 1. Executive Summary
This deployment plan outlines the orchestration of five distinct stages to acquire, build, configure, and execute the XCompact3D application on a Slurm-managed High-Performance Computing (HPC) cluster. The plan involves five specialist agents. Stages 1 and 2 are executed in parallel due to lack of dependency. Subsequent stages follow a linear dependency chain: **Acquisition ➔ Build ➔ Job Submission ➔ Monitoring**. All commands are designed to be executed within the specified working directory.

---

## 2. Stage Details & Agent Specifications

### Stage 1: Source Code Acquisition & Dependency Check
*   **Objective:** Download the upstream repository and verify local package manager availability for base dependencies.
*   **Agent:** `SourceAcquisitionAgent`
*   **Dependency:** None (Starts first).
*   **Expected Tokens (Context):** ~600 tokens.
*   **Hardware Requirements:**
    *   **Processors:** 2 vCPUs (Minimum)
    *   **Memory:** 2 GB RAM
    *   **Storage:** 1 GB Disk I/O
    *   **Network:** Standard LAN
*   **Detailed Commands:**
    ```bash
    # Navigate to working directory
    cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

    # Clone the main repository from upstream
    git clone --branch dev https://github.com/xcompact3d/Incompact3d.git

    # Fetch submodules (essential for full build)
    cd Incompact3d
    git submodule update --init --recursive

    # Check for system dependencies (Example for Ubuntu/CentOS)
    # Note: Specific package manager (apt/yum) chosen based on cluster OS
    # Command to list dependencies to be installed:
    grep -E '^depend' Makefile  # Or check configure script requirements
    ```
*   **Parallelism:** Can run simultaneously with Stage 2.

---

### Stage 2: Cluster Topology & Resource Query
*   **Objective:** Inspect the Slurm cluster to identify available partitions, node types, GPU availability, and network interconnects to optimize resource requests.
*   **Agent:** `ClusterTopologyAgent`
*   **Dependency:** None (Starts first).
*   **Expected Tokens (Context):** ~450 tokens.
*   **Hardware Requirements:**
    *   **Processors:** 1 vCPU
    *   **Memory:** 1 GB RAM
    *   **Storage:** Read-only access to Cluster Management System
    *   **Network:** Slurm Control Daemon access
*   **Detailed Commands:**
    ```bash
    # 1. List nodes and partitions
    sinfo -p

    # 2. Query detailed node information (CPU, GPU, Architecture)
    sinfo -h

    # 3. Visualize node topology (if available on the node)
    # scontrol show cluster all

    # 4. Check available GPUs on nodes
    sinfo -N | grep -B 1 "gpu"  # Logic to identify nodes with GPU resources

    # 5. Check partition availability
    scontrol show partition

    # 6. List network fabrics (if interconnect info available via Slurm DB)
    scontrol show allocations
    ```
*   **Parallelism:** Can run simultaneously with Stage 1.
*   **Output Artifact:** A JSON log file `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm_topology_report.json` (simulated creation).

---

### Stage 3: Build Configuration & Compilation
*   **Objective:** Configure the application based on Stage 2 findings (selecting MPI, HDF5, CUDA options) and compile the source code.
*   **Agent:** `CompilerAgent`
*   **Dependency:** Stage 1 (Must have source code).
*   **Expected Tokens (Context):** ~1200 tokens (Complex logic for build flags).
*   **Hardware Requirements:**
    *   **Processors:** 8 vCPUs (to utilize make flags like `-j8`)
    *   **Memory:** 32 GB RAM (Build artifacts)
    *   **Storage:** 20 GB Temporary Disk Space
    *   **GPU:** Optional (for compiling CUDA kernels if enabled)
*   **Detailed Commands:**
    ```bash
    # Ensure git submodules are updated
    # Enter source directory
    cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/Incompact3d

    # 1. Configure the application (Example using standard build options)
    make configure \
       --with-MPI=openmpi \
       --with-HDF5=/usr/local \
       --with-PETSc=/usr/local \
       --with-OpenMP=off \
       --with-CUDA=on \
       --enable-fortran

    # 2. Check dependency availability before full config
    # Assuming configure script checks for pkgconfig files
    # Command to install missing libraries if needed:
    # sudo apt-get update && sudo apt-get install libhdf5-openmpi-dev petsc3.9 libfftw3-dev

    # 3. Compile the application (Parallelize with number of cores)
    make -j$(nproc) -C bin

    # 4. Validate build artifacts
    ls -l bin/Incompact3d*

    # 5. Generate execution script
    cp bin/run_all_executable ./run_app.sh
    chmod +x ./run_app.sh
    ```
*   **Parallelism:** Serial Stage (Must wait for Stage 1).

---

### Stage 4: Job Submission Script Generation
*   **Objective:** Create a Slurm batch script (`srun` or `mpi` launcher) that requests appropriate resources based on Stage 2 (Cluster Topology) and Stage 3 (Binary Location), then submit the job.
*   **Agent:** `SchedulingAgent`
*   **Dependency:** Stage 3 (Must finish compiling).
*   **Expected Tokens (Context):** ~500 tokens.
*   **Hardware Requirements:**
    *   **Processors:** 2 vCPUs
    *   **Memory:** 2 GB RAM
    *   **Storage:** Minimal (Script IO)
    *   **Network:** Control daemon access
*   **Batch Script Content (`submit_batch.sh`):**
    ```bash
    #!/bin/bash
    # Slurm Batch Script for XCompact3D Deployment
    # Working Directory: $WORKING_DIR=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

    # Resource Requests (Adjust based on Stage 2 findings)
    # Requesting 2 GPUs (if available), 100 CPU-hours, and 200GB Memory
    # Nodes: 16 (MPI)

    # Clean previous runs
    rm -rf $WORKING_DIR/logs $WORKING_DIR/checkpoint
    mkdir -p $WORKING_DIR/logs

    # Set environment variables
    export OMP_NUM_THREADS=16
    export SLURM_MPIDIR=/usr/lib64/openmpi/bin
    export LD_LIBRARY_PATH=/usr/lib64/openmpi/lib64:$LD_LIBRARY_PATH
    export MPI_HOME=/usr/lib64/openmpi

    # Run the executable
    srun -n 1600 -G 2 --partition=compute --time=4:00:00 \
        $WORKING_DIR/Incompact3d/bin/Incompact3d \
        -i $WORKING_DIR/input_file_003D.in \
        -o $WORKING_DIR/outputs \
        -l $WORKING_DIR/logs/stdout.log

    # Capture exit codes
    if [ $? -eq 0 ]; then
        echo "Job completed successfully."
        exit 0
    else
        echo "Job failed with exit code $?"
        exit $1
    fi
    ```
    ```bash
    # Submit the job
    sbatch submit_batch.sh
    # Save job ID for monitoring
    JOB_ID=$(sbatch submit_batch.sh | tail -1 | awk '{print $NF}')
    echo "Job ID: $JOB_ID submitted."
    ```
*   **Parallelism:** Serial Stage.
*   **Output Artifact:** Slurm Job ID (`JobID_XXXXX`).

---

### Stage 5: Job Monitoring & Validation
*   **Objective:** Monitor the submitted Slurm job, ensure it does not crash, and verify output integrity.
*   **Agent:** `ValidationAgent`
*   **Dependency:** Stage 4 (Job must be running or completed).
*   **Expected Tokens (Context):** ~400 tokens.
*   **Hardware Requirements:**
    *   **Processors:** 4 vCPUs
    *   **Memory:** 4 GB RAM
    *   **Storage:** 10 GB (for log analysis)
    *   **Network:** Access to job logs
*   **Detailed Commands:**
    ```bash
    # 1. Check Job Status
    squeue -j $JOB_ID -o "%ID %JOB_NAME %TOUT %MEM"

    # 2. Once completed (or after 3s of idle), check logs
    tail -f $WORKING_DIR/logs/stdout.log

    # 3. Analyze exit codes
    if squeue -j $JOB_ID | grep -q "R"; then # If RUNNING
       echo "Job is Running"
       tail -n -100 $WORKING_DIR/logs/stdout.log
    elif squeue -j $JOB_ID | grep -q "C"; then # COMPLETED
       echo "Job Completed"
       # Validate output files exist
       exists_check -p $WORKING_DIR/outputs
    else
        echo "Job Failed, check stderr logs"
        cat $WORKING_DIR/logs/stderr.log
    fi

    # 4. Gather metrics for report
    scontrol show job $JOB_ID
    ```
*   **Parallelism:** Serial Stage.
*   **Success Criteria:** Job status `C` (Completed), Exit Code `0`, Output directory populated with `*.h5` or `*.out` files.

---

## 3. Summary of Resource Allocation

| Phase | Agent Role | Estimated Cost/Memory | Duration Est. |
| :--- | :--- | :--- | :--- |
| **Stage 1** | Source Acquisition | Low | ~1 Minute |
| **Stage 2** | Cluster Probe | Low | ~30 Seconds |
| **Stage 3** | Build/Compile | High (RAM/IO) | ~15-30 Minutes |
| **Stage 4** | Submission | Low | ~10 Seconds |
| **Stage 5** | Monitor/Validate | Medium | Dynamic (Runtime) |

**Total Estimated Deployment Time:** Build time + Runtime + Queue wait time.
**Note:** The plan assumes a clean checkout and standard Slurm installation (`slurmdbd`). If dependencies are missing at Stage 1, the plan assumes the use of `sudo apt-get install` or `yum install` commands are executed within the agent logic.
