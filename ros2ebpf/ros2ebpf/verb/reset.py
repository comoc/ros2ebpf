# Copyright 2026 Tomoya Fujita
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
`ros2 ebpf reset`: counters restart from zero.

With a daemon running, the `reset` method deletes every endpoint, process and
udp-drop entry while the probes stay attached; the next `rmw_*` call creates
the entry again from zero and re-announces the pid. Without a daemon on this
host the counters only live in the pinned maps, so those are removed instead.
"""

import subprocess
import sys

from ros2ebpf import daemon
from ros2ebpf.api import ConnectError
from ros2ebpf.api import resolve_targets
from ros2ebpf.api import RpcError
from ros2ebpf.verb import VerbExtension


class ResetVerb(VerbExtension):
    """Forget every endpoint, process and drop counter; counters restart from zero, probes stay attached."""

    def add_arguments(self, parser, cli_name):
        parser.add_argument(
            '--config', '-c', default=daemon.DEFAULT_CONFIG,
            help='Where pin_root is read from when no daemon is running (default: %(default)s)')
        parser.add_argument(
            '--no-sudo', action='store_true',
            help='Remove the pinned maps without sudo (only used when no daemon is running)')

    def main(self, *, args):
        local_only = not (getattr(args, 'host', None) or getattr(args, 'robot', None))
        if local_only and daemon.status(args.socket) is None:
            root = daemon.pin_root(getattr(args, 'config', daemon.DEFAULT_CONFIG))
            try:
                removed = daemon.remove_pins(root, sudo=False if getattr(args, 'no_sudo', False) else None)
            except (OSError, ValueError, subprocess.CalledProcessError) as e:
                print(f'error: cannot remove the pinned maps under {root}: {e}', file=sys.stderr)
                return 1
            print(f'ros2ebpfd is not running ({args.socket}); '
                  + (f'removed the pinned maps under {root}' if removed else f'nothing pinned under {root}'))
            return 0
        try:
            clients = resolve_targets(args)
        except ConnectError as e:
            print(f'error: {e}', file=sys.stderr)
            return 2
        rc = 0
        for c in clients:
            try:
                r = c.call('reset')
                print(f"{c.name}: {r.get('message', 'reset')}")
            except (ConnectError, RpcError) as e:
                print(f'{c.name}: error: {e}', file=sys.stderr)
                rc = 1
            finally:
                c.close()
        return rc
