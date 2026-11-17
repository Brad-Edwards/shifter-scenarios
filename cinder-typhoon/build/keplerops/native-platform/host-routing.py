#!/usr/bin/env python3
"""Permit range-router L2 transit before Docker's internal subnet filter."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from urllib.request import Request, urlopen

PROJECT = 'cinder-keplerops'
CHAIN = 'CINDER-FIELDLINK-L2'
COMMENT = 'cinder-fieldlink-native-routing'
NETWORKS = {'corporate': '10.77.50.0/24', 'delivery': '10.77.51.0/24',
            'cloud': '10.77.52.0/24', 'jobs': '10.77.53.0/24', 'connector': '10.77.60.0/24'}


def command(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    if arguments[0] == 'iptables':
        arguments = ['iptables', '--wait', '10', *arguments[1:]]
    return subprocess.run(arguments, check=check, capture_output=True, text=True, timeout=30)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def configure(run=command) -> None:
    router = json.loads(run(['docker', 'inspect', 'cinder-keplerops-router']).stdout)[0]
    require(router['Config']['Labels']['com.docker.compose.project'] == PROJECT, 'Foreign router project')
    attached = router['NetworkSettings']['Networks']
    require(set(attached) == {PROJECT + '-' + name for name in NETWORKS}, 'Unexpected router networks')
    bridges = []
    for suffix, subnet in NETWORKS.items():
        name = PROJECT + '-' + suffix
        network = json.loads(run(['docker', 'network', 'inspect', name]).stdout)[0]
        require(network['Name'] == name and network['Internal'] is True, 'Unexpected internal network')
        require(network['Labels']['com.docker.compose.project'] == PROJECT, 'Foreign network project')
        require(len(network['IPAM']['Config']) == 1, 'Unexpected network address count')
        require(network['IPAM']['Config'][0]['Subnet'] == subnet, 'Unexpected private subnet')
        identity = network['Id']
        require(bool(re.fullmatch(r'[0-9a-f]{64}', identity)), 'Invalid network identity')
        require(not network.get('Options', {}).get('com.docker.network.bridge.name'), 'Unexpected custom bridge')
        require(attached[name]['NetworkID'] == identity, 'Router network identity mismatch')
        require(attached[name]['IPAddress'] == subnet.split('/')[0].rsplit('.', 1)[0] + '.254', 'Unexpected router address')
        bridge = 'br-' + identity[:12]
        link = json.loads(run(['ip', '-d', '-j', 'link', 'show', 'dev', bridge]).stdout)[0]
        require(link['ifname'] == bridge and link['linkinfo']['info_kind'] == 'bridge', 'Unexpected bridge interface')
        bridges.append((bridge, subnet))
    rules = []
    for bridge, local in bridges:
        for other in NETWORKS.values():
            if local == other:
                continue
            for source, destination in ((local, other), (other, local)):
                rules.append(['-A', CHAIN, '-m', 'physdev', '--physdev-is-bridged',
                              '-i', bridge, '-o', bridge, '-s', source, '-d', destination, '-j', 'ACCEPT'])
    existing = run(['iptables', '-S', CHAIN], check=False)
    if existing.returncode:
        run(['iptables', '-N', CHAIN])
    actual = [line for line in existing.stdout.splitlines() if line.startswith('-A ')]
    matches = len(actual) == len(rules) and all(not run(['iptables', '-C', *rule[1:]], check=False).returncode for rule in rules)
    if not matches:
        run(['iptables', '-F', CHAIN])
        for rule in rules:
            run(['iptables', *rule])
    jump = ['DOCKER-USER', '-m', 'comment', '--comment', COMMENT, '-j', CHAIN]
    if run(['iptables', '-C', *jump], check=False).returncode:
        run(['iptables', '-I', jump[0], '1', *jump[1:]])
    print('Native range-router bridge transit configured; router access rules unchanged.')


def main() -> None:
    require(os.geteuid() == 0 and (socket.gethostname() in ('cinder-fieldlink-dev', 'cinder-keplerops-golden') or os.path.exists('/etc/cinder-keplerops-image')), 'Wrong development host or user')
    request = Request('http://metadata.google.internal/computeMetadata/v1/project/project-id',
                      headers={'Metadata-Flavor': 'Google'})
    with urlopen(request, timeout=5) as response:
        require(response.read().decode() == 'prod-mgau4w', 'Wrong development project')
    configure()


if __name__ == '__main__':
    main()
