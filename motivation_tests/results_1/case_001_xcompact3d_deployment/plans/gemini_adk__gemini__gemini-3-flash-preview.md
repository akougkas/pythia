---
case: case_001_xcompact3d_deployment
framework: gemini_adk
model: gemini-3-flash-preview
provider: gemini
session_id: None
duration_ms: 7570
duration_wall_s: 7.6
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T02:03:43.068431+00:00
error: None
---

# Plan

# Deployment Plan: XCompact3D on Slurm-managed HPC Cluster

This document outlines the step-by-step implementation plan for deploying the XCompact3D (Incompact3d) application. The plan is decomposed into five stages, assigning specialized agents and defining resource requirements for each.

## 1. System Assumptions
*   **Operating System:** Linux-based HPC environment.
*   **Compiler/MPI:** GNU or Intel Fortran compilers with an MPI implementation (OpenMPI or MPICH) are available via a module system.
*   **Libraries:** FFTW3 is required for XCompact3D.
*   **Hardware:** The HPC cluster uses Slurm for job scheduling.

---

## 2. Detailed Implementation Stages

### Stage 1: Source Code Acquisition and Dependency Mapping
*   **Specialist Agent:** `Source_Acquisition_Agent`
*   **Hardware Resources:** 1 vCPU, 2GB RAM, Internet Access.
*   **Estimated Tokens:** 1,000
*   **Dependencies:** None
*   **Tasks:**
    1.  Navigate to the working directory: `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`.
    2.  Clone the repository: `git clone https://github.com/xcompact3d/Incompact3d.git`.
    3.  Identify submodules or external dependencies (e.g., FFTW3).
    4.  Verify the integrity of the downloaded source.

### Stage 2: Code Analysis and Build Configuration
*   **Specialist Agent:** `Build_Engineer_Agent`
*   **Hardware Resources:** 2 vCPUs, 4GB RAM.
*   **Estimated Tokens:** 2,500
*   **Dependencies:** Stage 1
*   **Tasks:**
    1.  Analyze the `Makefile` and `README.md` in the root directory.
    2.  Identify the configuration file (usually `src/decomp_2d.f90` or a specific `Makefile` flag for FFTW).
    3.  **Dependency Installation:** Document commands to install FFTW3 if not present (e.g., `sudo apt-get install libfftw3-dev` or `module load fftw`).
    4.  **Build Commands:**
        *   `cd Incompact3d`
        *   Modify `Makefile` to point to correct MPI and FFTW paths.
        *   Execute `make clean && make -j 4`.
    5.  Verify the generation of the `xcompact3d` executable.

### Stage 3: HPC Environment Discovery
*   **Specialist Agent:** `HPC_Infrastructure_Agent`
*   **Hardware Resources:** 1 vCPU, 1GB RAM, SSH access to Cluster Head Node.
*   **Estimated Tokens:** 1,500
*   **Dependencies:** None (Can run in parallel with Stage 1 & 2)
*   **Tasks:**
    1.  Query partitions: `sinfo`.
    2.  Query node details: `scontrol show nodes`.
    3.  Check for GPU availability (if applicable): `sinfo -o "%P %G"`.
    4.  Identify network topology: `scontrol show topology`.
    5.  Determine the optimal partition for a high-performance CFD run.

### Stage 4: Slurm Job Script Generation and Submission
*   **Specialist Agent:** `Deployment_Orchestrator_Agent`
*   **Hardware Resources:** 1 vCPU, 1GB RAM.
*   **Estimated Tokens:** 2,000
*   **Dependencies:** Stage 2, Stage 3
*   **Tasks:**
    1.  Create a Slurm batch script `submit_xcompact3d.sh`:
        ```bash
        #!/bin/bash
        #SBATCH --job-name=XCompact3D_Run
        #SBATCH --output=xcompact3d_%j.out
        #SBATCH --error=xcompact3d_%j.err
        #SBATCH --nodes=2
        #SBATCH --ntasks-per-node=32
        #SBATCH --partition=compute
        #SBATCH --time=01:00:00

        module load openmpi/4.1.x
        module load fftw/3.3.x

        # Run the application
        mpirun -np 64 ./xcompact3d > output.log
        ```
    2.  Document the submission command: `sbatch submit_xcompact3d.sh`.

### Stage 5: Job Monitoring and Validation
*   **Specialist Agent:** `QA_Monitoring_Agent`
*   **Hardware Resources:** 1 vCPU, 1GB RAM.
*   **Estimated Tokens:** 1,500
*   **Dependencies:** Stage 4
*   **Tasks:**
    1.  Monitor job status: `squeue -u $USER`.
    2.  Check real-time logs: `tail -f xcompact3d_<jobid>.out`.
    3.  Validate execution: Check for the creation of `stats.dat` or visualization files (e.g., `.h5` or `.dat` files) to ensure the solver is iterating.
    4.  Verify exit codes: `sacct -j <jobid> --format=JobID,JobName,State,ExitCode`.

---

## 3. Execution Summary Table

| Stage | Agent | Parallel? | Dependencies | Est. Tokens |
| :--- | :--- | :--- | :--- | :--- |
| 1. Download | `Source_Acquisition_Agent` | Yes | None | 1,000 |
| 2. Build | `Build_Engineer_Agent` | No | Stage 1 | 2,500 |
| 3. Query HPC | `HPC_Infrastructure_Agent` | Yes | None | 1,500 |
| 4. Submit | `Deployment_Orchestrator_Agent` | No | Stage 2, 3 | 2,000 |
| 5. Validate | `QA_Monitoring_Agent` | No | Stage 4 | 1,500 |

---

## 4. Resource Requirements Summary
*   **Total Estimated Tokens:** 8,500
*   **Max Concurrent Agents:** 2 (Stage 1 and Stage 3 can run simultaneously).
*   **Working Directory:** All scripts and source code will reside in `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`.
