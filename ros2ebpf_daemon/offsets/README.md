# Struct offset table

`ros2ebpfd` reads two things out of process memory from inside the probe:

| What | Where | Why |
|---|---|---|
| `topic_name` / `service_name` | `rmw_publisher_t`, `rmw_subscription_t`, `rmw_client_t`, `rmw_service_t` (arg 0 of every `rmw_*` call) | the label on every series |
| `publication_sequence_number` | `rmw_message_info_t` (arg 3 of `rmw_take_with_info`) | sequence-gap detection |

These are ABI, not API.
The `lyrical` branch supports ROS 2 Lyrical and Rolling, so `src/offsets.c` has one row per (distro, architecture): `lyrical/x86_64`, `lyrical/aarch64`, `rolling/x86_64`, `rolling/aarch64`.
CI regenerates the values of both distros from their `rmw` headers on every commit (`check_rmw_offsets` in `scripts/github_workflows.sh`, one job per distro) and fails when a row is stale, and the daemon exports the row it uses as `ros2ebpf_host_info{offset_table="<distro>/<arch>"}`.
That checks the rows of the runner's architecture, x86_64; there is no aarch64 runner, so the `offsets-aarch64` job runs `scripts/check_offsets_arch.sh aarch64` instead: `gen.sh` in the arm64 `ros:lyrical-ros-base` and `ros:rolling-ros-base` images under qemu-user, which checks the `aarch64` rows against the released Lyrical and Rolling binaries (one sync behind mainline) and loads no BPF.
The distro of a shim is `shims[].distro` when the config sets it, else `<distro>` of `/opt/ros/<distro>/`, else Lyrical (the `install/` of a source build); any distro without a row is refused.
A change of the `rolling` rows on the `rolling` branch is always backported here: the rolling job fails until it is.
The distro this branch follows is the one constant `ROS2EBPF_DISTRO` in `src/offsets.h`: the daemon (source builds, the default row), `gen.sh` (`ROS2EBPF_DISTRO` in the environment) and `scripts/github_workflows.sh` take it from there, and `SUPPORTED_DISTROS` of `ros2 ebpf doctor` is tested against the table.
On this branch it is `lyrical`.

A mismatch (a Lyrical or Rolling install older or newer than its row) shows up as `ros2ebpf_name_read_failures_total` increasing and/or `ros2ebpf_unknown_rmw_processes > 0` (the identifier read from offset 0 does not start with `rmw_`).

## Updating the row

In the development container (the README demo), or on any machine with the Lyrical or Rolling installation and a C compiler:

```
./gen.sh /ws/install            # or /opt/ros/lyrical, /opt/ros/rolling; ROS2EBPF_DISTRO=rolling for a Rolling workspace
# distro=lyrical arch=x86_64
pub.topic_name=16
...
# src/offsets.c row:
    { "lyrical", "x86_64", 16, 16 },
```

Replace the row in `src/offsets.c` and rebuild.
Without an aarch64 machine, `scripts/check_offsets_arch.sh aarch64` prints the aarch64 rows from the released binaries (needs docker and qemu binfmt: `docker run --privileged --rm tonistiigi/binfmt --install arm64`).
`gen.sh` needs the merged layout: `/opt/ros/<distro>`, or a workspace built with `--merge-install`.
