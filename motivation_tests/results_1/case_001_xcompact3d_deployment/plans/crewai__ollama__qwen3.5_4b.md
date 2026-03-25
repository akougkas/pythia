---
case: case_001_xcompact3d_deployment
framework: crewai
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 43773
duration_wall_s: 43.8
cost_usd: None
num_turns: 1
timestamp: 2026-03-19T23:22:50.167843+00:00
error: None
---

# Plan

# XCompact3D HPC Deployment Implementation Plan

**Version:** 1.0  
**Status:** Planning Phase  
**Working Directory:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`  
**Application:** XCompact3D (via upstream repository `https://github.com/xcompact3d/Incompact3d`)  
**Cluster Manager:** SLURM  

---

## 1. Executive Summary
This document outlines the implementation plan to deploy the XCompact3D application on a High-Performance Computing (HPC) cluster. The plan decomposes the deployment into five distinct subtasks managed by specialized agents. While the primary deployment logic is sequential, specific subtasks are identified as parallel where dependencies allow. This plan includes the exact commands, scripts, agent specifications, and resource requirements.

---

## 2. Agent Specifications & Resource Allocation

| Agent ID | Agent Name | Specialization | Hardware Requirements (Local/Node) | Estimated Tokens |
| :--- | :--- | :--- | :--- | :--- |
| **A1** | `Repo-Clone-Agent` | Source Control & Dependency Fetching | Standard HPC Node (4vCPU / 16GB RAM / 1TB NVMe) | 150 |
| **A2** | `Build-Specialist` | Compilation & Library Management | Compilation Node (16vCPU / 64GB RAM / 500GB SSD) | 450 |
| **A3** | `Cluster-Auditor` | SLURM & Topology Query | HPC Controller Node Access (16vCPU / 32GB RAM) | 100 |
| **A4** | `Job-Submission-Agent` | Batch Job Scheduling (`sbatch`) | HPC Node Access (16vCPU / 32GB RAM) | 300 |
| **A5** | `Validation-Pipe` | Log Analysis & Status Check | Local Monitor Node (4vCPU / 8GB RAM) | 250 |

---

## 3. Stage Definitions & Dependencies

### 3.1 Stage 1: Repository & Dependency Fetching
*   **Agent:** `Repo-Clone-Agent` (A1)
*   **Description:** Clones source code from upstream, installs build dependencies (e.g., OpenBLAS, CUDA, LAPACK), and creates the build environment.
*   **Dependencies:** None (Start Point)
*   **Parallelism:** **Parallel** with Stage 3 (Cluster Audit)
*   **Expected Deliverables:** `./WorkingDir` source tree, `Makefile`/`CMakeLists.txt`, Installed System Libraries.

### 3.2 Stage 2: Build, Configure, Understand
*   **Agent:** `Build-Specialist` (A2)
*   **Description:** Reads source code, installs missing libraries, configures CMake, compiles XCompact3D, and performs static analysis.
*   **Dependencies:** Stage 1 (Source Code availability)
*   **Parallelism:** None (Strictly sequential after Stage 1)
*   **Expected Deliverables:** `./WorkingDir/build/XCompact3D` binary, build logs.

### 3.3 Stage 3: Cluster Query & Analysis
*   **Agent:** `Cluster-Auditor` (A3)
*   **Description:** Queries SLURM for available partitions, nodes, GPU availability, and network topology.
*   **Dependencies:** None (Independent of build)
*   **Parallelism:** **Parallel** with Stage 1 (Can be run before or during Stage 1)
*   **Expected Deliverables:** `cluster_status.txt`, `node_mapping.json`

### 3.4 Stage 4: SLURM Batch Submission
*   **Agent:** `Job-Submission-Agent` (A4)
*   **Description:** Constructs SLURM batch script, selects nodes based on Stage 3 analysis, submits job via `sbatch`.
*   **Dependencies:** Stage 2 (Binary exists), Stage 3 (Node topology available)
*   **Parallelism:** None (Strictly sequential after Stage 2 & 3)
*   **Expected Deliverables:** `my_job.sh`, Submitted Job ID (e.g., `12345`).

### 3.5 Stage 5: Execution Validation
*   **Agent:** `Validation-Pipe` (A5)
*   **Description:** Monitors job status, parses logs, validates application start-up and expected output.
*   **Dependencies:** Stage 4 (Job running)
*   **Parallelism:** None (Strictly sequential after Stage 4)
*   **Expected Deliverables:** `validation_report.txt`, Success/Fail flag.

---

## 4. Detailed Implementation Steps

### 4.1 Stage 1: Repository & Dependency Fetching

**Agent Action:** Run commands on local node.
**Function Signature:**
```bash
function fetch_xcompact_source() {
  local repo_url="https://github.com/xcompact3d/Incompact3d"
  local base_dir="/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir"
  local target_dir="$base_dir/xcompact3d_src"

  # Step 1: Clone repository (No SSH key assumed, use HTTPS)
  git clone --depth 1 "$repo_url" "$target_dir"
  
  # Step 2: Fetch dependencies (Assuming Ubuntu HPC environment)
  # Install required libraries for build
  sudo apt-get update
  sudo apt-get install -y \
    libopenblas-dev \
    liblapack-dev \
    build-essential \
    cmake \
    ninja-build
}
```

**Hardware Resource:** 4 vCPU, 16 GB RAM, NVMe Storage (500GB+).

---

### 4.2 Stage 2: Build, Configure, Understand

**Agent Action:** Execute build scripts and static analysis.
**Function Signature:**
```bash
function configure_and_build() {
  local build_dir="$base_dir/xcompact3d_src/build"
  local cmake_args="-DCMAKE_INSTALL_PREFIX=$base_dir/install"
  
  # Step 3: Create build directory and configure
  mkdir -p "$build_dir"
  cd "$build_dir"
  cmake "$cmake_args" ..
  
  # Step 4: Install libraries if not present (Check command)
  if [ -z "$OPENBLAS_DIR" ] || [ -z "$LAPACK_DIR" ]; then
    sudo apt-get install libopenblas-dev liblapack-dev
  fi
  
  # Step 5: Compile using Ninja (Faster than make)
  ninja
  # Verify build artifacts
  if [ -f "xcompact3d_compiled" ]; then
    echo "Build Successful"
    return 0
  else
    echo "Build Failed"
    return 1
  fi
}
```

**Hardware Resource:** 16 vCPU, 64 GB RAM, 500 GB SSD (Write-heavy).

---

### 4.3 Stage 3: Cluster Query & Analysis

**Agent Action:** Run SLURM commands to map resources.
**Function Signature:**
```bash
function query_slurm_topology() {
  local node_partitions="\"$base_dir/node_partitions.json\""
  local gpu_nodes="\"$base_dir/gpu_nodes.json\""
  
  # Step 1: Query available partitions
  sinfo -p -t
  # Step 2: Query specific GPUs (if applicable)
  sinfo --nodes --format='%A\n' | grep -i "gpu"
  # Step 3: Save topology
  echo "Available Nodes: $(sinfo -n | wc -l)" > $base_dir/nodes.txt
  echo "GPU Nodes: $(sinfo --nodes --format='%N' | grep -c gpu)" > $base_dir/gpu_map.txt
}
```

**Hardware Resource:** Access to SLURM Controller (Read-only access preferred).

---

### 4.4 Stage 4: SLURM Batch Submission

**Agent Action:** Generate and submit the batch script.
**Function Signature:**
```bash
function submit_slurm_job() {
  local job_name="xcompact3d_job"
  local partition="general_gpu"
  
  # Step 1: Construct Script Content
  cat > "$base_dir/my_job.sh" << EOF
#!/bin/bash
#SBATCH --job-name=$job_name
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4
#SBATCH --gpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --output=logs/xcompact3d_%j.log

# Step 2: Set environment
export LD_LIBRARY_PATH=/usr/local/lib
source /etc/profile

# Step 3: Execute application
./xcompact3d_compiled --input /data/input.txt --output /data/output.txt
EOF

  # Step 4: Submit via sbatch
  sbatch --output=/dev/null --error=/dev/null "$base_dir/my_job.sh" 2>/dev/null
  
  # Step 5: Capture Job ID
  local job_id=$(squeue -o %i -j $job_name)
  echo "Job ID: $job_id"
}
```

**Hardware Resource:** Access to SLURM Scheduler (Write access required).

---

### 4.5 Stage 5: Execution Validation

**Agent Action:** Monitor and parse logs.
**Function Signature:**
```bash
function validate_execution() {
  local log_file="/dev/null" # From Stage 4 stdout
  local status_file="/tmp/xcompact3d_status.txt"
  
  # Step 1: Poll Job Status
  while ! squeue -o '%A %j %T' --job-id=$job_id > /dev/null; do
    sleep 5
    echo "Monitoring..."
  done
  
  # Step 2: Check Log for Start Message
  grep -q "Application Started" "$base_dir/my_job.log"
  if [ $? -eq 0 ]; then
    echo "Validation: SUCCESS"
  else
    echo "Validation: FAILED"
    exit 1
  fi
}
```

**Hardware Resource:** Local Monitor Node.

---

## 5. Execution Order & Parallelism Logic

The deployment plan follows the following dependency graph:
`Stage 1 & Stage 3` **[Parallel]** -> `Stage 2` -> `Stage 4` -> `Stage 5`

### 5.1 Dependency Matrix
| Subtask | Depends On | Provided By |
| :--- | :--- | :--- |
| Stage 1 (Download) | None | Repo-Clone-Agent |
| Stage 3 (Query) | None | Cluster-Auditor |
| Stage 2 (Build) | Stage 1 | Build-Specialist |
| Stage 4 (Submission) | Stage 2, Stage 3 | Job-Submission-Agent |
| Stage 5 (Validation) | Stage 4 | Validation-Pipe |

### 5.2 Parallel Execution Strategy
1.  **Init Phase:** Launch `Repo-Clone-Agent` (A1) and `Cluster-Auditor` (A3) simultaneously.
    *   *Reasoning:* Building requires local source, Querying Cluster is independent. Both agents are resource-agnostic.
2.  **Build Phase:** Once A1 completes, A2 begins compiling.
    *   *Reasoning:* Binary needed for `sbatch`.
3.  **Submission Phase:** Once A2 finishes and A3 completes, A4 executes.
    *   *Reasoning:* Script needs binary and valid node allocation.
4.  **Validation Phase:** Once A4 returns Job ID, A5 monitors until completion.
    *   *Reasoning:* Needs output to verify success.

---

## 6. Final Deliverables & Configuration

### 6.1 File Structure Plan
```text
/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/
├── xcompact3d_src/           # Stage 1 Output
│   └── Incompact3d-master/   # Cloned Repo
├── build/                     # Stage 2 Output
│   └── CMakeCache.txt        # Configuration
│   └── xcompact3d_compiled   # Final Binary
├── install/                   # Stage 2 Output
│   └── lib/                  # Installed Libraries
├── logs/                      # Stage 4 & 5 Output
│   └── xcompact3d_job_0.log # Application Logs
├── node_partitions.json       # Stage 3 Output
├── gpu_nodes.json             # Stage 3 Output
└── my_job.sh                  # Stage 4 Output
```

### 6.2 Configuration Parameters
*   **Working Directory:** `/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir`
*   **Repository URL:** `https://github.com/xcompact3d/Incompact3d`
*   **Build Command:** `cmake -DCMAKE_BUILD_TYPE=Release .. && ninja`
*   **Installation Command:** `make install` (or `ninja install`)
*   **SLURM Partition:** `compute` (Default assumption; verify in Stage 3)
*   **Memory Limit:** 50 GB per node (Default assumption for 3D comp)
*   **Timeout:** 60 minutes (Stage 5 wait limit)

---

## 7. Risk Management & Contingencies

1.  **Build Failure:** If `Stage 2` fails, rollback `Stage 2` logs to error. Re-run `Stage 1` if missing headers.
2.  **Cluster Unavailable:** If `Stage 3` times out, implement exponential backoff in `Stage 3` script.
3.  **Job Rejection:** If `Stage 4` `sbatch` returns `REASON` (e.g., `Too many nodes`), modify `my_job.sh` resource requests and resubmit.
4.  **Validation Timeout:** If `Stage 5` exceeds 45 mins without output, trigger error flag.
