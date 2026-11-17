"""Check that development access cannot widen to golden instances or ports."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('peer_access', Path(__file__).with_name('peer-access.py'))
peer_access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peer_access)
PROJECT = 'prod-mgau4w'


def instance(peer):
    name, segment, address, network = peer
    return {'name': name, 'labels': {'purpose': 'development-range', 'segment': segment},
            'networkInterfaces': [{'networkIP': address,
                                  'network': f'projects/{PROJECT}/global/networks/{network}'}]}


def rule():
    return {'name': peer_access.RULE, 'network': f'projects/{PROJECT}/global/networks/cinder-arwc-golden',
            'direction': 'INGRESS', 'sourceRanges': ['10.77.49.9/32'],
            'targetTags': ['cinder-arwc-dev'], 'allowed': [{'IPProtocol': 'tcp', 'ports': ['443']}]}


class PeerAccessTests(unittest.TestCase):
    def test_rejects_golden_and_unmanaged_peer_mutations(self):
        valid = instance(peer_access.PEERS[1])
        peer_access.check_instance(valid, peer_access.PEERS[1], PROJECT)
        for mutation in ('name', 'address', 'purpose', 'network'):
            value = copy.deepcopy(valid)
            if mutation == 'name': value['name'] = 'cinder-arwc-golden'
            if mutation == 'address': value['networkInterfaces'][0]['networkIP'] = '10.77.59.2'
            if mutation == 'purpose': value['labels']['purpose'] = 'golden'
            if mutation == 'network': value['networkInterfaces'][0]['network'] = 'projects/other/global/networks/cinder-arwc-golden'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                peer_access.check_instance(value, peer_access.PEERS[1], PROJECT)

    def test_rejects_broader_or_disabled_rule_mutations(self):
        peer_access.check_rule(rule(), PROJECT)
        for key, value in (
            ('sourceRanges', ['10.77.49.0/24']), ('targetTags', ['cinder-arwc-carrier']),
            ('allowed', [{'IPProtocol': 'tcp'}]), ('disabled', True),
            ('sourceTags', ['cinder-keplerops-carrier']), ('direction', 'EGRESS'),
        ):
            changed = rule()
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                peer_access.check_rule(changed, PROJECT)

    def test_creates_only_narrow_rule_and_destination_tag(self):
        calls = []
        def cloud(command, **_):
            calls.append(command)
            if command[2:4] == ['instances', 'describe']:
                return json.dumps(instance(next(peer for peer in peer_access.PEERS if peer[0] == command[4])))
            if command[2:4] == ['firewall-rules', 'create']: return json.dumps([rule()])
            return '[]'
        with patch.object(peer_access.subprocess, 'check_output', side_effect=cloud):
            peer_access.configure(PROJECT, 'us-central1-a')
        create = next(command for command in calls if command[2:4] == ['firewall-rules', 'create'])
        self.assertIn('--source-ranges=10.77.49.9/32', create)
        self.assertIn('--target-tags=cinder-arwc-dev', create)
        self.assertIn('--allow=tcp:443', create)
        tag = next(command for command in calls if command[2:4] == ['instances', 'add-tags'])
        self.assertEqual(tag[4], 'cinder-arwc-dev')


if __name__ == '__main__':
    unittest.main()
