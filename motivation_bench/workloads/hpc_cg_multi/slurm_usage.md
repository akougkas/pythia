# Ares SLURM usage

## Common commands

| Action                      | Command                                                          |
|-----------------------------|------------------------------------------------------------------|
| Submit a batch job          | `sbatch script.slurm`                                            |
| Allocate interactively      | `salloc -N <count> --exclusive -w <nodelist>`                    |
| List your jobs              | `squeue -u $USER`                                                |
| Cluster availability        | `sinfo`                                                          |
| Cancel a job                | `scancel <jobid>`                                                |
| Inspect controller settings | `scontrol show config`                                           |

## Walltime and priority

- **Walltime cap: 48 hours per job.** Long studies must be checkpointed and resumed across multiple jobs.
- **Priority: first-come-first-served.** No user-side priority knob. For time-sensitive runs, coordinate with current users; do not assume queue jumping.

## Hostname routing — pick the right fabric

The same physical compute nodes are addressable under two hostnames:

| Hostname             | Fabric                | Use for                                       |
|----------------------|-----------------------|-----------------------------------------------|
| `ares-comp-NN`       | 10 GbE (default)      | low-bandwidth jobs, control plane, ssh        |
| `ares-comp-NN-40g`   | 40 GbE RoCE-capable   | RDMA / high-bandwidth MPI traffic             |

When the plan needs RoCE, **the Slurm `-w` nodelist must use the `-40g` hostnames.** Using the unsuffixed name routes traffic over 10 GbE and silently disables RoCE.

Verify RoCE at runtime:
```
ucx_info -d   # should list rc_verbs / rc_mlx5
ibstat        # InfiniBand-style query against the RoCE NIC
```

## Minimal directive block

```
#SBATCH --job-name=<name>
#SBATCH --nodes=<N>
#SBATCH --ntasks-per-node=<R>      # MPI ranks per node
#SBATCH --cpus-per-task=<T>        # OpenMP threads per rank
#SBATCH --time=HH:MM:SS            # ≤ 48:00:00
#SBATCH --exclusive                # add when measuring
# #SBATCH --nodelist=ares-comp-01-40g,ares-comp-02-40g,...   # if pinning + RoCE
```

Per-node sanity: `R × T ≤ 20 cores`. Going past 20 cores oversubscribes against the per-node ceiling (20 cores / 40 threads).

## Per-node memory budget

Compute nodes have **48 GB DDR4-2400** each. Common pitfalls:

- 20 ranks × 1 thread leaves only **2.4 GB/rank**. Usually too tight for HPC kernels with non-trivial state.
- Hybrid `R=2, T=10` is the safer default: 24 GB/rank, full core count, NUMA-clean.
- Plan for OS overhead: budget effective per-node RAM as **~44 GB**, not 48.

## Useful environment variables

```
OMP_NUM_THREADS=<T>
OMP_PROC_BIND=close
OMP_PLACES=cores
OMP_DISPLAY_ENV=verbose            # echo OpenMP config to stdout for the run record
UCX_TLS=rc,sm,self                 # if you need to force RoCE/UCX (verify first)
```

## Output location

By default Slurm writes `slurm-<jobid>.out` in the submit directory. For
multi-stage runs, redirect output to a node-local tier (see
`storage_decision_guide.md`) and rsync to shared at job end.
