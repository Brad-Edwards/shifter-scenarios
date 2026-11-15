"""Guard host bridge transit without changing the router's access policy."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'build/keplerops/native-platform/host-routing.py'
spec = importlib.util.spec_from_file_location('fieldlink_host_routing', SOURCE)
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class NativeDocker:
    def __init__(self):
        self.networks = {}
        self.attached = {}
        self.calls = []
        self.rules = []
        self.chain = False
        self.jump = False
        for index, (suffix, subnet) in enumerate(routing.NETWORKS.items(), 1):
            name = routing.PROJECT + '-' + suffix
            identity = f'{index:012x}' + '0' * 52
            self.networks[name] = {'Name': name, 'Id': identity, 'Internal': True,
                                   'Labels': {'com.docker.compose.project': routing.PROJECT},
                                   'Options': {}, 'IPAM': {'Config': [{'Subnet': subnet}]}}
            self.attached[name] = {'NetworkID': identity, 'IPAddress': subnet.split('/')[0].rsplit('.', 1)[0] + '.254'}

    def __call__(self, arguments, *, check=True):
        self.calls.append(arguments)
        output, code = '', 0
        if arguments[:2] == ['docker', 'inspect']:
            output = json.dumps([{'Config': {'Labels': {'com.docker.compose.project': routing.PROJECT}},
                                  'NetworkSettings': {'Networks': self.attached}}])
        elif arguments[:3] == ['docker', 'network', 'inspect']:
            output = json.dumps([self.networks[arguments[-1]]])
        elif arguments[0] == 'ip':
            output = json.dumps([{'ifname': arguments[-1], 'linkinfo': {'info_kind': 'bridge'}}])
        elif arguments[:2] == ['iptables', '-S']:
            code = 0 if self.chain else 1
            output = '\n'.join(' '.join(rule) for rule in self.rules)
        elif arguments[:2] == ['iptables', '-N']:
            self.chain = True
        elif arguments[:2] == ['iptables', '-F']:
            self.rules = []
        elif arguments[:2] == ['iptables', '-A']:
            self.rules.append(arguments[1:])
        elif arguments[:3] == ['iptables', '-C', 'DOCKER-USER']:
            code = 0 if self.jump else 1
        elif arguments[:2] == ['iptables', '-C']:
            code = 0 if ['-A', *arguments[2:]] in self.rules else 1
        elif arguments[:2] == ['iptables', '-I']:
            self.jump = True
        else:
            raise AssertionError(arguments)
        return subprocess.CompletedProcess(arguments, code, output, '')


class HostRoutingTests(unittest.TestCase):
    def test_only_same_bridge_private_transit_and_repeat_has_no_mutations(self):
        docker = NativeDocker()
        routing.configure(docker)
        mutations = [call for call in docker.calls if call[:2] in (['iptables', '-N'], ['iptables', '-F'], ['iptables', '-A'], ['iptables', '-I'])]
        self.assertEqual(len(docker.rules), 40)
        for rule in docker.rules:
            self.assertEqual(rule[rule.index('-i') + 1], rule[rule.index('-o') + 1])
            self.assertIn('--physdev-is-bridged', rule)
            self.assertIn(rule[rule.index('-s') + 1], routing.NETWORKS.values())
            self.assertIn(rule[rule.index('-d') + 1], routing.NETWORKS.values())
        routing.configure(docker)
        later = [call for call in docker.calls if call[:2] in (['iptables', '-N'], ['iptables', '-F'], ['iptables', '-A'], ['iptables', '-I'])]
        self.assertEqual(mutations, later)

    def test_foreign_expanded_and_wrong_bridge_fail_before_firewall_changes(self):
        for mutation in ('foreign', 'expanded', 'bridge', 'identity'):
            with self.subTest(mutation=mutation):
                docker = NativeDocker()
                network = next(iter(docker.networks.values()))
                if mutation == 'foreign':
                    network['Labels']['com.docker.compose.project'] = 'another-range'
                elif mutation == 'expanded':
                    network['IPAM']['Config'][0]['Subnet'] = '10.77.0.0/16'
                elif mutation == 'bridge':
                    network['Options']['com.docker.network.bridge.name'] = 'eth0'
                else:
                    next(iter(docker.attached.values()))['NetworkID'] = 'f' * 64
                with self.assertRaises(ValueError):
                    routing.configure(docker)
                self.assertFalse(any(call[0] == 'iptables' for call in docker.calls))


if __name__ == '__main__':
    unittest.main()
