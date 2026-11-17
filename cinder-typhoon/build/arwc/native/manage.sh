#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $(hostname) == cinder-arwc-dev ]] || {
  echo 'This mutable deployment is restricted to cinder-arwc-dev.' >&2
  exit 1
}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# shellcheck disable=SC1091
source images.env
compose=(docker compose --env-file images.env -f compose.yaml -f corporate.compose.yaml -f dmz.compose.yaml)
hostnames=(edge.arwc.test erp.arwc.test identity.arwc.test documents.arwc.test reports.arwc.test engineering.arwc.test suppliers.arwc.test render.arwc.test read-data.arwc.test)
certificate_is_current() {
  [[ -f .operator/ca/tls/server.crt ]] || return 1
  openssl x509 -in .operator/ca/tls/server.crt -noout -checkend 86400 >/dev/null || return 1
  for hostname in "${hostnames[@]}"; do
    openssl verify -verify_hostname "$hostname" \
      -CAfile .operator/ca/certs/root_ca.crt -untrusted .operator/ca/certs/intermediate_ca.crt \
      .operator/ca/tls/server.crt >/dev/null 2>&1 || return 1
  done
}
action=${1:-up}
case "$action" in
  build)
    python3 prepare.py
    "${compose[@]}" pull --ignore-buildable
    "${compose[@]}" build dns kerberos workplace
    ;;
  up)
    python3 prepare.py
    if [[ ! -f .operator/ca/config/ca.json ]]; then
      docker run --pull never --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        ca init --deployment-type standalone --name 'ARWC Certificate Authority' \
        --dns ca.arwc.test --address :9000 --provisioner infrastructure \
        --password-file /home/step/secrets/password >/dev/null 2>&1
    fi
    # Install the archive-submitter x509 template so step-ca signs archive
    # enrollment certificates with the participant-supplied CN (OU value).
    mkdir -p .operator/ca/templates/certs/x509
    cp templates/archive-submitter.tpl .operator/ca/templates/certs/x509/archive-submitter.tpl
    # Configure the infrastructure provisioner to use the template.
    python3 - <<'PYEOF'
import json, pathlib
p = pathlib.Path('.operator/ca/config/ca.json')
if p.exists():
    config = json.loads(p.read_text())
    for prov in config.get('authority', {}).get('provisioners', []):
        if prov.get('name') == 'infrastructure':
            prov.setdefault('options', {}).setdefault('x509', {})['templateFile'] = 'templates/certs/x509/archive-submitter.tpl'
            break
    p.write_text(json.dumps(config, indent=2))
PYEOF
    # Extract the provisioner JWK for the archive service to generate OTTs.
    python3 - <<'PYEOF'
import json, pathlib
p = pathlib.Path('.operator/ca/config/ca.json')
out = pathlib.Path('.operator/ca/provisioner.enc.json')
if p.exists():
    config = json.loads(p.read_text())
    for prov in config.get('authority', {}).get('provisioners', []):
        if prov.get('name') == 'infrastructure' and prov.get('encryptedKey'):
            out.write_text(prov['encryptedKey'])
            out.chmod(0o644)
            break
PYEOF
    if ! certificate_is_current; then
      mkdir -p .operator/ca/tls
      sans=()
      for hostname in "${hostnames[@]}"; do sans+=(--san "$hostname"); done
      docker run --pull never --rm --user 0:0 --network none --entrypoint step \
        -v "$PWD/.operator/ca:/home/step" "$STEP_CA_IMAGE" \
        certificate create edge.arwc.test /home/step/tls/server.crt /home/step/tls/server.key \
        --profile leaf --ca /home/step/certs/intermediate_ca.crt \
        --ca-key /home/step/secrets/intermediate_ca_key \
        --ca-password-file /home/step/secrets/password --not-after 8760h \
        "${sans[@]}" \
        --no-password --insecure --force >/dev/null
      cat .operator/ca/certs/intermediate_ca.crt >> .operator/ca/tls/server.crt
    fi
    chown -R 1000:1000 .operator/ca
    chmod 0755 .operator/ca/tls
    chown -R root:root .operator/ca/tls
    bash corporate-access.sh prepare
    # Extract retained engineering tools (including IMG-FIT-204-R6.bin for W16) from Docker images.
    bash capture-retained-tools.sh
    "${compose[@]}" up --no-build --pull never --wait --wait-timeout 420
    "${compose[@]}" exec -T --user www-data nextcloud php occ background:cron
    bash desktop-access.sh
    bash corporate-access.sh trust
    ;;
  status)
    "${compose[@]}" ps
    ;;
  seed)
    "${compose[@]}" exec -T corporate-db psql -U corporate -d planning \
      --set ON_ERROR_STOP=1 < planning.sql
    "${compose[@]}" --profile seed run --rm seed-erp
    # W11.1: Seed ASC-CRR-4417 Task in ERPNext under PROJ-0001 (WO-CRR-4417)
    # linked to asset AST-CRR-017. This Task supports the W11.1 contract truthfulness.
    # NOTE: Jules must NOT have DocShare on this task. The W11.2 path is the Metabase
    # SQL injection, not ERPNext access. No DocShare is seeded here.
    if [ -f ".operator/erp-seed.env" ]; then
        erp_admin_pass=$(grep '^ERP_ADMIN_PASSWORD=' .operator/erp-seed.env | cut -d= -f2)
        if [ -n "${erp_admin_pass}" ]; then
            python3 -c "
import json, ssl, urllib.request
from urllib.parse import urlencode
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = __import__('ssl').CERT_NONE
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
login_req = urllib.request.Request('https://suppliers.arwc.test/api/method/login',
    data=urlencode({'usr':'Administrator','pwd':'${erp_admin_pass}'}).encode(), method='POST',
    headers={'Content-Type':'application/x-www-form-urlencoded'})
with opener.open(login_req) as r: pass
check = urllib.request.Request('https://suppliers.arwc.test/api/resource/Task?filters=[[\"subject\",\"like\",\"%ASC-CRR-4417%\"]]&fields=[\"name\",\"subject\"]')
with opener.open(check) as r:
    tasks = json.loads(r.read()).get('data', [])
if tasks:
    print(f'ASC-CRR-4417 Task already exists: {tasks[0][\"name\"]}')
else:
    task_data = {'doctype':'Task','subject':'ASC-CRR-4417 — Asset-work association AST-CRR-017','project':'PROJ-0001',
        'description':'Asset-work association record. Asset: AST-CRR-017. Relation: ASSET_WORK. Association identifier: ASC-CRR-4417. Work order: WO-CRR-4417.',
        'status':'Open','priority':'Medium'}
    req = urllib.request.Request('https://suppliers.arwc.test/api/resource/Task',
        data=json.dumps(task_data).encode(), method='POST', headers={'Content-Type':'application/json'})
    with opener.open(req) as r:
        task_name = json.loads(r.read())['data']['name']
    print(f'Created ASC-CRR-4417 Task: {task_name} (no Jules DocShare — W11.2 uses SQL injection)')
" 2>/dev/null || echo "W11.1 ERPNext seeding skipped (ERPNext unavailable)"
        fi
    fi
    ;;
  seed-corporate-documents)
    python3 import-corporate-documents.py
    ;;
  seed-documents)
    "${compose[@]}" --profile seed run --rm seed-documents
    ;;
  seed-reports)
    "${compose[@]}" --profile seed run --rm seed-reports
    # Derive nadia.corvane's Metabase password from STAFF_SEED and write to the
    # golden operator dir so the archive service can create her Metabase session.
    if [ -f ".operator/documents-seed.env" ]; then
        staff_seed=$(grep '^STAFF_SEED=' .operator/documents-seed.env | cut -d= -f2)
        nadia_email="nadia.corvane@alterrawaterco.com"
        if [ -n "${staff_seed}" ]; then
            nadia_password=$(python3 -c "import hashlib,hmac,sys
seed=sys.argv[1]; email=sys.argv[2]
print(hmac.new(seed.encode(), email.encode(), hashlib.sha256).hexdigest())" \
                "${staff_seed}" "${nadia_email}")
            golden_op="$(cd .. && pwd)/.operator"
            mkdir -p "${golden_op}/archive-workflow"
            printf '{"email":"%s","password":"%s","metabase_url":"https://reports.arwc.test"}\n' \
                "${nadia_email}" "${nadia_password}" > "${golden_op}/archive-workflow/nadia-metabase.json"
            chmod 0644 "${golden_op}/archive-workflow/nadia-metabase.json"
            echo "Wrote nadia Metabase credentials to golden operator dir"
        fi
    fi
    # Query Metabase for the QRY-RESERVE-R7 question ID and write reports-state.json.
    golden_op="$(cd .. && pwd)/.operator"
    if [ -f ".operator/reports-seed.env" ]; then
        metabase_admin_password=$(grep '^METABASE_ADMIN_PASSWORD=' .operator/reports-seed.env | cut -d= -f2)
        if [ -n "${metabase_admin_password}" ]; then
            qry_id=$(python3 -c "
import json, ssl, urllib.request, sys
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = __import__('ssl').CERT_NONE
req = urllib.request.Request(
    'https://reports.arwc.test/api/session',
    data=json.dumps({'username':'planning.admin@alterrawaterco.com','password':sys.argv[1]}).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
    s = json.loads(r.read())['id']
req2 = urllib.request.Request('https://reports.arwc.test/api/card', headers={'X-Metabase-Session': s})
with urllib.request.urlopen(req2, context=ctx, timeout=10) as r:
    cards = json.loads(r.read())
q = [c for c in cards if c['name'] == 'QRY-RESERVE-R7']
print(q[0]['id'] if q else '')
" "${metabase_admin_password}" 2>/dev/null || true)
            if [ -n "${qry_id}" ]; then
                alloc_id=$(python3 -c "
import json, ssl, urllib.request
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = __import__('ssl').CERT_NONE
req = urllib.request.Request(
    'https://reports.arwc.test/api/session',
    data=json.dumps({'username':'planning.admin@alterrawaterco.com','password':'${metabase_admin_password}'}).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
    s = json.loads(r.read())['id']
req2 = urllib.request.Request('https://reports.arwc.test/api/card', headers={'X-Metabase-Session': s})
with urllib.request.urlopen(req2, context=ctx, timeout=10) as r:
    cards = json.loads(r.read())
q = [c for c in cards if c['name'] == 'ALLOC-DP3-CURRENT']
print(q[0]['id'] if q else '')
" 2>/dev/null || true)
                mkdir -p "${golden_op}/archive-workflow"
                meter_id=$(python3 -c "
import json, ssl, urllib.request
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = __import__('ssl').CERT_NONE
req = urllib.request.Request(
    'https://reports.arwc.test/api/session',
    data=json.dumps({'username':'planning.admin@alterrawaterco.com','password':'${metabase_admin_password}'}).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
    s = json.loads(r.read())['id']
req2 = urllib.request.Request('https://reports.arwc.test/api/card', headers={'X-Metabase-Session': s})
with urllib.request.urlopen(req2, context=ctx, timeout=10) as r:
    cards = json.loads(r.read())
q = [c for c in cards if c['name'] == 'METER-DP3-CURRENT']
print(q[0]['id'] if q else '')
" 2>/dev/null || true)
                printf '{"qry_reserve_r7_id":%s,"alloc_dp3_question_id":"%s","meter_dp3_question_id":"%s","metabase_url":"https://reports.arwc.test"}\n' \
                    "${qry_id}" "${alloc_id}" "${meter_id}" \
                    > "${golden_op}/archive-workflow/reports-state.json"
                chmod 0644 "${golden_op}/archive-workflow/reports-state.json"
                echo "Wrote reports state (qry_id=${qry_id}, alloc_id=${alloc_id}, meter_id=${meter_id}) to golden operator dir"
            fi
        fi
    fi
    ;;
  seed-engineering)
    bash seed-engineering.sh
    ;;
  seed-dmz)
    "${compose[@]}" exec -T --user postgres corporate-db bash -s < init-corporate.sh
    "${compose[@]}" exec -T corporate-db psql -U corporate -d planning \
      --set ON_ERROR_STOP=1 < dmz-views.sql
    ;;
  seed-portal)
    "${compose[@]}" --profile seed run --rm seed-portal
    # Write the contractor portal ERPNext reader config to the golden operator directory.
    # Contractor portal uses this to fetch APT-CRR-2026-09-18 from ERPNext at startup.
    erp_admin_password=$(grep -oP '(?<=ERP_ADMIN_PASSWORD=).+' .operator/erp-seed.env 2>/dev/null || true)
    if [ -n "${erp_admin_password}" ]; then
        portal_golden_op="$(cd .. && pwd)/.operator"
        # Write ERPNext reader config for contractor portal
        contractors_erp_json='{"url":"https://suppliers.arwc.test","username":"Administrator","password":"'"${erp_admin_password}"'"}'
        mkdir -p "${portal_golden_op}"
        printf '%s\n' "${contractors_erp_json}" > "${portal_golden_op}/contractors-erp.json"
        printf '%s\n' "${contractors_erp_json}" > ".operator/contractors-erp.json"
        chmod 0644 "${portal_golden_op}/contractors-erp.json" 2>/dev/null || true
        chmod 0644 ".operator/contractors-erp.json" 2>/dev/null || true
        echo "W13.1: Wrote contractors-erp.json for contractor portal ERPNext fetch"
        # Write Nextcloud reader config (W14.1: contractor portal fetches field bag)
        nc_admin_password=$(grep -oP '(?<=DOCUMENTS_ADMIN_PASSWORD=).+' .operator/documents-seed.env 2>/dev/null || true)
        if [ -n "${nc_admin_password}" ]; then
            contractors_nc_json='{"url":"https://documents.arwc.test","username":"records-admin","password":"'"${nc_admin_password}"'","field_bag_path":"/remote.php/dav/files/records-admin/contractor-workspace/FIELD-BAG-CRR-4417-R3.json"}'
            mkdir -p "${portal_golden_op}"
            printf '%s\n' "${contractors_nc_json}" > "${portal_golden_op}/contractors-nc.json"
            printf '%s\n' "${contractors_nc_json}" > ".operator/contractors-nc.json"
            chmod 0644 "${portal_golden_op}/contractors-nc.json" ".operator/contractors-nc.json" 2>/dev/null || true
            echo "W14.1: Wrote contractors-nc.json for contractor portal Nextcloud fetch"
        fi
        # Write Nextcloud reader config for approval/maintenance-review service (W15.1).
        approval_nc_path="/remote.php/dav/files/records-admin/contractor-workspace/CACHE-DRW-OG2-R8.json"
        approval_nc_json='{"url":"https://documents.arwc.test","username":"records-admin","password":"'"${nc_admin_password}"'","association_path":"'"${approval_nc_path}"'"}'
        mkdir -p "${portal_golden_op}"
        printf '%s\n' "${approval_nc_json}" > "${portal_golden_op}/approval-nc.json"
        printf '%s\n' "${approval_nc_json}" > ".operator/approval-nc.json"
        chmod 0644 "${portal_golden_op}/approval-nc.json" ".operator/approval-nc.json" 2>/dev/null || true
        echo "W15.1: Wrote approval-nc.json for maintenance-review Nextcloud fetch"
        # Write ERPNext reader config for maintenance-review service (W15.4).
        approval_erp_json='{"url":"https://suppliers.arwc.test","username":"Administrator","password":"'"${erp_admin_password}"'"}'
        printf '%s\n' "${approval_erp_json}" > "${portal_golden_op}/approval-erp.json"
        printf '%s\n' "${approval_erp_json}" > ".operator/approval-erp.json"
        chmod 0644 "${portal_golden_op}/approval-erp.json" ".operator/approval-erp.json" 2>/dev/null || true
        echo "W15.4: Wrote approval-erp.json for maintenance-review ERPNext fetch"
    fi
    ;;
  seed-early-cards)
    "${compose[@]}" --profile seed run --rm seed-early-cards
    ;;
  seed-identity)
    "${compose[@]}" --profile seed run --rm seed-identity
    ;;
  seed-archive)
    # Generate a pool of step-ca OTTs for the archive enrollment endpoint.
    # The provisioner key stays on the host; the archive container receives
    # only the pre-generated tokens, not the signing secrets.
    # Each OTT is single-use (step-ca enforces jti uniqueness).
    # Generate enough for a full participant session.
    mkdir -p .operator/archive-workflow/tokens
    chmod 0755 .operator/archive-workflow/tokens
    # Clear any stale tokens from a previous reset.
    rm -f .operator/archive-workflow/tokens/ott-*.jwt
    # Extract the provisioner encrypted key if not already done.
    python3 - <<'PYEOF'
import json, pathlib
p = pathlib.Path('.operator/ca/config/ca.json')
out = pathlib.Path('.operator/ca/provisioner.enc.json')
if p.exists() and not out.exists():
    config = json.loads(p.read_text())
    for prov in config.get('authority', {}).get('provisioners', []):
        if prov.get('name') == 'infrastructure' and prov.get('encryptedKey'):
            out.write_text(prov['encryptedKey']); out.chmod(0o644); break
PYEOF
    # Generate OTTs from within the running step-ca container.
    # The step-ca server must be running (it was started by 'up' above).
    # Generate 50 OTTs (1-hour validity each; participant calls GET for a fresh one).
    # 50 tokens covers repeated enrollment attempts across a full event session.
    echo "Generating step-ca enrollment tokens..."
    for i in $(seq -w 1 50); do
      # Note: stdout redirect must come before stderr redirect for docker exec.
      docker exec cinder-arwc-native-ca-1 \
        step ca token \
        --provisioner infrastructure \
        --key /home/step/provisioner.enc.json \
        --password-file /home/step/secrets/password \
        --ca-url https://ca.arwc.test:9000 \
        --root /home/step/certs/root_ca.crt \
        --not-after 1h \
        "archive-submitter" \
        > ".operator/archive-workflow/tokens/ott-${i}.jwt" 2>/dev/null || true
    done
    # Also copy root and intermediate certs for the participant to discover.
    cp .operator/ca/certs/root_ca.crt .operator/archive-workflow/step-ca-root.pem
    cp .operator/ca/certs/intermediate_ca.crt .operator/archive-workflow/step-ca-intermediate.pem
    chmod 0644 .operator/archive-workflow/step-ca-root.pem .operator/archive-workflow/step-ca-intermediate.pem
    echo "Generated $(ls .operator/archive-workflow/tokens/ott-*.jwt 2>/dev/null | wc -l) enrollment tokens"
    # Copy tokens to the golden ARWC operator directory for the archive container.
    # From build/arwc/native/, the golden .operator is at ../  (build/arwc/.operator).
    golden_op="$(cd .. && pwd)/.operator"
    mkdir -p "${golden_op}/archive-workflow/tokens"
    chmod 0755 "${golden_op}/archive-workflow/tokens"
    cp .operator/archive-workflow/tokens/ott-*.jwt "${golden_op}/archive-workflow/tokens/" 2>/dev/null || true
    chmod 0644 "${golden_op}/archive-workflow/tokens/"ott-*.jwt 2>/dev/null || true
    # Derive a stable password for the archive query role from the handover key.
    # The handover key is stable per range; this keeps the archive DB password
    # consistent across seed-archive runs without requiring manual updates.
    archive_db_pass=$(head -c 32 ../.operator/handover.key 2>/dev/null | sha256sum | head -c 48 || openssl rand -hex 24)
    # Seed archive.records table and archive_query role in corporate-db.
    "${compose[@]}" exec -T --user postgres corporate-db psql -U corporate -d planning \
        --no-psqlrc --set ON_ERROR_STOP=1 <<SQL
CREATE SCHEMA IF NOT EXISTS archive;
CREATE TABLE IF NOT EXISTS archive.records (
    record_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL,
    workflow TEXT,
    attachment TEXT,
    organizational_unit TEXT,
    classification TEXT NOT NULL
);
INSERT INTO archive.records (record_id, revision, workflow, attachment, organizational_unit, classification)
VALUES
    ('AR-MAINT-017', 2, 'AWF-CRR-229-R4', 'ARC-229-A', 'MaintenanceArchive', 'maintenance archive'),
    ('AR-CRR-229', 4, 'AWF-CRR-229-R4', 'ARC-229-A', 'CairnReachArchive', 'retained corporate archive')
ON CONFLICT (record_id) DO UPDATE SET
    revision = EXCLUDED.revision, workflow = EXCLUDED.workflow,
    attachment = EXCLUDED.attachment, organizational_unit = EXCLUDED.organizational_unit,
    classification = EXCLUDED.classification;
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'archive_query') THEN
        CREATE ROLE archive_query NOINHERIT;
    END IF;
END
\$\$;
ALTER ROLE archive_query LOGIN PASSWORD '${archive_db_pass}';
GRANT USAGE ON SCHEMA archive TO archive_query;
GRANT USAGE ON SCHEMA archive TO archive_query;
GRANT SELECT ON archive.records TO archive_query;
SQL
    # Write DB credentials for the archive container.
    # The golden ARWC compose reads from ../arwc/.operator/archive-workflow/.
    for opdir in .operator "${golden_op}"; do
        mkdir -p "${opdir}/archive-workflow"
        chmod 0755 "${opdir}/archive-workflow"
        printf '{"host":"corporate-db","database":"planning","user":"archive_query","password":"%s"}\n' \
            "${archive_db_pass}" > "${opdir}/archive-workflow/db-reader.json"
        chmod 0644 "${opdir}/archive-workflow/db-reader.json"
    done
    echo "PostgreSQL archive.records seeded"
    # Seed Nextcloud workflow and reader credentials.
    # Capture output so we can extract the Gitea reader state printed to stdout.
    seed_archive_out=$("${compose[@]}" --profile seed run --rm seed-archive 2>&1)
    echo "${seed_archive_out}"
    gitea_state_json=$(echo "${seed_archive_out}" | grep '^ARCHIVE_GITEA_STATE_JSON=' \
        | sed 's/^ARCHIVE_GITEA_STATE_JSON=//' | python3 -c 'import sys,json; print(json.loads(sys.stdin.read().strip()))' 2>/dev/null || true)
    if [ -n "${gitea_state_json}" ]; then
        mkdir -p "${golden_op}/archive-workflow"
        printf '%s\n' "${gitea_state_json}" > "${golden_op}/archive-workflow/gitea-reader.json"
        chmod 0644 "${golden_op}/archive-workflow/gitea-reader.json"
        echo "Wrote Gitea reader credentials to golden operator dir"
    fi
    # Seed the W12.1 retained-collectors Gitea repo from the host (operator dir is root-owned,
    # inaccessible from the seed container). Read the token from the already-written gitea-reader.json.
    gitea_reader_json="${golden_op}/archive-workflow/gitea-reader.json"
    if [ -f "${gitea_reader_json}" ]; then
        gitea_token=$(python3 -c "import json; print(json.load(open('${gitea_reader_json}')).get('token',''))" 2>/dev/null || true)
    else
        gitea_token=""
    fi
    collector_path=".operator/retained-tools/files/collection/collector-crr"
    if [ -n "${gitea_token}" ] && sudo test -f "${collector_path}" 2>/dev/null; then
        gitea_ip=$(sudo docker inspect cinder-arwc-native-gitea-1 --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null | head -1 || true)
        gitea_api="http://${gitea_ip:-localhost}:3000/api/v1"
        # Use admin basic auth for write operations (reader token is read-only).
        # shellcheck disable=SC1091
        source .operator/engineering-seed.env 2>/dev/null || true
        gitea_admin_auth="engineering-admin:${GITEA_ADMIN_PASSWORD:-}"
        tmpjson=$(mktemp /tmp/gitea-collector-XXXXXX.json)
        # Create retained-collectors repo if needed (admin auth required).
        curl -sf -X POST "${gitea_api}/org/arwc-archive/repos" \
            -u "${gitea_admin_auth}" \
            -H "Content-Type: application/json" \
            -d '{"name":"retained-collectors","private":true,"auto_init":true,"default_branch":"main"}' \
            -o /dev/null 2>/dev/null || true
        # Check existing file SHA (reader token is sufficient).
        existing_sha=$(curl -sf "${gitea_api}/repos/arwc-archive/retained-collectors/contents/collector-crr" \
            -H "Authorization: token ${gitea_token}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || true)
        sudo python3 - "${collector_path}" "${existing_sha}" "${tmpjson}" <<'PYEOF'
import base64, json, sys
path, sha, out = sys.argv[1:]
content = base64.b64encode(open(path, "rb").read()).decode()
body = {"message": "Add retained collector artifact", "content": content, "branch": "main"}
if sha:
    body["sha"] = sha
    body["message"] = "Update retained collector artifact"
json.dump(body, open(out, "w"))
PYEOF
        if [ -n "${existing_sha}" ]; then
            curl -sf -X PUT "${gitea_api}/repos/arwc-archive/retained-collectors/contents/collector-crr" \
                -u "${gitea_admin_auth}" \
                -H "Content-Type: application/json" \
                -d "@${tmpjson}" \
                -o /dev/null
            echo "W12.1: Updated collector-crr in Gitea arwc-archive/retained-collectors"
        else
            curl -sf -X POST "${gitea_api}/repos/arwc-archive/retained-collectors/contents/collector-crr" \
                -u "${gitea_admin_auth}" \
                -H "Content-Type: application/json" \
                -d "@${tmpjson}" \
                -o /dev/null
            echo "W12.1: Uploaded collector-crr to Gitea arwc-archive/retained-collectors"
        fi
        rm -f "${tmpjson}"
    else
        echo "W12.1: Skipping Gitea collector seed (token=${#gitea_token} chars, collector exists=$(sudo test -f "${collector_path}" 2>/dev/null && echo yes || echo no))"
    fi
    ;;
  seed-applications)
    # Start the cinder-arwc application stack (archive, contractors, approval, data, data-bridge).
    # Run after all seed steps: requires ERPNext, Nextcloud, Metabase, Gitea, and corporate-db to be seeded.
    # The main compose.yaml defines the cinder-arwc-corporate network; seed-applications creates it.
    app_compose=(docker compose --project-name cinder-arwc --env-file images.env -f ../compose.yaml)
    "${app_compose[@]}" up --no-build --pull never -d
    echo "cinder-arwc application stack started (archive, contractors, approval, data, data-bridge)"
    # Start the engineering workbench (a-engineering) for W19 diagnostic service.
    # Uses the CORPORATE session auth (no historian proxy needed).
    golden_op="$(cd .. && pwd)/.operator"
    docker volume create cinder-arwc-engineering-data 2>/dev/null || true
    docker network create --driver bridge --subnet 10.77.63.0/24 cinder-arwc-engineering 2>/dev/null || true
    docker stop cinder-arwc-engineering 2>/dev/null; docker rm cinder-arwc-engineering 2>/dev/null || true
    docker run -d \
      --name cinder-arwc-engineering \
      --network cinder-arwc-engineering --ip 10.77.63.40 \
      --hostname process-view --domainname arwc.test --dns 10.77.60.10 \
      -e ARWC_SERVICE_USER=arwc-engineering \
      -e ARWC_STATE_ROOT=/var/lib/arwc-engineering \
      -e ARWC_PROCESS_ROLE=engineering \
      --restart unless-stopped --read-only \
      --security-opt no-new-privileges:false \
      --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN \
      --cap-add FOWNER --cap-add DAC_OVERRIDE \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
      --tmpfs /run:rw,nosuid,nodev,size=8m,mode=0755 \
      -v cinder-arwc-engineering-data:/var/lib/arwc-engineering \
      -v cinder-arwc-connector-fieldlink:/run/arwc-corporate:ro \
      -v cinder-arwc-issuer-socket:/run/arwc:rw \
      -v "${golden_op}/handover.key:/run/arwc-handover/authentication.key:ro" \
      -v "${golden_op}/tls/server.crt:/run/arwc-tls/server.crt:ro" \
      -v "${golden_op}/tls/server.key:/run/arwc-tls/server.key:ro" \
      -v "${golden_op}/tls/ca.crt:/run/arwc-tls/ca.crt:ro" \
      "${PROCESS_IMAGE:-cinder-arwc/a-engineering:hand-build}"
    docker network connect --ip 10.77.60.55 --alias process-view.arwc.test \
      cinder-arwc-corporate cinder-arwc-engineering 2>/dev/null || true
    echo "a-engineering (process-view.arwc.test) started at 10.77.60.55"
    # Seed EVT-COMM-OG2-114 commissioning event into the OT historian so the participant
    # can discover it by querying alarm_history WHERE alarm_group = 'OG-CRR-02'.
    # This is the qualifying commissioning observation required for W19.4.
    docker exec arwc-ot-compat-postgres-1 psql -U historian -d historian -c "
INSERT INTO ot_history.alarm_events (name, type, ontime, offtime, acktime, acknowledging_user,
  text, alarm_group, value, native_status, origin, observed_at)
VALUES ('EVT-COMM-OG2-114', 'high', '2026-11-13 09:28:14+00', '2026-11-13 09:29:23+00',
  '2026-11-13 09:28:56+00', 'engineer',
  'Outlet group OG-CRR-02 commissioning observation 114: dual-outlet flow balance verified',
  'OG-CRR-02', '1', 'FA', 'OT qualifying campaign commissioning record',
  '2026-11-13 09:29:27+00') ON CONFLICT DO NOTHING;" 2>/dev/null || true
    echo "EVT-COMM-OG2-114 commissioning event seeded to OT historian (W19.4)"
    # Start the instruments workbench (a-instruments) for W20 instrument image service.
    # Uses the CORPORATE session auth (same as a-engineering).
    docker volume create cinder-arwc-instruments-data 2>/dev/null || true
    docker network create --driver bridge --subnet 10.77.64.0/24 cinder-arwc-control 2>/dev/null || true
    docker stop cinder-arwc-instruments 2>/dev/null; docker rm cinder-arwc-instruments 2>/dev/null || true
    docker run -d \
      --name cinder-arwc-instruments \
      --network cinder-arwc-control --ip 10.77.64.40 \
      --hostname independent-instruments --domainname arwc.test --dns 10.77.60.10 \
      -e ARWC_SERVICE_USER=arwc-instruments \
      -e ARWC_STATE_ROOT=/var/lib/arwc-instruments \
      -e ARWC_PROCESS_ROLE=instruments \
      --restart unless-stopped --read-only \
      --security-opt no-new-privileges:true \
      --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN \
      --cap-add FOWNER --cap-add DAC_OVERRIDE \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
      --tmpfs /run:rw,nosuid,nodev,size=8m,mode=0755 \
      -v cinder-arwc-instruments-data:/var/lib/arwc-instruments \
      -v cinder-arwc-connector-fieldlink:/run/arwc-corporate:ro \
      -v "${golden_op}/handover.key:/run/arwc-handover/authentication.key:ro" \
      -v "${golden_op}/tls/server.crt:/run/arwc-tls/server.crt:ro" \
      -v "${golden_op}/tls/server.key:/run/arwc-tls/server.key:ro" \
      -v "${golden_op}/tls/ca.crt:/run/arwc-tls/ca.crt:ro" \
      "${PROCESS_IMAGE:-cinder-arwc/a-instruments:hand-build}"
    docker network connect --ip 10.77.60.56 --alias independent-instruments.arwc.test \
      cinder-arwc-corporate cinder-arwc-instruments 2>/dev/null || true
    echo "a-instruments (independent-instruments.arwc.test) started at 10.77.60.56"
    # Start the diagnostics service (a-diagnostics) for W23+ estimator vulnerability chain.
    # Proxied by a-engineering (process-view.arwc.test) via X-ARWC-Internal: historian-r21.
    docker volume create cinder-arwc-diagnostics-data 2>/dev/null || true
    docker stop cinder-arwc-diagnostics 2>/dev/null; docker rm cinder-arwc-diagnostics 2>/dev/null || true
    docker run -d \
      --name cinder-arwc-diagnostics \
      --network cinder-arwc-engineering --ip 10.77.63.50 \
      --hostname diagnostic-services --domainname arwc.test --dns 10.77.60.10 \
      -e ARWC_SERVICE_USER=arwc-diagnostics \
      -e ARWC_STATE_ROOT=/var/lib/arwc-diagnostics \
      --restart unless-stopped --read-only \
      --security-opt no-new-privileges:true \
      --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN \
      --cap-add FOWNER --cap-add DAC_OVERRIDE \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
      --tmpfs /run:rw,nosuid,nodev,size=8m,mode=0755 \
      -v cinder-arwc-diagnostics-data:/var/lib/arwc-diagnostics \
      -v cinder-arwc-engineering-data:/run/arwc-engineering:ro \
      -v "${golden_op}/tls/server.crt:/run/arwc-tls/server.crt:ro" \
      -v "${golden_op}/tls/server.key:/run/arwc-tls/server.key:ro" \
      -v "${golden_op}/tls/ca.crt:/run/arwc-tls/ca.crt:ro" \
      "${DIAGNOSTIC_IMAGE:-cinder-arwc/a-diagnostics:hand-build}"
    docker network connect --ip 10.77.60.58 --alias diagnostic-services.arwc.test \
      cinder-arwc-corporate cinder-arwc-diagnostics 2>/dev/null || true
    echo "a-diagnostics (diagnostic-services at 10.77.63.50/10.77.60.58) started on cinder-arwc-engineering + cinder-arwc-corporate"
    # Start the maintenance renderer (a-renderer) for W26 renderer profile discovery.
    # Provides GET /api/renderers/current → RENDER-MAINT-CRR-R9 profile.
    # Reads approval from cinder-arwc-approval-evidence volume (populated by W15 flow).
    # Reads contractor session from cinder-arwc-field-session volume (populated by W13 flow).
    docker volume create cinder-arwc-renderer-state 2>/dev/null || true
    docker volume create cinder-arwc-renderer-evidence 2>/dev/null || true
    docker volume create cinder-arwc-approval-evidence 2>/dev/null || true
    docker volume create cinder-arwc-field-session 2>/dev/null || true
    # Seed approval-evidence from approval container (requires approval container to be running)
    docker run --rm \
      -v cinder-arwc-approval-data:/approval:ro \
      -v cinder-arwc-approval-evidence:/evidence:rw \
      --entrypoint sh "${RENDERER_IMAGE:-cinder-arwc/a-renderer:hand-build}" -c \
      'cp /approval/evidence/approval.json /evidence/approval.json && \
       chmod 0640 /evidence/approval.json && chown root:arwc-approval-evidence /evidence/approval.json' \
      2>/dev/null || true
    docker stop cinder-arwc-renderer 2>/dev/null; docker rm cinder-arwc-renderer 2>/dev/null || true
    docker run -d \
      --name cinder-arwc-renderer \
      --network cinder-arwc-corporate --ip 10.77.60.54 \
      --hostname maintenance-renderer --domainname arwc.test --dns 10.77.60.10 \
      -e ARWC_SERVICE_USER=arwc-renderer \
      -e ARWC_STATE_ROOT=/var/lib/arwc-renderer \
      --restart unless-stopped --read-only \
      --security-opt no-new-privileges:true \
      --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN \
      --cap-add FOWNER --cap-add DAC_OVERRIDE \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
      --tmpfs /run:rw,nosuid,nodev,size=8m,mode=0755 \
      -v cinder-arwc-renderer-state:/var/lib/arwc-renderer \
      -v cinder-arwc-approval-evidence:/run/arwc-approval-evidence:ro \
      -v cinder-arwc-field-session:/run/arwc-field-session:ro \
      -v cinder-arwc-renderer-evidence:/run/arwc-renderer-evidence:rw \
      -v "${golden_op}/tls/server.crt:/run/arwc-tls/server.crt:ro" \
      -v "${golden_op}/tls/server.key:/run/arwc-tls/server.key:ro" \
      -v "${golden_op}/tls/ca.crt:/run/arwc-tls/ca.crt:ro" \
      "${RENDERER_IMAGE:-cinder-arwc/a-renderer:hand-build}"
    echo "a-renderer (maintenance-renderer at 10.77.60.54) started"
    # Start the control broker (a-control-broker) for W26.4 control client issuance.
    # POST /api/approval-clients/current → CTRL-CLIENT-CRR-26 (W26.CONTROL).
    # Reads: contractor session (W13), approval evidence (W15), renderer attestation (W26.3).
    # NOTE: The renderer mounts cinder-arwc-renderer-evidence rw so W26.3 writes the attestation
    # directly there. The control-broker reads from the same volume (ro). No copy step needed.
    docker volume create cinder-arwc-control-broker-state 2>/dev/null || true
    docker volume create cinder-arwc-issuer-socket 2>/dev/null || true
    docker stop cinder-arwc-control-broker 2>/dev/null; docker rm cinder-arwc-control-broker 2>/dev/null || true
    docker run -d \
      --name cinder-arwc-control-broker \
      --network cinder-arwc-corporate --ip 10.77.60.57 \
      --hostname control-broker --domainname arwc.test --dns 10.77.60.10 \
      -e ARWC_SERVICE_USER=arwc-control-broker \
      -e ARWC_STATE_ROOT=/var/lib/arwc-control-broker \
      --restart unless-stopped --read-only \
      --security-opt no-new-privileges:true \
      --cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add CHOWN \
      --cap-add FOWNER --cap-add DAC_OVERRIDE \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777 \
      --tmpfs /run:rw,nosuid,nodev,size=8m,mode=0755 \
      -v cinder-arwc-issuer-socket:/run/arwc:rw \
      -v cinder-arwc-control-broker-state:/var/lib/arwc-control-broker \
      -v cinder-arwc-approval-evidence:/run/arwc-approval-evidence:ro \
      -v cinder-arwc-field-session:/run/arwc-field-session:ro \
      -v cinder-arwc-renderer-evidence:/run/arwc-renderer-evidence:ro \
      -v "${golden_op}/tls/server.crt:/run/arwc-tls/server.crt:ro" \
      -v "${golden_op}/tls/server.key:/run/arwc-tls/server.key:ro" \
      -v "${golden_op}/tls/ca.crt:/run/arwc-tls/ca.crt:ro" \
      "${CONTROL_BROKER_IMAGE:-cinder-arwc/a-control-broker:hand-build}"
    echo "a-control-broker (control-broker.arwc.test at 10.77.60.57) started"
    ;;
  reset)
    [[ ${2-} == cinder-arwc-native ]] || {
      echo 'Reset requires the exact project name: reset cinder-arwc-native' >&2
      exit 2
    }
    # Stop and remove the application stack (cinder-arwc project) before resetting the native stack.
    docker compose --project-name cinder-arwc --env-file images.env -f ../compose.yaml down --volumes 2>/dev/null || true
    "${compose[@]}" down --volumes
    bash "$0" up
    bash "$0" seed
    bash "$0" seed-dmz
    bash "$0" seed-documents
    bash "$0" seed-reports
    bash "$0" seed-portal
    bash "$0" seed-early-cards
    bash "$0" seed-identity
    bash "$0" seed-engineering
    bash "$0" seed-archive
    bash "$0" seed-corporate-documents
    exec bash "$0" seed-applications
    ;;
  *) echo 'Usage: manage.sh build|up|status|seed|seed-documents|seed-corporate-documents|seed-reports|seed-engineering|seed-dmz|seed-portal|seed-early-cards|seed-identity|seed-archive|seed-applications|reset cinder-arwc-native' >&2; exit 2 ;;
esac
