#!/usr/bin/env python3
"""Administrator-only single-interface acceptance, never using the real catalog."""

import argparse
from dataclasses import asdict
import json
import os
from uuid import uuid4

from check_workstations import UBUNTU_IMAGE, UBUNTU_USER, validate_lab, RuntimePolicy, DockerRuntime, Session, SessionState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid', type=int, required=True)
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error('Run as administrator with the desktop UID')
    runtime = DockerRuntime(workstation_images={UBUNTU_IMAGE}, checkpoint_scope='network-test-' + uuid4().hex)
    runtime.client.api.timeout = 240
    policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
    sessions = []

    def start(internet=None, secondary=False):
        network = {'id': 'lan'}
        if internet is not None:
            network['internet'] = internet
        networks = [network]
        if secondary:
            networks.append({'id': 'backend', 'internet': False})
        document = {
            'apiVersion': 'cyberlab.ptit/v1', 'kind': 'Lab',
            'metadata': {'id': 'network-fixture', 'name': 'Network fixture', 'version': '1.0.0'},
            'networks': networks, 'terminals': ['client', 'server'],
            'nodes': [{'id': name, 'image': UBUNTU_IMAGE, 'command': ['sleep', 'infinity'],
                       'networks': ['lan', 'backend'] if secondary and name == 'server' else ['lan'],
                       'user': asdict(UBUNTU_USER), 'resources': {'memory_mb': 512, 'cpu_millicores': 1000}}
                      for name in ('client', 'server')],
        }
        lab = validate_lab(document)
        policy.validate(lab)
        session = Session(uuid4().hex, lab, arguments.uid, SessionState.RUNNING, 'fixture', 'fixture')
        sessions.append(session)
        runtime.start(session)
        container(session, 'server').exec_run(
            ['/usr/bin/timeout', '220', '/usr/bin/python3', '-m', 'http.server', '18765', '--directory', '/tmp'],
            user='2000:2000', detach=True)
        return session

    def container(session, name):
        return runtime._workspace_container(session, next(node for node in session.lab.nodes if node.id == name))

    def run(session, name, script):
        result = container(session, name).exec_run(
            ['/usr/bin/timeout', '200', '/bin/bash', '-euc', script], user='2000:2000')
        if result.exit_code:
            raise RuntimeError(f'Fixture {name} failed ({result.exit_code}): {result.output[-3000:].decode(errors="replace")}')
        return result.output.decode()

    def topology(session, external, count=1):
        networks = runtime._resources(runtime.client.networks, session.id)
        assert len(networks) == count
        lan = next(network for network in networks if network.name.endswith('-lan'))
        assert lan.attrs['Internal'] is not external
        for node in session.lab.nodes:
            current = container(session, node.id)
            assert len(current.attrs['NetworkSettings']['Networks']) == len(node.networks)
            assert not current.attrs['HostConfig']['PortBindings']
            links = json.loads(run(session, node.id, 'ip -j link show'))
            names = {link['ifname'].split('@')[0] for link in links}
            assert names == {'lo', *('eth' + str(index) for index in range(len(node.networks)))}, names
        run(session, 'client', 'getent hosts server >/dev/null; curl --noproxy "*" --max-time 5 '
            '--retry 2 --retry-connrefused --retry-delay 1 -fsS http://server:18765 >/dev/null')
        return lan.id

    try:
        online = start()
        online_network = topology(online, True)
        run(online, 'client', 'ip route show default | grep -q "dev eth0"; '
            'sudo -n apt-get -o Acquire::Retries=0 -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 '
            '-o APT::Update::Error-Mode=any update -qq; '
            'sudo -n env DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=0 '
            '-o Acquire::http::Timeout=15 install -y --no-install-recommends hello >/dev/null; hello >/dev/null')
        print('PASS: one eth0 carries internal DNS/TCP, default route, apt update/install', flush=True)

        separate = start(True)
        assert topology(separate, True) != online_network
        other_ip = next(iter(container(separate, 'server').attrs['NetworkSettings']['Networks'].values()))['IPAddress']
        run(online, 'client', f'! curl --noproxy "*" --max-time 3 -fsS http://{other_ip}:18765 >/dev/null 2>&1')
        print('PASS: simultaneous Sessions own separate bridges; cross-bridge TCP blocked', flush=True)
        runtime.remove(separate.id)

        offline = start(False)
        topology(offline, False)
        for name in ('client', 'server'):
            run(offline, name, 'test -z "$(ip route show default)"')
        print('PASS: offline LAN keeps local DNS/TCP, one eth0 and no hidden Internet route', flush=True)
        runtime.remove(offline.id)

        multi = start(True, secondary=True)
        topology(multi, True, count=2)
        run(multi, 'server', 'test -n "$(ip route show default)"')
        print('PASS: eth1 exists only for the explicitly attached second network', flush=True)
    finally:
        try:
            for session in sessions:
                runtime.remove(session.id)
        finally:
            runtime.client.close()
    print('PASS: isolated fixture resources removed; production catalog and Sessions untouched', flush=True)


if __name__ == '__main__':
    main()
