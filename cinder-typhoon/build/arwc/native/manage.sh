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
    ;;
  reset)
    [[ ${2-} == cinder-arwc-native ]] || {
      echo 'Reset requires the exact project name: reset cinder-arwc-native' >&2
      exit 2
    }
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
    exec bash "$0" seed-corporate-documents
    ;;
  *) echo 'Usage: manage.sh build|up|status|seed|seed-documents|seed-corporate-documents|seed-reports|seed-engineering|seed-dmz|seed-portal|seed-early-cards|seed-identity|seed-archive|reset cinder-arwc-native' >&2; exit 2 ;;
esac
