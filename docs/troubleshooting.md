# Troubleshooting

Run `ros2 ebpf doctor` first: it checks the kernel, BTF, bpffs, capabilities, the shim symbols, the daemon and the exporter, one PASS / INFO / FAIL line each.
Then:

| Symptom | Cause / fix |
|---|---|
| `failed to load BPF objects` / `libbpf: … BTF` | kernel without BTF or < 5.8; `ls /sys/kernel/btf/vmlinux` |
| `cannot create pin root /sys/fs/bpf/ros2ebpf` | bpffs not mounted: `sudo mount -t bpf bpf /sys/fs/bpf` |
| `attach … failed: Operation not permitted` | missing `CAP_BPF`/`CAP_PERFMON` (or `CAP_SYS_ADMIN` on < 5.8); container not privileged |
| `no librmw_implementation.so found yet` | no ROS process running and no `shims:` entry; harmless, discovery keeps scanning |
| no `ros2_*` series at all, while `ros2ebpf_map_entries{map="endpoints"}` > 0, `map="processes"` is 0 and `ros2ebpf_identity_resolve_failures_total` grows | the daemon is not in the host pid namespace: the probes report host pids and `/proc/<pid>` does not exist in the daemon's container, so every endpoint stays unresolved and is skipped at scrape time; start the container with `--pid host` (the DaemonSet sets `hostPID: true`) |
| `domain_id="unknown"` | `/proc/<pid>/environ` unreadable: add `CAP_SYS_PTRACE`, or the process runs in a different user namespace |
| `ros2ebpf_name_read_failures_total` grows, `ros2ebpf_unknown_rmw_processes > 0` | struct offsets differ from the table: this Rolling is older or newer than the row in `ros2ebpf_daemon/src/offsets.c`; run `ros2ebpf_daemon/offsets/gen.sh <prefix>` and update the row ([offsets/README.md](../ros2ebpf_daemon/offsets/README.md)) |
| `shim … ROS 2 humble on x86_64 is not supported` | ros2ebpf follows Rolling only; a shim under `/opt/ros/<other distro>/` is skipped |
| `shim …: FAIL (open: No such file or directory)` | the `shims:` path in `/etc/ros2ebpf/config.yaml` does not exist in the daemon's mount namespace; for a source build it is `<workspace>/install/rmw_implementation/lib/librmw_implementation.so` as seen from inside the container |
| `shim … is not a usable librmw_implementation.so: missing …` | wrong path (vendor library instead of the shim?) |
| `ros2 ebpf status`: `cannot connect … Permission denied` | add your user to group `ros2ebpf`, or use `sudo` ([cli.md](cli.md#start-and-privileges)) |
| `pinned maps have ABI N … recreating` | upgrade changed the map layout; counters reset once |
| counters for a one-shot client never appear | endpoint counters are deleted with the endpoint; look at the server side (`side="server"`) |
| many `pid … exited: removed 0 endpoints` | normal: `rmw_destroy_*` already removed them at clean shutdown |
| a node started before the daemon shows nothing | it is counted from its next `rmw_*` call: the uprobe lives on the library's inode, not on a process; a node that only publishes intra-process never calls `rmw_publish` |

Debug logging: `ros2 ebpf config set log_level debug` (or `--log-level debug` in the foreground).
The daemon's own health series (`ros2ebpf_probes_attached`, `ros2ebpf_*_failures_total`, …) are listed in [metrics.md](metrics.md), and the "ros2ebpf daemon health" Grafana dashboard plots them.
