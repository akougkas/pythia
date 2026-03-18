You are a dispatch planner for the scientific computing orchestration system. Your job is to produce a **written deployment plan** that describes the decomposed subtasks,  the specialist agent assigned for each subtask, and the hardware resources required by running the agent, etc. Do NOT execute any commands or download anything. Output only the plan document as text.

My goal is to deploy the XCompact3D application on an HPC cluster managed by Slurm. The plan must cover these stages and include the exact commands, scripts, and configurations for running XCompact3D :
1. Document the commands to download the XCompact3D source code from the upstream repository (`https://github.com/xcompact3d/Incompact3d`) and fetch all required dependencies.
2. Document the steps to read and understand the XCompact3D source code, the build, configure, and running commands.  For building, it should include the command for installing any required libraries.
3. Document the Slurm commands (`sinfo`, `scontrol`, etc.) how to query available nodes, partitions, GPUs, and network topology.
4. Document the full Slurm batch script with appropriate resource requests, and document the `sbatch` command to submit the job.
5. Document the commands to check job status, read logs, and validate that the application started correctly.

During the deployment, I want you to launch multiple agents. For subtasks that have **no mutual dependency**, they can be scheduled to run in parallel.  For each stage, specify: 1) which specialist agent would handle it; 2) what hardware resources it needs to run the agents 3) the expect number of tokens to use; 4) dependencies on other stages

Write the complete plan as a structured markdown document