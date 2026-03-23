---
case: case_001_xcompact3d_deployment
framework: agents_sdk
model: gpt-5
provider: github_models
session_id: None
duration_ms: 140288
duration_wall_s: 140.3
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T03:02:50.846768+00:00
error: None
---

# Plan

# XCompact3D on Slurm HPC — End-to-End Deployment Plan (Dispatch-Oriented)

This is a written deployment plan only. It decomposes the work into clear stages, assigns a specialist agent to each stage, specifies hardware resources and expected token usage, enumerates dependencies, and provides exact commands, scripts, and configurations to download, build, configure, submit, and validate XCompact3D (Incompact3d) runs under Slurm. No commands will be executed by this plan.

Assumptions (explicit):
- Cluster uses Environment Modules (Lmod) for dependencies. If not, Spack instructions are provided as a fallback.
- MPI (OpenMPI or MPICH), FFTW 3 (with MPI), and HDF5 (with parallel/MPI) are available and will be used. NetCDF is optional and not required for the baseline run.
- XCompact3D binary name is incompact3d (consistent with repository name). Input file name assumed to be input.i3d (common convention). If the bundled example uses a different name, substitute accordingly.
- The application is CPU-only; GPUs are not required.
- Slurm is configured with srun and sbatch; cgroups are enabled; shared filesystem is available to all compute nodes.
- Working directory exists and is writable: /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
- You have a standard non-root user with a Slurm account and a default project/partition available.

Contents:
- Team and roles (agents)
- Resource plan for each agent and parallelizable stages
- Directory layout plan
- Stage-by-stage detailed procedures with exact commands and scripts
- Artifacts list and validation criteria
- Risks and contingencies

--------------------------------------------------------------------------------
Team and Roles (Specialist Agents)
- A1: GitOps + Dependency Wrangler
  - Clones repositories, inventories/loads modules or installs deps via Spack.
- A2: Code Reader + Build Engineer (Fortran/MPI/HPC)
  - Reads project layout, authors make configuration, builds the binary.
- A3: Cluster Surveyor (Slurm/Topology)
  - Enumerates nodes, partitions, GPUs, interconnect, limits, and job qos.
- A4: Slurm Job Author
  - Authors batch script, sets resource requests and environment for stable runs.
- A5: Run Monitor + Validation Analyst
  - Submits jobs, monitors, validates logs and run products.
- A6: Documentation Curator
  - Organizes artifacts, records versions, prepares READMEs.

--------------------------------------------------------------------------------
Hardware Resources for Agents, Expected Token Usage, and Dependencies

Legend:
- CPU: login node vCPUs
- MEM: login node memory
- TOKENS: estimated LLM tokens if these agents are automated; includes reasoning and writing
- DEPS: dependencies (stage prerequisites)
- PARALLEL: whether stage can run concurrently with others

Stage S1 — Source + Dependencies (A1)
- CPU: 1 vCPU on login node
- MEM: 1–2 GB
- TOKENS: 500–900
- DEPS: none
- PARALLEL: yes (can run with S3)

Stage S2 — Code Read + Build + Configure (A2)
- CPU: 1 vCPU on login node for authoring; plus compile on login or dedicated build node as policy allows
- MEM: 2–4 GB
- TOKENS: 900–1400
- DEPS: S1
- PARALLEL: partially (reading can start after shallow clone; full build waits for deps)

Stage S3 — Cluster Survey (A3)
- CPU: 1 vCPU on login node
- MEM: <1 GB
- TOKENS: 400–700
- DEPS: none
- PARALLEL: yes (with S1)

Stage S4 — Slurm Batch Script Authoring (A4)
- CPU: 1 vCPU on login node
- MEM: <1 GB
- TOKENS: 500–900
- DEPS: S2 (needs binary path and run command), S3 (needs partition/node topology info)
- PARALLEL: no (must wait for S2/S3 outputs)

Stage S5 — Submission, Monitoring, Validation (A5)
- CPU: 1 vCPU on login node
- MEM: <1 GB
- TOKENS: 500–900
- DEPS: S4
- PARALLEL: n/a

Stage S6 — Documentation + Archival (A6)
- CPU: 1 vCPU on login node
- MEM: <1 GB
- TOKENS: 300–600
- DEPS: S1–S5
- PARALLEL: n/a

--------------------------------------------------------------------------------
Directory Layout Plan (under WorkingDir)

Root: /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

- src/Incompact3d                 # git clone target for upstream source
- deps/                           # optional: Spack prefix or custom builds
- build/                          # build artifacts (if out-of-source used)
- cases/                          # case inputs and run directories
  - examples/                     # copies of upstream examples or templates
  - taylor_green/                 # sample case folder (example)
- slurm/
  - xcompact3d_run.sbatch         # Slurm batch script
- env/
  - module_setup.sh               # environment setup used by batch and local shells
  - make.inc                      # selected make configuration for build
- logs/
  - build.log
  - submit.log
  - job.<jobid>.out               # symlinked to slurm-<jobid>.out
- docs/
  - DEPLOY_NOTES.md               # generated by A6
  - VERSIONS.txt                  # module/spack and git commit info

--------------------------------------------------------------------------------
Execution Plan and Parallelization Overview

- In parallel:
  - S1 (A1): Clone + dependency inventory/load
  - S3 (A3): Cluster survey and partition/node inventory

- Then:
  - S2 (A2): Code reading + build (depends on S1)
  - S4 (A4): Author Slurm batch (depends on S2 and S3)
  - S5 (A5): Submit + monitor + validate (depends on S4)
  - S6 (A6): Document and archive (final consolidation)

--------------------------------------------------------------------------------
Stage S1 — Commands to Download Source and Fetch Dependencies
Agent: A1 (GitOps + Dependency Wrangler)
Resources: 1 vCPU login; 1–2 GB RAM
Dependencies: none
Parallel: yes

1) Prepare directories
- Commands (not executed; to be run on login node):
  mkdir -p /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/{src,deps,build,cases,slurm,env,logs,docs}
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir

2) Clone upstream source (with submodules if any)
- Commands:
  cd src
  git clone --recursive https://github.com/xcompact3d/Incompact3d.git
  cd Incompact3d
  # Optionally pin to a known tag/release (assumption: 'v5.0' exists; adjust if needed)
  # git fetch --tags
  # git checkout v5.0
  git submodule update --init --recursive

3) Inventory and load dependencies via Environment Modules (preferred)
- Commands to inspect available modules:
  module avail 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log
  module spider openmpi 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log
  module spider mpich 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log
  module spider fftw 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log
  module spider hdf5 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log

- Select one MPI stack (example uses OpenMPI), FFTW (with MPI), HDF5 (parallel). Example module loads (adjust names/versions to cluster):
  module purge
  module load gcc/12.2.0
  module load openmpi/4.1.6
  module load fftw/3.3.10-mpi
  module load hdf5/1.14.3-mpi
  # optional helpers:
  module load cmake/3.27.9  # in case needed for utilities
  module load python/3.10   # if any post-processing needs it

- Persist an environment bootstrap script for reuse by build and sbatch:
  cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/module_setup.sh << 'EOF'
  #!/usr/bin/env bash
  module purge
  module load gcc/12.2.0
  module load openmpi/4.1.6
  module load fftw/3.3.10-mpi
  module load hdf5/1.14.3-mpi
  export OMP_NUM_THREADS=1
  export UCX_ERROR_SIGNALS=SIGBUS,SIGSEGV,SIGFPE
  export UCX_WARN_UNUSED_ENV_VARS=n
  export HDF5_USE_FILE_LOCKING=FALSE
  EOF
  chmod +x /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/module_setup.sh

4) Fallback: Install dependencies via Spack (if modules unavailable)
- Install Spack (if not provided by site):
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/deps
  git clone https://github.com/spack/spack.git
  . spack/share/spack/setup-env.sh

- Install toolchain and libs (example):
  spack compiler find
  spack install openmpi@4.1.6
  spack install fftw@3.3.10 +mpi
  spack install hdf5@1.14.3 +mpi +fortran
  spack load openmpi@4.1.6
  spack load fftw@3.3.10 +mpi
  spack load hdf5@1.14.3 +mpi +fortran

- Persist Spack bootstrap (optional):
  cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/spack_setup.sh << 'EOF'
  #!/usr/bin/env bash
  . /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/deps/spack/share/spack/setup-env.sh
  spack load openmpi@4.1.6
  spack load fftw@3.3.10 +mpi
  spack load hdf5@1.14.3 +mpi +fortran
  export OMP_NUM_THREADS=1
  export HDF5_USE_FILE_LOCKING=FALSE
  EOF
  chmod +x /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/spack_setup.sh

Outputs/Artifacts:
- src/Incompact3d checked out with submodules
- env/module_setup.sh and/or env/spack_setup.sh created
- logs/build.log appended with module queries

--------------------------------------------------------------------------------
Stage S2 — Read/Understand Source, Build, Configure, Run Commands
Agent: A2 (Code Reader + Build Engineer)
Resources: 1 vCPU login; 2–4 GB RAM
Dependencies: S1
Parallel: partial (read can begin after clone; compile after deps)

2.1) Read and understand repository structure
- Explore top-level files:
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/src/Incompact3d
  ls -la
  # optional, if 'tree' exists:
  # tree -L 2

- Suggested reading order:
  - README.md, docs/ (build, run, and case descriptions)
  - src/ directory (Fortran sources; main program typically in incompact3d.f90 or similar)
  - makefiles/ or arch/ (architecture-specific make configs if provided)
  - examples/ or cases/ (reference input files; confirm naming convention for input.i3d/INPUT)
  - scripts/ or tools/ (post/ pre-processing utilities)

- Quick code indexing and dependency sense-making:
  grep -R --line-number "program " src || true
  grep -R --line-number "module " src | head
  grep -R --line-number "fftw" src | head
  grep -R --line-number "hdf5" src | head
  grep -R --line-number "mpi_" src | head

2.2) Build configuration (Makefile-based)
- Assumption: Project uses a Makefile expecting a machine/architecture include (make.inc). We will author env/make.inc and reference it from the build.
- Create a GNU+OpenMPI make include with MPI + FFTW + HDF5:

  cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/make.inc << 'EOF'
  # Compiler setup
  FC       = mpif90
  CC       = mpicc

  # Flags (GNU)
  # Note: -fallow-argument-mismatch helps legacy Fortran code on GCC >=10
  FFLAGS   = -O3 -fopenmp -fimplicit-none -fallow-argument-mismatch
  CFLAGS   = -O3
  LDFLAGS  =

  # Paths from loaded modules or Spack (adjust if needed)
  FFTW_ROOT ?= ${FFTW_DIR}
  HDF5_ROOT ?= ${HDF5_DIR}

  # Includes and libraries
  INC_FFTW = -I$(FFTW_ROOT)/include
  LIB_FFTW = -L$(FFTW_ROOT)/lib -lfftw3_mpi -lfftw3

  INC_HDF5 = -I$(HDF5_ROOT)/include
  LIB_HDF5 = -L$(HDF5_ROOT)/lib -lhdf5_fortran -lhdf5 -lz

  LIBS     = $(LIB_FFTW) $(LIB_HDF5) -lm

  # Preprocessor defs (adjust as needed; examples)
  #DEFS    = -DUSE_HDF5 -DUSE_MPIIO

  # Export to Make
  export FC CC FFLAGS CFLAGS LDFLAGS INC_FFTW LIB_FFTW INC_HDF5 LIB_HDF5 LIBS
  EOF

- If the project provides a template arch file (e.g., in arch/Makefile.inc.gfortran_openmpi), prefer copying and editing that:
  # Example if exists:
  # cp arch/Makefile.inc.gfortran_openmpi /home/jye/.../env/make.inc
  # edit paths to FFTW/HDF5 as needed

2.3) Build commands
- Load environment, then build:
  source /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/module_setup.sh
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/src/Incompact3d

  # If top-level Makefile expects make.inc in current dir, symlink it:
  ln -sf /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/make.inc make.inc

  # Clean and compile (capture logs)
  make clean 2>&1 | tee /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log
  make -j $(nproc) 2>&1 | tee -a /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/build.log

- Expected result: an executable (name often incompact3d or xcompact3d) under the repo root or src/. Confirm:
  file ./incompact3d || file ./src/incompact3d || ls -l

- If the build system differs (e.g., a specific make target or directory), adapt:
  # Examples:
  # make ARCH=gfortran_openmpi
  # make -C src -f Makefile.gfortran

2.4) Case setup and run commands (non-Slurm dry-run planning)
- Identify an example case in the repo (assume examples/TaylorGreen or similar). Copy it under WorkingDir:
  mkdir -p /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/cases/examples
  # Example — adjust to actual example path in repo:
  cp -r examples/TaylorGreen /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/cases/taylor_green

- Confirm input file and binary invocation pattern:
  # Common patterns include:
  #   srun ./incompact3d < input.i3d
  #   srun ./incompact3d input.i3d
  # We will use redirection; Slurm stage will reflect this.

- Runtime environment (when running interactively on a compute node):
  export OMP_NUM_THREADS=1
  srun -n 4 ./incompact3d < input.i3d

Outputs/Artifacts:
- env/make.inc authored and linked into source dir
- logs/build.log with full compile transcript
- Compiled executable path confirmed
- cases/taylor_green prepared

--------------------------------------------------------------------------------
Stage S3 — Slurm Cluster Interrogation (nodes, partitions, GPUs, topology)
Agent: A3 (Cluster Surveyor)
Resources: 1 vCPU login; <1 GB RAM
Dependencies: none
Parallel: yes

3.1) Partitions and node states summary
- Basic partition/availability:
  sinfo
  sinfo -s
  sinfo -o "%P %a %l %D %N %t"

3.2) Node-level details and features
- Nodes with detailed features and GRES (GPUs if present):
  sinfo -N -l
  sinfo --Format=nodename,partition,cpusstate,cpus,mem,gres,features:50,statelong

- Show a specific node:
  scontrol show node <nodename>

3.3) Partitions with constraints and GRES
  sinfo --Format=partition,avail,cpus,gres,features:50,maxnodes,maxcpus,maxmem,timelimit

3.4) Topology and network hints
  scontrol show topology
  scontrol show config | egrep -i "topology|selecttype|scheduler"
  scontrol show hostnames

3.5) QoS, accounts (if enabled)
  sacctmgr show qos format=Name,MaxWall,MaxJobs,MaxCPUs,MaxNodes%10,Priority%10
  sacctmgr show assoc where user=$USER format=Account,Partition,QOS%-30

3.6) GPU focus (for completeness; app is CPU-only)
  sinfo -o "%P %G %N %D %t"
  sinfo --Format=partition,gres
  scontrol show node <gpu-node> | egrep -i "gres|gpu|vendor"

Outputs/Artifacts:
- Copy/paste outputs captured into docs/DEPLOY_NOTES.md and logs/cluster_survey.txt (if desired by tee)

--------------------------------------------------------------------------------
Stage S4 — Slurm Batch Script with Resource Requests and sbatch Submission Command
Agent: A4 (Slurm Job Author)
Resources: 1 vCPU login; <1 GB RAM
Dependencies: S2, S3
Parallel: no

4.1) Resource sizing assumptions for a baseline run
- Example: 4 nodes, 32 MPI ranks per node, total 128 ranks; 1 CPU per task; OMP_NUM_THREADS=1; time limit 2 hours.
- Partition placeholder: cpu (replace with actual from Stage S3).
- Exclusive allocation recommended to avoid noisy neighbors when benchmarking; remove if policy requires sharing.

4.2) Author batch script slurm/xcompact3d_run.sbatch
- Script content (adjust partition, account, mail settings as appropriate):

  cat > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm/xcompact3d_run.sbatch << 'EOF'
  #!/usr/bin/env bash
  #SBATCH --job-name=xcompact3d_tg
  #SBATCH --partition=cpu                    # adjust from sinfo
  #SBATCH --nodes=4
  #SBATCH --ntasks-per-node=32
  #SBATCH --cpus-per-task=1
  #SBATCH --time=02:00:00
  #SBATCH --exclusive
  #SBATCH --hint=nomultithread               # if hyperthreading exists and you want physical cores
  #SBATCH --output=%x-%j.out
  #SBATCH --error=%x-%j.err
  #SBATCH --chdir=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/cases/taylor_green
  #SBATCH --comment="XCompact3D Taylor-Green baseline"

  set -euo pipefail

  echo "[$(date)] SLURM job starting on nodes: ${SLURM_NODELIST}"
  echo "SLURM_NTASKS=${SLURM_NTASKS} NTASKS_PER_NODE=${SLURM_NTASKS_PER_NODE}"

  # Load environment
  source /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/module_setup.sh

  # MPI/HDF5 safety and diagnostics
  export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
  export I_MPI_DEBUG=0
  export HDF5_USE_FILE_LOCKING=FALSE
  ulimit -s unlimited

  # Path to executable (adjust if binary resides elsewhere)
  X3D_BIN=/home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/src/Incompact3d/incompact3d
  INPUT_FILE=input.i3d

  # Confirm files
  echo "Binary: ${X3D_BIN}"
  echo "Input:  ${INPUT_FILE}"
  ls -l "${X3D_BIN}" "${INPUT_FILE}"

  # Optional: bind ranks to cores for stability
  CPU_BIND="--cpu-bind=cores"
  # Optional: network options (cluster-specific; comment out if unknown)
  # export UCX_NET_DEVICES=mlx5_0:1

  # Launch
  echo "[$(date)] Launching srun..."
  srun ${CPU_BIND} "${X3D_BIN}" < "${INPUT_FILE}"

  rc=$?
  echo "[$(date)] srun finished with exit code ${rc}"
  exit ${rc}
  EOF

4.3) Permissions
  chmod +x /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/slurm/xcompact3d_run.sbatch

4.4) Document the sbatch submission command
- From working dir:
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir
  sbatch slurm/xcompact3d_run.sbatch | tee -a logs/submit.log

Outputs/Artifacts:
- slurm/xcompact3d_run.sbatch ready
- logs/submit.log contains job submission line with JobID

--------------------------------------------------------------------------------
Stage S5 — Commands to Check Job Status, Read Logs, and Validate Startup
Agent: A5 (Run Monitor + Validation Analyst)
Resources: 1 vCPU login; <1 GB RAM
Dependencies: S4
Parallel: n/a

5.1) Job status and queue
- After submitting (record JobID N):
  squeue -j <JobID> -o "%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"
  scontrol show job <JobID>
  sacct -j <JobID> --format=JobID,JobName%20,Partition,Account,AllocNodes,AllocTRES,State,Elapsed,MaxRSS%12,MaxVMSize%12,ExitCode

5.2) Logs
- Slurm standard output and error appear in the working directory or chdir path set by #SBATCH --output/--error:
  cd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/cases/taylor_green
  tail -n 100 -f xcompact3d_tg-<JobID>.out
  tail -n 100 -f xcompact3d_tg-<JobID>.err

- Optional symlink for convenience:
  ln -sf xcompact3d_tg-<JobID>.out /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/logs/job.<JobID>.out

5.3) Validate that the application started correctly
- Look for typical startup lines:
  - MPI world size (e.g., “Number of MPI processes: 128”)
  - FFTW/HDF5 initialization messages (if any)
  - Reading input and grid configuration (e.g., “Reading input.i3d”, “nx=…, ny=…, nz=…”)
  - Time-step initialization and first iteration report
- Use grep on stdout:
  egrep -i "mpi|processes|fftw|hdf5|reading|grid|nx|ny|nz|time step|iteration" xcompact3d_tg-<JobID>.out | head -n 50

- Verify outputs produced (names vary by case):
  ls -lh
  # Look for restart files, field outputs (e.g., .h5, .bin), logs specific to the code.

- Confirm no immediate runtime errors:
  egrep -i "error|fail|segmentation|abort" xcompact3d_tg-<JobID>.err xcompact3d_tg-<JobID>.out || true

5.4) Troubleshooting quick checks
- If job pending:
  squeue -j <JobID> -o "%.18i %.2t %R"
- If job fails quickly:
  scontrol show job <JobID> | egrep -i "Reason=|ExitCode"
  # Check module environment echoed at top of output log
  # Confirm HDF5/FFTW MPI variants are used (module spider output or ldd on binary)
  ldd /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/src/Incompact3d/incompact3d | egrep "fftw|hdf5|mpi"

5.5) Cancel job (if needed)
  scancel <JobID>

Outputs/Artifacts:
- Slurm logs and case outputs
- Validation grep results and notes appended to docs/DEPLOY_NOTES.md

--------------------------------------------------------------------------------
Stage S6 — Documentation and Archival
Agent: A6 (Documentation Curator)
Resources: 1 vCPU login; <1 GB RAM
Dependencies: S1–S5
Parallel: n/a

6.1) Record versions and environment
  git -C /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/src/Incompact3d rev-parse HEAD > /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/docs/VERSIONS.txt
  module list 2>> /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/docs/VERSIONS.txt

6.2) Summarize deployment in docs/DEPLOY_NOTES.md
- Include:
  - Git commit/tag
  - Module/Spack packages and versions
  - Build flags (env/make.inc)
  - Slurm resources (nodes, tasks per node, time)
  - JobIDs and paths to logs/output files
  - Any deviations from assumptions

--------------------------------------------------------------------------------
Appendix A — Alternative Dependency Resolutions

A.1) MPICH stack
- Replace openmpi with mpich modules:
  module purge
  module load gcc/12.2.0
  module load mpich/4.1.2
  module load fftw/3.3.10-mpi
  module load hdf5/1.14.3-mpi
- Update env/make.inc if FFTW/HDF5 variables differ (FFTW_DIR/HDF5_DIR may be set by modules).

A.2) No HDF5 I/O
- If HDF5 parallel is unavailable, you can build without it:
  - Remove HDF5 includes/libs from make.inc
  - Undefine USE_HDF5 in DEFS
  - Ensure example/input does not require HDF5 I/O

--------------------------------------------------------------------------------
Appendix B — Slurm Cluster Query Cookbook

- Show all partitions with time limits:
  sinfo -o "%P %a %l %L %D %t"
- Show node resources:
  sinfo -N --Format=NodeHost,CPUsState,CPUs,Memory,StateLong,Gres
- Job accounting for a user:
  sacct -u $USER --format=JobID,JobName,Partition,AllocCPUS,Elapsed,State,ExitCode%12 | tail -n +3 | column -t

--------------------------------------------------------------------------------
Appendix C — Risk Matrix and Mitigations

- Risk: FFTW/HDF5 modules are serial-only (no MPI)
  Mitigation: Use module spider to find mpi-enabled variants (look for +mpi or -mpi suffix), or use Spack installations with +mpi.

- Risk: Makefile layout differs from plan
  Mitigation: Inspect repo’s docs/Makefile; if an arch-specific include is required, copy the closest template and adjust library paths.

- Risk: Input file name differs (not input.i3d)
  Mitigation: Use the exact input file packaged with the example case directory; adjust srun invocation accordingly.

- Risk: Hyperthreading causing oversubscription
  Mitigation: Use #SBATCH --hint=nomultithread and OMP_NUM_THREADS=1; also consider --cpu-bind=cores.

- Risk: File locking errors on parallel FS with HDF5
  Mitigation: export HDF5_USE_FILE_LOCKING=FALSE in environment and sbatch script.

--------------------------------------------------------------------------------
Quick Reference: End-to-End Command Snippets

- Clone source:
  git clone --recursive https://github.com/xcompact3d/Incompact3d.git

- Load modules:
  source env/module_setup.sh

- Build:
  ln -sf /home/jye/publications/cases/case_001_xcompact3d_deployment/WorkingDir/env/make.inc make.inc
  make clean && make -j $(nproc)

- Submit:
  sbatch slurm/xcompact3d_run.sbatch

- Monitor:
  squeue -u $USER
  tail -f cases/taylor_green/xcompact3d_tg-<JobID>.out

- Cancel:
  scancel <JobID>

--------------------------------------------------------------------------------
Deliverables Checklist

- [ ] Source fetched: src/Incompact3d
- [ ] Dependencies resolved via modules or Spack
- [ ] Build configured: env/make.inc
- [ ] Executable present: src/Incompact3d/incompact3d
- [ ] Example case prepared: cases/taylor_green with input.i3d
- [ ] Slurm script authored: slurm/xcompact3d_run.sbatch
- [ ] Job submitted and monitored; logs captured in cases/... and logs/submit.log
- [ ] Documentation finalized in docs/DEPLOY_NOTES.md and docs/VERSIONS.txt

End of plan.
