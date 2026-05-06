# Storage placement guide — Ares cluster

Each compute node has four local tiers plus access to one shared pool. Pick a
tier explicitly per artifact; never default. Anchor every placement decision
in the access pattern (sequential vs. random, hot vs. warm vs. cold, per-rank
vs. shared-across-ranks) and the size of the artifact.

## Tier summary

| Tier          | Path                  | Capacity            | Best for                                          | Avoid for                              |
|---------------|-----------------------|---------------------|---------------------------------------------------|----------------------------------------|
| Node NVMe     | `/mnt/nvme/$USER`     | 250 GB (8 nodes 256 GB) | hot scratch; intermediate reductions; per-rank checkpoints | data shared across nodes               |
| Node SSD      | `/mnt/ssd/$USER`      | 512 GB              | warm working set; build artifacts; mid-size logs   | high-IOPS hot loops                    |
| Node HDD      | `/mnt/hdd/$USER`      | 1 TB                | cold per-node logs; sequential captures            | random I/O                             |
| Shared bulk   | `/mnt/common/$USER`   | 48 TB (RAID-5)      | source repos; final results; cross-rank inputs     | high-rate writes >10 GB (parity penalty)|
| Home          | `/home/$USER`         | small               | scripts; configs; small fixtures                   | bulk data of any kind                  |

## Decision rules

1. **Intermediate >10 GB → node-local NVMe.** RAID-5 sequential writes are parity-amplified; large transient files belong on per-node scratch.
2. **Final results → shared RAID-5** (`/mnt/common/$USER`). They need to be visible to the login node and across compute nodes.
3. **Source code, Slurm scripts, build inputs → shared or home** (small enough to live there; need to be visible from the login node).
4. **Per-rank scratch → NVMe** when the working set fits; SSD when 250 GB is too tight; HDD only for sequential cold-stage outputs.
5. **Cross-node intermediates → shared RAID-5** unless the size triggers rule (1). At >10 GB, prefer to recompute or shard rather than cross the parity penalty.

## Heterogeneity to watch

The NVMe tier is **not uniform**: nodes 01–24 have Samsung 960 Evo (250 GB); nodes 25–32 have Toshiba RD400 (256 GB). For I/O-heavy jobs that pin themselves to specific nodes, pick a homogeneous subset (24-node Samsung pool *or* 8-node Toshiba pool) and document which.

The SSD and HDD tiers are uniform across all 32 compute nodes.

## Anti-patterns

- Writing TB-scale intermediates to the shared RAID-5 pool. Parity amplification will dominate runtime.
- Using the master node OS SSD (128 GB) for any compute-side data. It's an OS volume, not scratch.
- Assuming `/home` will scale. It's small and shared; treat it as config-only.
- Mixing Samsung and Toshiba NVMe in a benchmarking run without acknowledging the vendor split — IOPS profiles differ.
