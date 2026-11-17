#!/usr/bin/env python3
"""Allow only the FieldLink development VM to reach the ARWC development carrier."""
import argparse
import json
import os
import subprocess

RULE = 'cinder-dev-fieldlink-to-arwc'
TARGET = 'cinder-arwc-dev'
PEERS = (
    ('cinder-fieldlink-dev', 'fieldlink', '10.77.49.9', 'cinder-keplerops-golden'),
    (TARGET, 'arwc', '10.77.59.11', 'cinder-arwc-golden'),
)


def check_instance(value: dict, peer: tuple, project: str) -> None:
    name, segment, address, network = peer
    interface = value['networkInterfaces'][0]
    if (value['name'] != name
            or value.get('labels', {}).get('purpose') != 'development-range'
            or value.get('labels', {}).get('segment') != segment
            or interface['networkIP'] != address
            or interface['network'].split('projects/', 1)[-1] != f'{project}/global/networks/{network}'):
        raise ValueError('Peer access requires the exact managed development VMs')


def check_rule(value: dict, project: str) -> None:
    expected = {
        'name': RULE, 'direction': 'INGRESS', 'sourceRanges': ['10.77.49.9/32'],
        'targetTags': [TARGET], 'allowed': [{'IPProtocol': 'tcp', 'ports': ['443']}],
    }
    if (any(value.get(key) != item for key, item in expected.items())
            or value['network'].split('projects/', 1)[-1] != f'{project}/global/networks/cinder-arwc-golden'
            or value.get('disabled', False)
            or any(value.get(key) for key in ('denied', 'sourceTags', 'sourceServiceAccounts',
                                              'targetServiceAccounts', 'destinationRanges'))):
        raise ValueError('Existing development peer rule has an unexpected scope; refusing to change it')


def configure(project: str, zone: str) -> None:
    def cloud(*arguments: str):
        return json.loads(subprocess.check_output(
            [os.environ.get('GCLOUD_BIN', 'gcloud'), 'compute', *arguments,
             f'--project={project}', '--format=json'], text=True, timeout=90))

    peers = []
    for peer in PEERS:
        value = cloud('instances', 'describe', peer[0], f'--zone={zone}')
        check_instance(value, peer, project)
        peers.append(value)
    tagged = cloud('instances', 'list', f'--filter=tags.items={TARGET}')
    if any(value['name'] != TARGET or value['zone'].rsplit('/', 1)[-1] != zone for value in tagged):
        raise ValueError('The development destination tag is present on another instance')
    rules = cloud('firewall-rules', 'list', f'--filter=name={RULE}')
    if rules:
        if len(rules) != 1:
            raise ValueError('Ambiguous development peer rule')
        check_rule(rules[0], project)
    else:
        created = cloud('firewall-rules', 'create', RULE,
                        '--network=cinder-arwc-golden', '--direction=INGRESS',
                        '--allow=tcp:443', '--source-ranges=10.77.49.9/32',
                        f'--target-tags={TARGET}',
                        '--description=FieldLink development delivery to the ARWC development carrier')
        check_rule(created[0] if isinstance(created, list) else created, project)
    if TARGET not in peers[1].get('tags', {}).get('items', []):
        cloud('instances', 'add-tags', TARGET, f'--zone={zone}', f'--tags={TARGET}')
    print('Development peer access ready: 10.77.49.9 -> cinder-arwc-dev TCP 443')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('zone')
    args = parser.parse_args()
    configure(args.project, args.zone)
