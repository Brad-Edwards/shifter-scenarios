#!/usr/bin/env python3
"""Replace FLAG_PLACEHOLDER_<CARD> markers in the code tree with the card's placement.yaml value."""
import re, subprocess, yaml
R = '/tmp/cinder-dev-release/cinder-typhoon'
pl = {f['flag_id']: f['value'] for f in yaml.safe_load(open(R + '/flags/placement.yaml'))['flags']}
files = subprocess.run("grep -rlE 'FLAG_PLACEHOLDER_[TKW][0-9]{2}\\.[0-9]+' --exclude-dir=.operator --exclude-dir=__pycache__ build assets",
                       shell=True, cwd=R, capture_output=True, text=True).stdout.split()
n = 0
for f in files:
    p = R + '/' + f
    s = open(p).read()
    new = re.sub(r'FLAG_PLACEHOLDER_([TKW]\d{2}\.\d+)', lambda m: pl[m.group(1)], s)
    n += len(re.findall(r'FLAG_PLACEHOLDER_', s))
    open(p, 'w').write(new)
print(f'filled {n} placeholders in {len(files)} files')
# Known invented or misplaced values seen in agent edits -> the card they belong to (scoped per file).
KNOWN = {
  'build/keplerops/runtime/cloud-api.py': {'FLAG{0b9877c3539fbcfa}':'K13.4','FLAG{244cd323590694f6}':'K14.2','FLAG{c1e0dbfdffe75425}':'K14.1','FLAG{19f186b21e73e545}':'K14.3'},
  'build/keplerops/runtime/cloud_api.py': {'FLAG{0b9877c3539fbcfa}':'K13.4','FLAG{244cd323590694f6}':'K14.2','FLAG{c1e0dbfdffe75425}':'K14.1','FLAG{19f186b21e73e545}':'K14.3'},
  'build/keplerops/runtime/ci.py': {'FLAG{fbd7154bb29c94fa}':'K09.3','FLAG{e4c1d273080dec0d}':'K09.4','FLAG{a4b836c914be9dc1}':'K09.1','FLAG{e1cd013a6cdd8991}':'K29.1'},
  'build/keplerops/runtime/workbench.py': {'FLAG{3040a0c2f8443498}':'K03.2','FLAG{b333bddf473ffe8c}':'K01.4','FLAG{dc079e33f8c31fc3}':'K03.1'},
  'build/keplerops/runtime/preview.py': {'FLAG{d80272e908362cf6}':'K10.2','FLAG{3262988684853120}':'K10.3','FLAG{b146d6f6e4c22bb0}':'K10.1'},
  'build/keplerops/runtime/source.py': {'FLAG{65213f715150f979}':'K11.1'},
  'build/keplerops/runtime/registry.py': {'FLAG{ae7bb9411e4f18dc}':'K07.2','FLAG{fdecb38cd9d8caf9}':'K29.3','FLAG{9099ebbc409c46a6}':'K07.1','FLAG{b0a818a78d859f0c}':'K05.1'},
  'build/keplerops/runtime/support.py': {'FLAG{c3add5a56e78f14e}':'K01.2','FLAG{1b1140a49220ce2d}':'K27.1','FLAG{0e70287767fe900a}':'K27.2','FLAG{06bff5331f0c2052}':'K27.3','FLAG{0b49ce87466c9946}':'K25.2'},
  'build/arwc/runtime/fieldlink_consumer.py': {'FLAG{dcb9c36f1eb38451}':'K26.1','FLAG{09929e787131c2bf}':'K26.2','FLAG{b461f302f2a11c33}':'K26.3'},
  'build/arwc/runtime/diagnostic_services.py': {'FLAG{1f645e26df3a9337}':'W24.1','FLAG{872d5e092b71a887}':'W24.2','FLAG{d0cc78b0a39a4025}':'W24.3','FLAG{59e9352118f165df}':'W24.4'},
  'build/arwc/runtime/process_services.py': {'FLAG{3d5d2c2140e91b8a}':'W25.1','FLAG{bce0cb872388f5cc}':'W25.2','FLAG{22a87db2c46cc60b}':'W25.3','FLAG{6337599c4e7ff993}':'W25.4'},
  'build/arwc/runtime/maintenance_renderer.py': {'FLAG{660639096fab0268}':'W26.1','FLAG{45073d5e6105d267}':'W26.2','FLAG{73d92335d305813c}':'W26.3'},
  'build/arwc/runtime/control_broker.py': {'FLAG{1a5db9933a1cbd9b}':'W26.4'},
}
import os
fixed = 0
for rel, mapping in KNOWN.items():
    p = R + '/' + rel
    if not os.path.exists(p): continue
    s2 = open(p).read(); new2 = s2
    for bad, card in mapping.items():
        if bad in new2: new2 = new2.replace(bad, pl[card]); fixed += 1
    if new2 != s2: open(p, 'w').write(new2)
print(f'corrected {fixed} known wrong values')
