#!/usr/bin/env python3
"""List existing declared, mounted and owned native range volumes for backup."""
import json
import subprocess

PROJECT = 'cinder-keplerops'


def output(arguments: list[str]) -> str:
    return subprocess.check_output(arguments, text=True, timeout=30)


def inventory(run=output) -> list[str]:
    # Avoid resolving private service env files merely to read volume names.
    model = json.loads(run(['docker', 'compose', 'config', '--no-env-resolution', '--format', 'json']))
    if model['name'] != PROJECT:
        raise ValueError('Unexpected Compose project')
    declared = {value['name'] for value in model['volumes'].values()}
    existing = set(run(['docker', 'volume', 'ls', '-q']).splitlines())
    owned = set(run(['docker', 'volume', 'ls', '--filter', 'label=com.docker.compose.project=' + PROJECT, '-q']).splitlines())
    mounted = set()
    containers = run(['docker', 'compose', 'ps', '-aq']).splitlines()
    if not containers:
        raise ValueError('No range containers available for backup inventory')
    template = '{"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}}}'
    for line in run(['docker', 'inspect', '--format', template, *containers]).splitlines():
        container = json.loads(line)
        if container['labels'].get('com.docker.compose.project') != PROJECT:
            raise ValueError('Foreign container in backup inventory')
        mounted.update(mount['Name'] for mount in container['mounts'] if mount['Type'] == 'volume')
    if not mounted <= declared or not mounted <= existing:
        raise ValueError('Mounted volume is missing from declared native storage')
    selected = (declared & existing) | owned | mounted
    if not selected or any(not name.startswith(PROJECT + '-') for name in selected | declared):
        raise ValueError('Unexpected volume outside the range namespace')
    return sorted(selected)


if __name__ == '__main__':
    for volume in inventory():
        print(volume)
