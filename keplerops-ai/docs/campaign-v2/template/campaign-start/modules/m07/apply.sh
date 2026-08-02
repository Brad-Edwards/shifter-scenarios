#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m07"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_ADMIN_TOKEN=31a5a4b4ab3cdbaf110644eed06853b2b418daf6
readonly TRAINER_TOKEN=KAI-Orion-Trainer-2b68d419a7f340ce
readonly TRAINER_EMAIL=orion.contributor@keplerops.lab
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_ADMIN_AUTH="${FORGEJO_ADMIN_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly CINDER_FORGEJO_API_URL="${CINDER_FORGEJO_API_URL:-http://10.61.90.30:3000/api/v1}"
readonly CINDER_FORGEJO_ADMIN_AUTH="${CINDER_FORGEJO_ADMIN_AUTH:-cinder-operator:Cinder-Operations-Git-K3m7Pq4x}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly HARBOR_ADMIN_AUTH="${HARBOR_ADMIN_AUTH:-admin:KeplerV2-Training-Harbor}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_AUTH="${MLFLOW_AUTH:-svc-orion-training:KeplerV2-Training-MLflow-Service}"

log() { printf '[orion integrity setup] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

forgejo() {
  local method=$1 path=$2
  shift 2
  curl -fsS --user "${FORGEJO_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

cinder_forgejo() {
  local method=$1 path=$2
  shift 2
  curl -fsS --user "${CINDER_FORGEJO_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X "${method}" "$@" "${CINDER_FORGEJO_API_URL}${path}"
}

ensure_forgejo_user() {
  local username=$1 password=$2 email=$3
  if ! forgejo GET "/users/${username}" >/dev/null 2>&1; then
    forgejo POST /admin/users --data "$(jq -cn \
      --arg username "${username}" --arg password "${password}" --arg email "${email}" \
      '{username:$username,password:$password,email:$email,must_change_password:false,restricted:false,visibility:"private"}')" >/dev/null
  else
    forgejo PATCH "/admin/users/${username}" --data "$(jq -cn --arg password "${password}" '{password:$password,must_change_password:false,active:true}')" >/dev/null
  fi
}

ensure_forgejo_org() {
  local owner=$1 title=$2
  forgejo GET "/orgs/${owner}" >/dev/null 2>&1 || \
    forgejo POST /orgs --data "$(jq -cn --arg username "${owner}" --arg full_name "${title}" \
      '{username:$username,full_name:$full_name,visibility:"private"}')" >/dev/null
}

ensure_forgejo_repo() {
  local owner=$1 repo=$2 description=$3 private=$4
  forgejo GET "/repos/${owner}/${repo}" >/dev/null 2>&1 || \
    forgejo POST "/orgs/${owner}/repos" --data "$(jq -cn \
      --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
      '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
}

grant_repo() {
  local owner=$1 repo=$2 username=$3 permission=${4:-write}
  forgejo PUT "/repos/${owner}/${repo}/collaborators/${username}" \
    --data "$(jq -cn --arg permission "${permission}" '{permission:$permission}')" >/dev/null
}

ensure_cinder_user() {
  local username=$1 password=$2 email=$3
  if ! cinder_forgejo GET "/users/${username}" >/dev/null 2>&1; then
    cinder_forgejo POST /admin/users --data "$(jq -cn \
      --arg username "${username}" --arg password "${password}" --arg email "${email}" \
      '{username:$username,password:$password,email:$email,must_change_password:false,restricted:false,visibility:"private"}')" >/dev/null
  fi
}

ensure_cinder_org() {
  local owner=$1 title=$2
  cinder_forgejo GET "/orgs/${owner}" >/dev/null 2>&1 || \
    cinder_forgejo POST /orgs --data "$(jq -cn --arg username "${owner}" --arg full_name "${title}" \
      '{username:$username,full_name:$full_name,visibility:"private"}')" >/dev/null
}

ensure_cinder_repo() {
  local owner=$1 repo=$2 description=$3 private=$4
  cinder_forgejo GET "/repos/${owner}/${repo}" >/dev/null 2>&1 || \
    cinder_forgejo POST "/orgs/${owner}/repos" --data "$(jq -cn \
      --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
      '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
}

ensure_cinder_operator_repo() {
  local repo=$1 description=$2 private=$3
  cinder_forgejo GET "/repos/cinder-operator/${repo}" >/dev/null 2>&1 || \
    cinder_forgejo POST /user/repos --data "$(jq -cn \
      --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
      '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
}

grant_cinder_repo() {
  local owner=$1 repo=$2 username=$3 permission=${4:-write}
  cinder_forgejo PUT "/repos/${owner}/${repo}/collaborators/${username}" \
    --data "$(jq -cn --arg permission "${permission}" '{permission:$permission}')" >/dev/null
}

upsert_file() {
  local owner=$1 repo=$2 path=$3 message=$4 source=$5 existing sha payload existing_digest source_digest method=POST
  existing="$(forgejo GET "/repos/${owner}/${repo}/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${existing}")"
  if [[ -n ${sha} ]]; then
    method=PUT
    existing_digest="$(jq -r '.content' <<<"${existing}" | tr -d '\n' | base64 -d | sha256sum | awk '{print $1}')"
    source_digest="$(sha256sum "${source}" | awk '{print $1}')"
    [[ ${existing_digest} != "${source_digest}" ]] || return 0
  fi
  payload="$(base64 -w0 "${source}" | jq -Rs \
    --arg message "${message}" --arg sha "${sha}" \
    '{content:.,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
  forgejo "${method}" "/repos/${owner}/${repo}/contents/${path}" --data "${payload}" >/dev/null
}

upsert_cinder_file() {
  local owner=$1 repo=$2 path=$3 message=$4 source=$5 existing sha payload existing_digest source_digest method=POST
  existing="$(cinder_forgejo GET "/repos/${owner}/${repo}/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${existing}")"
  if [[ -n ${sha} ]]; then
    method=PUT
    existing_digest="$(jq -r '.content' <<<"${existing}" | tr -d '\n' | base64 -d | sha256sum | awk '{print $1}')"
    source_digest="$(sha256sum "${source}" | awk '{print $1}')"
    [[ ${existing_digest} != "${source_digest}" ]] || return 0
  fi
  payload="$(base64 -w0 "${source}" | jq -Rs --arg message "${message}" --arg sha "${sha}" \
    '{content:.,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
  cinder_forgejo "${method}" "/repos/${owner}/${repo}/contents/${path}" --data "${payload}" >/dev/null
}

capture_clean_state() {
  [[ -s ${STATE_ROOT}/baseline-export.json && -s ${STATE_ROOT}/baseline-export-sha256 &&
     -s ${STATE_ROOT}/baseline-labels.json && -s ${STATE_ROOT}/upstream-clean.json ]] && return 0
  docker exec -i kep-v2-postgres psql --set ON_ERROR_STOP=1 \
    --username kepler --dbname labelstudio >/dev/null <<SQL
UPDATE authtoken_token SET key = '${LABEL_STUDIO_ADMIN_TOKEN}'
WHERE user_id = (SELECT id FROM htx_user WHERE email = 'annotation.admin@keplerops.lab');
SQL
  "${TEMPLATE_ROOT}/engineering/reconcile-release-risk-labels.sh" >/dev/null
  local exported
  exported="$(curl -fsS -H "Authorization: Token ${LABEL_STUDIO_ADMIN_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects?page_size=100" | jq -er \
    '.results[] | select(.title == "Orion Release Risk Training Baseline") | .id' | head -n1)"
  curl -fsS -H "Authorization: Token ${LABEL_STUDIO_ADMIN_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects/${exported}/export?exportType=JSON" \
    >"${STATE_ROOT}/baseline-export.json"
  jq 'map({key:.data.record_id,value:{text:.data.text,label:.annotations[-1].result[0].value.choices[0]}}) | from_entries' \
    "${STATE_ROOT}/baseline-export.json" >"${STATE_ROOT}/baseline-labels.json"
  python3 - "${STATE_ROOT}/baseline-export.json" >"${STATE_ROOT}/baseline-export-sha256" <<'PY'
import hashlib
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    exported = json.load(source)
print(hashlib.sha256(json.dumps(exported, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
PY
  jq '[to_entries[] | {record_id:.key,text:.value.text,label:.value.label}]' \
    "${STATE_ROOT}/baseline-labels.json" >"${STATE_ROOT}/upstream-clean.json"
  chmod 0640 "${STATE_ROOT}/baseline-export.json" "${STATE_ROOT}/baseline-export-sha256" \
    "${STATE_ROOT}/baseline-labels.json" "${STATE_ROOT}/upstream-clean.json"
}

reconcile_trainer_access() {
  docker exec -i kep-v2-postgres psql --set ON_ERROR_STOP=1 \
    --username kepler --dbname labelstudio >/dev/null <<SQL
DO \$\$
DECLARE columns_sql text; values_sql text; contributor_id bigint; admin_id bigint;
        source_org_id bigint; contributor_org_id bigint; target_project_id bigint;
BEGIN
  SELECT id INTO admin_id FROM htx_user WHERE email = 'annotation.admin@keplerops.lab';
  IF admin_id IS NULL THEN RAISE EXCEPTION 'Label Studio bootstrap administrator is absent'; END IF;
  IF NOT EXISTS (SELECT 1 FROM htx_user WHERE email = '${TRAINER_EMAIL}') THEN
    SELECT string_agg(quote_ident(column_name), ',' ORDER BY ordinal_position),
           string_agg(CASE column_name
             WHEN 'email' THEN quote_literal('${TRAINER_EMAIL}')
             WHEN 'username' THEN quote_literal('${TRAINER_EMAIL}')
             WHEN 'first_name' THEN quote_literal('Orion')
             WHEN 'last_name' THEN quote_literal('Contributor')
             WHEN 'is_active' THEN 'true'
             WHEN 'is_superuser' THEN 'false'
             WHEN 'is_staff' THEN 'false'
             WHEN 'password' THEN quote_literal('!')
             ELSE quote_ident(column_name) END, ',' ORDER BY ordinal_position)
      INTO columns_sql, values_sql
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'htx_user' AND column_name <> 'id';
    EXECUTE format('INSERT INTO htx_user (%s) SELECT %s FROM htx_user WHERE id = %s',
                   columns_sql, values_sql, admin_id);
  END IF;
  SELECT id INTO contributor_id FROM htx_user WHERE email = '${TRAINER_EMAIL}';
  UPDATE htx_user SET is_active = true, is_superuser = false, is_staff = false, password = '!'
    WHERE id = contributor_id;
  IF to_regclass('public.organizations_organizationmember') IS NULL
     OR to_regclass('public.organization') IS NULL
     OR to_regclass('public.project') IS NULL THEN
    RAISE EXCEPTION 'Label Studio organization boundary tables are unavailable';
  END IF;
  SELECT id, organization_id INTO target_project_id, source_org_id
    FROM project WHERE title = 'Orion Release Risk Training Baseline' ORDER BY id LIMIT 1;
  IF target_project_id IS NULL OR source_org_id IS NULL THEN
    RAISE EXCEPTION 'Orion release-risk project or source organization is absent';
  END IF;
  SELECT id INTO contributor_org_id FROM organization
    WHERE title = 'Orion Release Risk Contributors' ORDER BY id LIMIT 1;
  IF contributor_org_id IS NULL THEN
    SELECT string_agg(quote_ident(column_name), ',' ORDER BY ordinal_position),
           string_agg(CASE column_name
             WHEN 'title' THEN quote_literal('Orion Release Risk Contributors')
             WHEN 'token' THEN quote_literal(md5('orion-release-risk-contributors'))
             WHEN 'created_by_id' THEN contributor_id::text
             ELSE quote_ident(column_name) END, ',' ORDER BY ordinal_position)
      INTO columns_sql, values_sql
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'organization'
        AND column_name <> 'id';
    EXECUTE format('INSERT INTO organization (%s) SELECT %s FROM organization WHERE id = %s RETURNING id',
                   columns_sql, values_sql, source_org_id) INTO contributor_org_id;
  END IF;
  UPDATE project SET organization_id = contributor_org_id WHERE id = target_project_id;
  UPDATE htx_user SET active_organization_id = contributor_org_id WHERE id = contributor_id;
  DELETE FROM organizations_organizationmember
    WHERE user_id = contributor_id AND organization_id <> contributor_org_id;
  IF NOT EXISTS (SELECT 1 FROM organizations_organizationmember
                 WHERE user_id = contributor_id AND organization_id = contributor_org_id) THEN
    SELECT string_agg(quote_ident(column_name), ',' ORDER BY ordinal_position),
           string_agg(CASE column_name WHEN 'user_id' THEN contributor_id::text
             WHEN 'organization_id' THEN contributor_org_id::text
             ELSE quote_ident(column_name) END, ',' ORDER BY ordinal_position)
      INTO columns_sql, values_sql
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'organizations_organizationmember'
        AND column_name <> 'id';
    EXECUTE format('INSERT INTO organizations_organizationmember (%s) SELECT %s FROM organizations_organizationmember WHERE user_id = %s AND organization_id = %s LIMIT 1',
                   columns_sql, values_sql, admin_id, source_org_id);
  END IF;
  INSERT INTO authtoken_token(key, created, user_id)
    VALUES ('${TRAINER_TOKEN}', now(), contributor_id)
    ON CONFLICT (user_id) DO UPDATE SET key = EXCLUDED.key;
  IF EXISTS (SELECT 1 FROM authtoken_token WHERE key = '${TRAINER_TOKEN}' AND user_id = admin_id) THEN
    RAISE EXCEPTION 'bounded contributor token remains attached to the administrator';
  END IF;
END \$\$;
SQL
  local projects target_id denied_id denied_status
  projects="$(curl -fsS -H "Authorization: Token ${TRAINER_TOKEN}" "${LABEL_STUDIO_URL}/api/projects?page_size=100")"
  [[ $(jq '[.results[] | select(.title == "Orion Release Risk Training Baseline")] | length' <<<"${projects}") -eq 1 ]] ||
    die 'bounded contributor cannot see exactly the assigned Orion project'
  [[ $(jq '.results | length' <<<"${projects}") -eq 1 ]] ||
    die 'bounded contributor can enumerate Label Studio projects outside its assignment'
  target_id="$(jq -er '.results[0].id' <<<"${projects}")"
  denied_id="$(curl -fsS -H "Authorization: Token ${LABEL_STUDIO_ADMIN_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects?page_size=100" | jq -er --argjson target "${target_id}" \
    '.results[] | select(.id != $target) | .id' | head -n1)" ||
    die 'a same-service Label Studio denied control project is unavailable'
  denied_status="$(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Token ${TRAINER_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects/${denied_id}")"
  [[ ${denied_status} == 403 || ${denied_status} == 404 ]] ||
    die "bounded contributor unexpectedly reached denied Label Studio project ${denied_id}"
  printf '%s\n' "${denied_id}" >"${STATE_ROOT}/label-studio-denied-project-id"
  chmod 0640 "${STATE_ROOT}/label-studio-denied-project-id"
}

seed_repositories() {
  ensure_forgejo_user svc-orion-training "${TRAINER_TOKEN}" svc-orion-training@keplerops.lab
  grant_repo keplerops orion-build svc-orion-training read
  ensure_forgejo_user upstream.maintainer Cinder-Upstream-Maintainer-2026 upstream.maintainer@orion-upstream.lab
  ensure_cinder_user cinder.publisher Cinder-Dataset-Publisher-2026 cinder.publisher@cinder.lab
  ensure_forgejo_org orion-upstream 'Orion Upstream Data Cooperative'
  ensure_cinder_org cinder-labs 'Cinder Research'
  ensure_forgejo_repo keplerops orion-model-integrity 'Orion model data, evaluation, and graph sources.' true
  ensure_forgejo_repo orion-upstream release-risk-corpus 'Versioned upstream Orion-compatible release-risk corpus.' false
  ensure_cinder_repo cinder-labs orion-poisoned-dataset 'Cinder dataset and isolated model-artifact publications.' false
  ensure_cinder_operator_repo orion-model-artifacts 'Cinder isolated Orion artifact execution and accepted releases.' true
  grant_repo keplerops orion-model-integrity svc-orion-training write
  grant_repo orion-upstream release-risk-corpus upstream.maintainer admin
  grant_cinder_repo cinder-labs orion-poisoned-dataset cinder.publisher admin
  grant_cinder_repo cinder-labs orion-poisoned-dataset cinder-field-operator admin
  grant_cinder_repo cinder-operator orion-model-artifacts cinder.publisher read
  grant_cinder_repo cinder-operator orion-model-artifacts cinder-field-operator read

  local seed="${STATE_ROOT}/seed"
  install -d -m 0750 "${seed}/integrity/evaluation" "${seed}/integrity/model" "${seed}/upstream" "${seed}/cinder/.forgejo/workflows"
  jq '.[0:16]' "${STATE_ROOT}/upstream-clean.json" >"${seed}/integrity/evaluation/holdout.clean.json"
  cp "${seed}/integrity/evaluation/holdout.clean.json" "${seed}/integrity/evaluation/holdout.json"
  cp "${seed}/integrity/evaluation/holdout.clean.json" "${STATE_ROOT}/holdout-clean.json"
  chmod 0640 "${STATE_ROOT}/holdout-clean.json"
  cp "${STATE_ROOT}/upstream-clean.json" "${seed}/upstream/dataset.json"
  cp "${STATE_ROOT}/upstream-clean.json" "${seed}/cinder/dataset.json"
  sha256sum "${seed}/upstream/dataset.json" | sed 's# .*/#  #' >"${seed}/upstream/checksums.sha256"
  sha256sum "${seed}/cinder/dataset.json" | sed 's# .*/#  #' >"${seed}/cinder/checksums.sha256"
  cp "${MODULE_ROOT}/payloads/upstream/README.md" "${seed}/upstream/README.md"
  cp "${MODULE_ROOT}/payloads/integrity/README.md" "${seed}/integrity/README.md"
  cp "${MODULE_ROOT}/payloads/integrity/graph_mutation.py" "${seed}/integrity/model/graph_mutation.py"
  cp "${MODULE_ROOT}/payloads/integrity/backdoor-plan.example.json" "${seed}/integrity/model/backdoor-plan.example.json"
  cp "${MODULE_ROOT}/payloads/integrity/graph-behavior-plan.example.json" "${seed}/integrity/model/graph-behavior-plan.example.json"
  cp "${MODULE_ROOT}/payloads/cinder/README.md" "${seed}/cinder/README.md"
  cp "${MODULE_ROOT}/payloads/cinder/loader.py" "${seed}/cinder/loader.py"
  cp "${MODULE_ROOT}/payloads/cinder/build_unsafe_model.py" "${seed}/cinder/build_unsafe_model.py"
  cp "${MODULE_ROOT}/payloads/cinder/verifier.py" "${seed}/cinder/verifier.py"
  cp "${MODULE_ROOT}/payloads/cinder/publish_report.py" "${seed}/cinder/publish_report.py"
  cp "${MODULE_ROOT}/payloads/cinder/publish_release.py" "${seed}/cinder/publish_release.py"
  cp "${MODULE_ROOT}/payloads/cinder/sandbox_builder.py" "${seed}/cinder/sandbox_builder.py"
  cp "${MODULE_ROOT}/payloads/cinder/review-request.example.json" "${seed}/cinder/review-request.example.json"
  cp "${MODULE_ROOT}/payloads/cinder/release-risk-integrity-heldout.json" \
    "${seed}/cinder/release-risk-integrity-heldout.json"
  cp "${MODULE_ROOT}/payloads/cinder/verify-embedded-model.yml" \
    "${seed}/cinder/.forgejo/workflows/verify-embedded-model.yml"

  local file
  for file in README.md evaluation/holdout.clean.json evaluation/holdout.json model/graph_mutation.py \
    model/backdoor-plan.example.json model/graph-behavior-plan.example.json; do
    upsert_file keplerops orion-model-integrity "${file}" "Seed Orion model-integrity source" "${seed}/integrity/${file}"
  done
  for file in README.md dataset.json checksums.sha256; do
    upsert_file orion-upstream release-risk-corpus "${file}" "Seed trusted upstream corpus" "${seed}/upstream/${file}"
  done
  for file in README.md dataset.json checksums.sha256 loader.py build_unsafe_model.py review-request.example.json; do
    upsert_cinder_file cinder-labs orion-poisoned-dataset "${file}" "Seed Cinder publication workspace" "${seed}/cinder/${file}"
  done
  upsert_cinder_file cinder-operator orion-model-artifacts verifier.py 'Seed isolated artifact verifier' "${seed}/cinder/verifier.py"
  upsert_cinder_file cinder-operator orion-model-artifacts publish_report.py 'Seed immutable artifact handoff publisher' "${seed}/cinder/publish_report.py"
  upsert_cinder_file cinder-operator orion-model-artifacts publish_release.py 'Seed accepted artifact release publisher' "${seed}/cinder/publish_release.py"
  upsert_cinder_file cinder-operator orion-model-artifacts sandbox_builder.py 'Seed bounded submission builder' "${seed}/cinder/sandbox_builder.py"
  upsert_cinder_file cinder-operator orion-model-artifacts release-risk-integrity-heldout.json \
    'Record server-held evaluation suite commitment' "${seed}/cinder/release-risk-integrity-heldout.json"
  upsert_cinder_file cinder-operator orion-model-artifacts .forgejo/workflows/verify-embedded-model.yml \
    'Seed isolated artifact review workflow' "${seed}/cinder/.forgejo/workflows/verify-embedded-model.yml"
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/CINDER_ATTESTATION_KEY \
    --data '{"data":"Cinder-Isolated-Execution-2026"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/ORION_PROVENANCE_KEY \
    --data '{"data":"KeplerOps-Orion-Provenance-2026"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/ARTIFACT_REVIEW_REFERENCE \
    --data '{"data":"FLAG{7089e273d0b9e97f}"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/CINDER_OBJECT_ACCESS_KEY \
    --data '{"data":"cinder-operator"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/CINDER_OBJECT_SECRET_KEY \
    --data '{"data":"Cinder-Operations-ObjectStore-T7v2Lm9q"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/ARTIFACT_RELEASE_USER \
    --data '{"data":"cinder-operator"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/ARTIFACT_RELEASE_PASSWORD \
    --data '{"data":"Cinder-Operations-Git-K3m7Pq4x"}' >/dev/null
  cinder_forgejo PUT /repos/cinder-operator/orion-model-artifacts/actions/secrets/CINDER_HELDOUT_CASES_B64 \
    --data "$(jq -cn --arg data "$(base64 -w0 "${TEMPLATE_ROOT}/engineering/release-risk/integrity-heldout.json")" '{data:$data}')" >/dev/null
  touch "${STATE_ROOT}/repositories-seeded"
}

reconcile_harbor() {
  local project robots robot_id
  project='{"project_name":"cinder-datasets","public":true,"metadata":{"auto_scan":"false"}}'
  curl -fsS --user "${HARBOR_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X POST --data "${project}" "${HARBOR_API_URL}/projects" >/dev/null 2>&1 || true
  robots="$(curl -fsS --user "${HARBOR_ADMIN_AUTH}" "${HARBOR_API_URL}/robots?page=1&page_size=100")"
  robot_id="$(jq -r '.[] | select(.name == "robot$cinder-datasets+cinder-publisher") | .id' <<<"${robots}" | head -n1)"
  if [[ -n ${robot_id} ]]; then
    curl -fsS --user "${HARBOR_ADMIN_AUTH}" -X DELETE "${HARBOR_API_URL}/robots/${robot_id}" >/dev/null
  fi
  curl -fsS --user "${HARBOR_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X POST --data '{"name":"cinder-publisher","description":"Bounded Cinder dataset publisher","disable":false,"duration":-1,"level":"project","secret":"Cinder-Dataset-Publisher-2026","permissions":[{"kind":"project","namespace":"cinder-datasets","access":[{"resource":"repository","action":"pull"},{"resource":"repository","action":"push"}]}]}' \
    "${HARBOR_API_URL}/robots" >/dev/null
}

clean_training_exists() {
  local experiments experiment_id runs baseline_sha
  baseline_sha="$(<"${STATE_ROOT}/baseline-export-sha256")"
  experiments="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data '{"max_results":100}' "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
  experiment_id="$(jq -r '.experiments[]? | select(.name == "Orion Release Risk Training") | .experiment_id' <<<"${experiments}" | head -n1)"
  [[ -n ${experiment_id} ]] || return 1
  runs="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg id "${experiment_id}" '{experiment_ids:[$id],max_results:1000}')" \
    "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
  jq -e --arg sha "${baseline_sha}" 'any(.runs[]?;
    .info.status == "FINISHED" and
    any(.data.tags[]?; .key == "source.export_sha256" and .value == $sha) and
    any(.data.tags[]?; .key == "model.family" and .value == "release-risk") and
    any(.data.tags[]?; .key == "source.repository" and .value == "keplerops/orion-build") and
    any(.data.tags[]?; .key == "source.commit" and (.value | test("^[0-9a-f]{40}$"))) and
    any(.data.tags[]?; .key == "source.tree_sha256" and (.value | test("^[0-9a-f]{64}$"))) and
    any(.data.tags[]?; .key == "data.lakefs_commit" and (.value | length > 0)) and
    any(.data.tags[]?; .key == "data.dvc_md5" and (.value | test("^[0-9a-f]{32}$"))) and
    any(.data.tags[]?; .key == "model.onnx_sha256" and (.value | test("^[0-9a-f]{64}$"))) and
    any(.data.tags[]?; .key == "model.package_schema_sha256" and (.value | test("^[0-9a-f]{64}$"))) and
    any(.data.tags[]?; .key == "provenance.signature" and (.value | test("^[0-9a-f]{64}$"))))' \
    <<<"${runs}" >/dev/null
}

capture_clean_training_reference() {
  local experiments experiment_id runs baseline_sha run run_id versions model_version
  baseline_sha="$(<"${STATE_ROOT}/baseline-export-sha256")"
  experiments="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data '{"max_results":100}' "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
  experiment_id="$(jq -er '.experiments[]? | select(.name == "Orion Release Risk Training") | .experiment_id' \
    <<<"${experiments}" | head -n1)"
  runs="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg id "${experiment_id}" '{experiment_ids:[$id],max_results:1000}')" \
    "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
  run="$(jq -ec --arg sha "${baseline_sha}" '
    [.runs[]? | select(
      .info.status == "FINISHED" and
      any(.data.tags[]?; .key == "model.family" and .value == "release-risk") and
      any(.data.tags[]?; .key == "source.export_sha256" and .value == $sha) and
      any(.data.tags[]?; .key == "source.repository" and .value == "keplerops/orion-build") and
      any(.data.tags[]?; .key == "source.commit" and (.value | test("^[0-9a-f]{40}$"))) and
      any(.data.tags[]?; .key == "source.tree_sha256" and (.value | test("^[0-9a-f]{64}$"))) and
      any(.data.tags[]?; .key == "data.dvc_md5" and (.value | test("^[0-9a-f]{32}$"))) and
      any(.data.tags[]?; .key == "model.onnx_sha256" and (.value | test("^[0-9a-f]{64}$"))) and
      any(.data.tags[]?; .key == "model.package_schema_sha256" and (.value | test("^[0-9a-f]{64}$"))))]
    | sort_by(.info.start_time | tonumber) | last' <<<"${runs}")"
  run_id="$(jq -er '.info.run_id' <<<"${run}")"
  versions="$(curl -fsS --get --user "${MLFLOW_AUTH}" \
    --data-urlencode "filter=name='Orion Release Risk'" --data-urlencode 'max_results=1000' \
    "${MLFLOW_URL}/api/2.0/mlflow/model-versions/search")"
  model_version="$(jq -er --arg run_id "${run_id}" \
    '[.model_versions[]? | select(.run_id == $run_id)] | sort_by(.version | tonumber) | last | .version' \
    <<<"${versions}")"
  jq -e --arg version "${model_version}" '
    def tag($key): [.data.tags[]? | select(.key == $key)][0].value;
    {schema:"keplerops.orion.clean-training-reference/v1", model_family:"release-risk",
     registered_model_name:"Orion Release Risk", mlflow_model_version:$version,
     mlflow_run_id:.info.run_id, source_repository:tag("source.repository"),
     source_commit:tag("source.commit"), source_tree_sha256:tag("source.tree_sha256"),
     source_export_sha256:tag("source.export_sha256"),
     training_lakefs_commit:tag("data.lakefs_commit"), dvc_md5:tag("data.dvc_md5"),
     airflow_dag_run_id:tag("training.dag_run_id"), model_sha256:tag("model.onnx_sha256"),
     native_weights_sha256:tag("model.native_weights_sha256"),
     tokenizer_sha256:tag("model.tokenizer_sha256"),
     label_schema_sha256:tag("model.label_schema_sha256"),
     preprocessing_sha256:tag("model.preprocessing_sha256"),
     package_schema_sha256:tag("model.package_schema_sha256"),
     provenance_signature:tag("provenance.signature")}' <<<"${run}" \
    >"${STATE_ROOT}/clean-training-reference.json"
  jq -e '
    .schema == "keplerops.orion.clean-training-reference/v1" and
    (.mlflow_run_id | test("^[0-9a-f]{32}$")) and
    (.mlflow_model_version | test("^[0-9]+$")) and
    (.source_commit | test("^[0-9a-f]{40}$")) and
    (.source_tree_sha256 | test("^[0-9a-f]{64}$")) and
    (.source_export_sha256 | test("^[0-9a-f]{64}$")) and
    (.dvc_md5 | test("^[0-9a-f]{32}$")) and
    (.model_sha256 | test("^[0-9a-f]{64}$")) and
    (.package_schema_sha256 | test("^[0-9a-f]{64}$"))' \
    "${STATE_ROOT}/clean-training-reference.json" >/dev/null || \
    die 'clean training reference lacks exact promotion identifiers'
  chmod 0640 "${STATE_ROOT}/clean-training-reference.json"
}

ensure_clean_training_reference() {
  if clean_training_exists; then capture_clean_training_reference; return 0; fi
  local run_id state
  run_id="orion-clean-reference-$(cut -c1-12 "${STATE_ROOT}/baseline-export-sha256")-$(date +%s)"
  docker exec kep-v2-airflow-api airflow dags trigger orion_release_risk_training --run-id "${run_id}" >/dev/null
  for _ in $(seq 1 360); do
    state="$(docker exec kep-v2-airflow-api airflow dags list-runs \
      --dag-id orion_release_risk_training --output json 2>/dev/null |
      jq -r --arg run "${run_id}" '.[] | select((.run_id // .dag_run_id) == $run) | .state' | head -n1)"
    case "${state,,}" in
      success)
        clean_training_exists || die 'clean reference run lacks matching MLflow lineage'
        capture_clean_training_reference
        return 0
        ;;
      failed) die 'clean reference training run failed' ;;
    esac
    sleep 5
  done
  die 'clean reference training run did not finish within 30 minutes'
}

reconcile_airflow() {
  compose up -d --no-build airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  local attempt token
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
    http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
  for attempt in $(seq 1 60); do
    if curl -fsS -H "Authorization: Bearer ${token}" \
        http://10.61.40.35:8080/api/v2/dags/orion_label_export >/dev/null 2>&1; then
      docker exec kep-v2-airflow-api airflow sync-perm >/dev/null
      docker exec kep-v2-airflow-api \
        python /opt/airflow/orion-integrity/reconcile_airflow_roles.py >/dev/null
      docker exec kep-v2-airflow-api airflow users create \
        --username svc-orion-trainer --firstname Orion --lastname Trainer \
        --role 'Orion Runner' --email svc-orion-trainer@keplerops.lab \
        --password "${TRAINER_TOKEN}" >/dev/null 2>&1 || \
        docker exec kep-v2-airflow-api airflow users reset-password \
          --username svc-orion-trainer --password "${TRAINER_TOKEN}" >/dev/null
      local runner_token denied_status dag_id
      runner_token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
        --data "$(jq -cn --arg password "${TRAINER_TOKEN}" \
          '{username:"svc-orion-trainer",password:$password}')" \
        http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
      for dag_id in orion_release_risk_training orion_label_export orion_integrity_training \
          orion_integrity_review orion_upstream_sync orion_holdout_evaluation \
          orion_graph_review orion_dataset_attestation; do
        curl -fsS -H "Authorization: Bearer ${runner_token}" \
          "http://10.61.40.35:8080/api/v2/dags/${dag_id}" >/dev/null
      done
      denied_status="$(curl -sS -o /dev/null -w '%{http_code}' \
        -H "Authorization: Bearer ${runner_token}" \
        http://10.61.40.35:8080/api/v2/dags/engineering_inventory)"
      [[ ${denied_status} == 403 || ${denied_status} == 404 ]] || \
        die 'earned trainer identity has unscoped Airflow DAG access'
      ensure_clean_training_reference
      return 0
    fi
    (( attempt < 60 )) || break
    sleep 2
  done
  die 'Airflow did not discover the m07 workflow bundle'
}

apply_one() {
  local operation=$1
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${operation}"
  capture_clean_state
  reconcile_trainer_access
  seed_repositories
  reconcile_harbor
  reconcile_airflow
  install -d -m 0750 "${STATE_ROOT}/applied"
  printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  log "reconciled ${operation} start state"
}

main() {
  local requested=${1:-all} operation command
  for command in awk base64 curl cut date docker jq python3 sha256sum; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  install -d -m 0770 "${STATE_ROOT}"
  chown 50000:0 "${STATE_ROOT}"
  install -d -m 0700 "${STATE_ROOT}/attempts/kep-m07-i"
  chown 1000:1000 "${STATE_ROOT}/attempts/kep-m07-i"
  if [[ ${requested} != all ]]; then apply_one "${requested}"; return; fi
  capture_clean_state
  reconcile_trainer_access
  seed_repositories
  reconcile_harbor
  reconcile_airflow
  install -d -m 0750 "${STATE_ROOT}/applied"
  while IFS= read -r operation; do
    printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  done < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  log 'reconciled all operation start state'
}

main "$@"
