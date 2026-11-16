# The `ros2 ebpf` CLI

`ros2 ebpf` is a `ros2cli` extension (package `ros2ebpf`) that starts and stops `ros2ebpfd` and talks to it over its control socket.
Every verb works locally through `/run/ros2ebpf/control.sock`, or against other hosts through ssh or the optional HTTP control port.

## Global options

`--socket PATH` (local), `--host H` (repeatable: `user@host` via ssh, `host:9478` via HTTP, `unix:///path`), `--robot R` with `--fleet-file` ([configuration.md](configuration.md#etcros2ebpffleetyaml-cli-only)), `--format table|json`.

## Verbs

| Verb | What it does |
|---|---|
| `start [-c FILE] [--log-level L] [--log-file FILE] [--timeout S] [--no-sudo] [--binary P]` | spawn `ros2ebpfd` detached (via `sudo -n` when not root), wait until it answers, print the summary; exit 1 if not healthy |
| `stop [--timeout S]` | ask the daemon to exit (counters stay in the pinned maps); exit 0 when it was not running |
| `status [-v] [-q]` | health table; exit 1 if any configured family is not fully attached (readiness check) |
| `enable <family>` / `disable <family>` | attach / detach `publish`, `take`, `services`, `udp_drops`; counters kept |
| `reload` | re-read config.yaml + expectations.yaml, no detach |
| `reset [-c FILE] [--no-sudo]` | forget every endpoint, process and drop counter while the probes stay attached; counters restart from zero at the next call (a counter reset for Prometheus); with no daemon running, removes the pinned maps under `pin_root` of the config instead (through `sudo -n` when not root) |
| `monitor [--interval S] [--view endpoints\|processes\|health] [--filter F] [--once] [--no-color]` | full-screen terminal view, no Prometheus or browser needed: endpoint rates with sparklines, processes, daemon health; `e`/`p`/`h` switch views, `/` filters, `s` sorts, `?` help, `q` quits; `--once` prints one plain frame |
| `top [--topic T] [--domain D] [--kind K] [--interval S] [--once]` | live rates from two map reads (bench tool); for `client` and `service` rows `Hz` is requests and `Hz(2nd)` is responses |
| `config show \| get KEY \| set KEY VALUE [--no-reload] \| keys` | edit the config file with validation, then reload |
| `expectations capture [--duration S] [--takers] [-o FILE] \| show` | write expectations.yaml from observed rates |
| `doctor [--config F] [--shim P]` | kernel, BTF, bpffs, pid namespace, capabilities, shim symbols, daemon, exporter, and whether the daemon resolves process identity |
| `metrics [--grep S]` | the exposition, through the control socket (works in `external` mode too) |

## `start` and privileges

`ros2 ebpf start` runs the daemon with `-c /etc/ros2ebpf/config.yaml` unless `-c FILE` says otherwise, detached, with its output in `~/.ros/log/ros2ebpfd.log`.
In the development container everything is root and nothing more is needed.
On a host where the CLI is not root, `ros2 ebpf start` runs the daemon through `sudo -n` (`sudo -v` once, or a NOPASSWD sudoers line for `ros2ebpfd`) and the daemon hands its control socket to that user, or to the `ros2ebpf` group when it exists (`sudo groupadd -f ros2ebpf && sudo usermod -aG ros2ebpf "$USER"` lets a whole team talk to it).
`--log-level debug --log-file FILE` select the verbosity and where the output goes; `--no-sudo` when the binary already has the capabilities (`CAP_BPF CAP_PERFMON CAP_SYS_PTRACE`, plus `CAP_SYS_RESOURCE`).

To run in the foreground instead: `ros2ebpfd -c /etc/ros2ebpf/config.yaml --log-level debug` (Ctrl-C stops it; `ros2 ebpf stop` works on it too).

Expected log lines of a healthy start (one shim, every family enabled):

```
I ros2ebpfd 0.1.0 starting: host=main machine_id=… distro=ubuntu-26.04 arch=x86_64 kernel=7.0.0-…
I shim <workspace>/install/rmw_implementation/lib/librmw_implementation.so: distro=lyrical arch=x86_64 dev=… ino=… (config)
I probe family publish enabled: 2/2 links
I probe family take enabled: 2/2 links
I probe family services enabled: 6/6 links
I probe family udp_drops enabled
I metrics at http://0.0.0.0:9477/metrics
I control socket at /run/ros2ebpf/control.sock
I ready: 16/16 probe links attached, 1 shim(s), offset table lyrical/x86_64
```

## Day-2 operations

```bash
ros2 ebpf config set probes.seq_gap '[/chatter]'   # edits config.yaml, then reloads the daemon
ros2 ebpf config set topics.exclude '[/parameter_events, /rosout, /tf]'
ros2 ebpf disable udp_drops                          # detach a family at runtime, counters kept
ros2 ebpf expectations capture --duration 60 --takers -o /tmp/expectations.yaml   # then copy to /etc/ros2ebpf
ros2 ebpf reload                                     # re-read config.yaml / expectations.yaml (or SIGHUP)
ros2 ebpf stop && ros2 ebpf start                    # counters survive: maps are pinned in bpffs
ros2 ebpf reset                                      # counters restart from zero, probes stay attached (also with the daemon stopped: removes the pinned maps)
```

Debug logging at runtime: `ros2 ebpf config set log_level debug`.

## Hosts without ROS: `ros2ebpf-ctl`

`ros2ebpf-ctl status|enable|disable|reload|snapshot|config|metrics` (package `ros2ebpf_daemon`, no ROS dependency) does the same over the socket, `-q` for exit-code-only.
`ros2ebpf-ctl rpc` is the ssh transport the CLI uses for `--host user@host`.

## Several hosts

`--host` can be repeated, and `--robot NAME` expands to the hosts of that robot in `fleet.yaml`; `status`, `top`, `monitor` and `metrics` then print one row or section per host.
The whole procedure for robots made of several hosts is [deployment.md](deployment.md).
