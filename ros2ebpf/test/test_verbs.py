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

import argparse
import ctypes.util
import os

import pytest
import yaml

from ros2ebpf.verb.config import coerce
from ros2ebpf.verb.config import ConfigVerb
from ros2ebpf.verb.config import get_path
from ros2ebpf.verb.config import set_path
from ros2ebpf.verb.doctor import elf_dynamic_symbols
from ros2ebpf.verb.doctor import in_host_pid_namespace
from ros2ebpf.verb.doctor import REQUIRED_SYMBOLS
from ros2ebpf.verb.doctor import self_metric
from ros2ebpf.verb.status import StatusVerb


def test_config_paths():
    doc = {}
    set_path(doc, 'probes.publish', False)
    set_path(doc, 'topics.exclude', ['/rosout'])
    set_path(doc, 'host', 'main')
    assert doc == {'probes': {'publish': False}, 'topics': {'exclude': ['/rosout']}, 'host': 'main'}
    assert get_path(doc, 'probes.publish') is False
    assert get_path(doc, 'probes.take') is None
    assert get_path(doc, 'nope.x.y') is None


def test_coerce():
    assert coerce('probes.publish', 'true') is True
    assert coerce('identity.default_domain_id', '7') == 7
    assert coerce('topics.exclude', '[/a, /b]') == ['/a', '/b']
    assert coerce('topics.exclude', '/a') == ['/a']
    assert coerce('probes.seq_gap', 'all') == 'all'
    assert coerce('histogram_buckets_seconds', '[0.001, 0.01]') == [0.001, 0.01]
    assert coerce('log_level', 'debug') == 'debug'
    with pytest.raises(ValueError):
        coerce('probes.publish', 'maybe')
    with pytest.raises(ValueError):
        coerce('identity.default_domain_id', 'x')
    with pytest.raises(ValueError):
        coerce('topics.exclude', '{a: 1}')


def test_config_set_file(tmp_path, capsys):
    cfg = tmp_path / 'config.yaml'
    cfg.write_text('probes:\n  publish: true\nlog_level: info\n')
    verb = ConfigVerb()
    args = argparse.Namespace(action='set', key='probes.take', value='false', file=str(cfg),
                              no_reload=True, format='table', socket='/x', host=[], robot=None,
                              fleet_file='/x')
    assert verb.main(args=args) == 0
    doc = yaml.safe_load(cfg.read_text())
    assert doc['probes'] == {'publish': True, 'take': False}
    assert doc['log_level'] == 'info'
    args.action = 'get'
    args.key = 'probes.take'
    assert verb.main(args=args) == 0
    assert capsys.readouterr().out.strip().endswith('false')


def test_status_table(capsys):
    results = {'local': {
        'healthy': True, 'host': 'main', 'robot': '', 'probes_attached': 15, 'probes_expected': 15,
        'shims': [{'path': '/opt/ros/rolling/lib/librmw_implementation.so'}],
        'exporter': {'mode': 'inprocess', 'serving': True}, 'maps': {'processes': 2},
        'identity': {'domains_seen': [0, 7]}, 'offset_table': 'rolling/x86_64', 'uptime_seconds': 3725,
        'probes': {'publish': {'enabled': True, 'attached': 2, 'expected': 2}},
    }}
    StatusVerb.print_table(results, {'remote': 'boom'}, verbose=False)
    out = capsys.readouterr().out
    assert 'local' in out and 'yes' in out and '15/15' in out and '0,7' in out and '1h02m' in out
    assert 'remote' in out and 'ERR' in out


def test_elf_parser_on_libc():
    libc = ctypes.util.find_library('c')
    if not libc:
        pytest.skip('no libc found')
    # find_library returns a soname; locate the file through the loader cache
    lib_dirs = ('/lib/x86_64-linux-gnu', '/lib/aarch64-linux-gnu', '/usr/lib64', '/lib64', '/usr/lib', '/lib')
    candidates = [libc] + [os.path.join(d, libc) for d in lib_dirs]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        pytest.skip('cannot locate libc file')
    syms = elf_dynamic_symbols(path)
    assert 'printf' in syms and 'malloc' in syms
    assert all(s not in syms for s in REQUIRED_SYMBOLS)


@pytest.mark.skipif(not os.path.isdir('/opt/ros'), reason='no ROS 2 installation')
def test_elf_parser_on_shim():
    for d in os.listdir('/opt/ros'):
        p = f'/opt/ros/{d}/lib/librmw_implementation.so'
        if os.path.exists(p):
            syms = elf_dynamic_symbols(p)
            assert all(s in syms for s in REQUIRED_SYMBOLS)


def test_in_host_pid_namespace(tmp_path):
    f = tmp_path / 'ns'
    f.write_text('')
    assert in_host_pid_namespace(str(f)) is False          # a regular file never has the init namespace inode
    assert in_host_pid_namespace(str(tmp_path / 'missing')) is None
    assert in_host_pid_namespace() in (True, False)        # /proc/self/ns/pid is always readable on Linux


def test_self_metric():
    body = ('# HELP ros2ebpf_map_entries Entries per pinned map.\n'
            '# TYPE ros2ebpf_map_entries gauge\n'
            'ros2ebpf_map_entries{host="a",map="endpoints"} 6\n'
            'ros2ebpf_map_entries{host="a",map="processes"} 0\n'
            'ros2ebpf_identity_resolve_failures_total{host="a"} 131\n'
            'ros2ebpf_scrape_duration_seconds 0.001\n')
    assert self_metric(body, 'ros2ebpf_map_entries', map='endpoints') == 6
    assert self_metric(body, 'ros2ebpf_map_entries', map='processes') == 0
    assert self_metric(body, 'ros2ebpf_identity_resolve_failures_total') == 131
    assert self_metric(body, 'ros2ebpf_scrape_duration_seconds') == 0.001
    assert self_metric(body, 'ros2ebpf_map_entries', map='udp_drops') is None
    assert self_metric(body, 'ros2ebpf_map') is None       # prefix of a name is not a match
