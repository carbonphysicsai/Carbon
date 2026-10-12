# Different jobs need different storage

This is a public/non-sensitive recommendation, not the sealed-worker plan.
Source constants are fixed low/base/high; scenarios are ASSUMPTION. Procurement,
public-data redistribution rights and security acceptance stay with the owner.

| Option | Access / execution | Strength | Limitation that changes the decision |
|---|---|---|---|
| Existing local SSD | Actual host filesystem; compute comes from that host | Repeated reads avoid the WAN, and existing unused capacity has no new rental | Capacity and host availability unknown; device loss and local deletion need a separate copy. No hardware or AX42 inspected |
| Storage Box | SFTP/SCP, rsync/Borg and other file protocols; restricted SSH | Cheap capacity blocks and included traffic; snapshots and sub-accounts | No full shell or uploaded-script execution; ten simultaneous connections. RAID is on one host, not a second independent server. Snapshot space and retention need budgeting |
| Hippius S3 | Object API and HTTP range reads; separate CPU VM product | PAYG object distribution without egress charges at current published rate | S3 is not a local POSIX disk. End-to-end speed, complete API compatibility, service history and recovery performance are unmeasured here. Drive's client encryption is not automatically S3's security model |
| B2 | S3-compatible/native object API; separate compute needed | Published usage tariff, lifecycle/retention tooling and another provider | Downloads beyond the allowance cost money; an object mount does not remove request/latency behavior. Versioned/deleted data can continue to occupy billable storage |
| Server Auction | Full root, rescue installation, local disks and CPU | Can combine public dataset preparation, CPU work, cache and distribution on one rental | Older machines differ in throughput. Raw disk sum is not mirrored usable space. Self-managed OS, copies, updates and restore are owner operational work; availability and acceptance unverified |
| Hippius CPU VM | Linux SSH VM; vendor describes SEV-SNP and attested encrypted disk | Flexible compute alongside its S3; published resource prices | Stopped VM still billed; deletion stops billing. Default total quota 32 vCPU / 128 GB / 1,024 GB disk; account-specific approval unknown. Hardware confidentiality is not a Carbon-tested guarantee |

Sources: [Box access restrictions](https://docs.hetzner.com/storage/storage-box/access/access-ssh-rsync-borg/),
[Box single-host RAID and protocols](https://docs.hetzner.com/storage/storage-box/general/),
[Hippius range requests](https://docs.hippius.com/storage/s3/advanced),
[B2 pricing](https://www.backblaze.com/cloud-storage/pricing),
[Auction features](https://www.hetzner.com/sb/),
[Hippius compute](https://docs.hippius.com/use/compute),
[compute billing/quotas](https://docs.hippius.com/use/compute/billing).

## Storage path to recommend

For a file-oriented public corpus, the default candidate is Box plus a local
cache. Check the free capacity of the **permitted public-work host**, not a
hidden-material machine. Use immutable content/version manifests, preserve the
source/license receipt and retain a separate recoverable copy. A snapshot or
mirror on the same server does not supply provider/host independence.

For an S3-oriented public kit or public artifact downloads, Hippius PAYG is the
lower current usage tariff than B2. Keep B2 on the table for independent copies,
buyer requirements or a measured operational advantage. No decentralization
premium or Bittensor advantage is assumed. A public file is not automatically
rights-clear for redistribution; the kit's existing rights policy still applies.

A rented auction host can become a public CPU workhorse/cache, but compare
**completed cases per total euro**, not advertised cores alone. At the sampled
prices it should not displace Box purely to save storage rent. The recommendation
does not depend on any owner account being approved, including Robot.

## Public-only check before an owner purchase decision

Proposed test, not executed: copy a rights-cleared public stand-in corpus,
verify its manifest, restore it on a different public-work host, measure cold
sequential transfer and repeated small/random reads, and exercise range reads,
multipart uploads, retry/resume and deletion/version accounting where needed.
Use the real pinned worker image only on public material. Record CPU type,
physical cores/threads, memory, cache state, bytes, elapsed time and actual bill.

ASSUMPTION diagnostic corpus low/base/high **1/10/100 GB**; repeated read passes
**1/3/10** are sensitivity scenarios, not performance targets. Owner-authorized
test spending limit, acceptance latency, retention and required copy count are
HUMAN_INPUT. Research makes no purchase and runs no provider experiment.

## Why local cache matters

For a public dataset of size D repeatedly read R times, cache misses generate
approximately `D * R * (1-hit_fraction)` remote bytes; preprocessing, checkpoints
and version retention add bytes separately. An object mount can still reread
data across workers, so measure aggregate traffic rather than only one process.

For fixed **ASSUMPTION 1 TB** and effective throughput low/base/high
**50/100/500 Mbit/s**, one full transfer takes **44.44/22.22/4.44 hours** before
protocol overhead. Those are arithmetic scenarios, not measured providers;
Hetzner's advertised 1 Gbit/s auction port is only a link ceiling. Even free
egress does not make remote latency free. Sharding, staging and cache policy
belong to an authorized engineering ticket, not this research PR.
