#!/usr/bin/env bash
set -Eeuo pipefail

readonly KEY=${KEPLEROPS_V2_SSH_KEY:-/root/.ssh/keplerops-v2}
readonly DC01=${KEPLEROPS_DC01_ADDRESS:-192.168.78.10}
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

[[ $EUID -eq 0 ]] || { echo 'reconcile-directory-roles.sh must run as root' >&2; exit 2; }
[[ -r $KEY ]] || { printf 'SSH key is unreadable: %s\n' "$KEY" >&2; exit 2; }

"${SSH[@]}" "kepler@${DC01}" sudo bash -s <<'REMOTE'
set -Eeuo pipefail

for ou in People 'Service Accounts' Workstations Servers Groups; do
  samba-tool ou add "OU=${ou}" >/dev/null 2>&1 || true
done

ensure_user() {
  local username=$1 password=$2 given=$3 surname=$4 department=$5 email=$6
  if ! samba-tool user show "$username" >/dev/null 2>&1; then
    samba-tool user create "$username" "$password" \
      --userou='OU=People' --given-name="$given" --surname="$surname" \
      --department="$department" --company='KeplerOps AI Systems' \
      --mail-address="$email" >/dev/null
  elif ! samba-tool user show "$username" | grep -Fqi ',OU=People,DC='; then
    samba-tool user move "$username" 'OU=People' >/dev/null
  fi
  samba-tool user rename "$username" --mail-address="$email" >/dev/null
}

ensure_service_user() {
  local username=$1 password=$2 description=$3
  if ! samba-tool user show "$username" >/dev/null 2>&1; then
    samba-tool user create "$username" "$password" \
      --userou='OU=Service Accounts' --description="$description" >/dev/null
  elif ! samba-tool user show "$username" | grep -Fqi ',OU=Service Accounts,DC='; then
    samba-tool user move "$username" 'OU=Service Accounts' >/dev/null
  fi
  samba-tool user setexpiry "$username" --noexpiry >/dev/null
}

ensure_group() {
  local group=$1 description=$2
  samba-tool group show "$group" >/dev/null 2>&1 ||
    samba-tool group add "$group" --groupou='OU=Groups' \
      --group-scope=Global --group-type=Security \
      --description="$description" >/dev/null
}

add_members() {
  local group=$1
  shift
  local member
  for member in "$@"; do
    samba-tool group addmembers "$group" "$member" >/dev/null 2>&1 || true
  done
}

ensure_user reviewer 'KeplerV2-Training-Reviewer' Rina Chen 'Model Evaluation' reviewer@keplerops.lab
ensure_user ml.engineer 'KeplerV2-Training-MLEngineer' Maya Ortiz 'AI Research' ml.engineer@keplerops.lab
ensure_user data.annotator 'KeplerV2-Training-Annotator' Imani Brooks 'Data Operations' data.annotator@keplerops.lab
ensure_user release.engineer 'KeplerV2-Training-Release' Elliot Park 'Release Engineering' release.engineer@keplerops.lab
ensure_user release.approver 'KeplerV2-Training-Approver' Priya Nair 'Release Governance' release.approver@keplerops.lab
ensure_user platform.operator 'KeplerV2-Training-Platform' Luca Bianchi 'AI Platform' platform.operator@keplerops.lab
ensure_user support.analyst 'KeplerV2-Training-Support' Jonas Becker Support support.analyst@keplerops.lab
ensure_user comms.publisher 'KeplerV2-Training-Comms' Samira Okafor Communications comms.publisher@keplerops.lab
ensure_user finance.operator 'KeplerV2-Training-Finance' Hana Suzuki Finance finance.operator@keplerops.lab
ensure_user security.auditor 'KeplerV2-Training-Auditor' Darius Cole Security security.auditor@keplerops.lab
ensure_service_user svc-keycloak-ldap 'KeplerV2-Training-Keycloak-LDAP' \
  'Read-only LDAP bind for Keycloak federation'

while IFS='|' read -r group description; do
  ensure_group "$group" "$description"
done <<'GROUPS'
GG-Orion-Researchers|Orion research staff
GG-Orion-Annotators|Orion dataset annotators
GG-Orion-Evaluators|Orion model evaluators
GG-Release-Engineers|Release engineering staff
GG-Release-Approvers|Independent release approvers
GG-Platform-Operators|AI platform operators
GG-Support-Agents|Customer support agents
GG-Communications|Corporate communications staff
GG-Finance-Operations|Finance operations staff
GG-Security-Auditors|Security audit staff
RG-WorkHub-Orion|WorkHub Orion project access
RG-Nextcloud-Orion-Internal|Nextcloud Orion internal room access
RG-Forgejo-Orion-Read|Forgejo Orion read access
RG-Forgejo-Orion-Contribute|Forgejo Orion contribution access
RG-Jupyter-Orion-Evaluation|Jupyter Orion evaluation workspace access
RG-LabelStudio-Orion-Contribute|Label Studio Orion contribution access
RG-MLflow-Orion-Read|MLflow Orion read access
RG-MLflow-Orion-Maintain|MLflow Orion maintenance access
RG-Harbor-Orion-Review|Harbor Orion review access
RG-Harbor-Orion-Release|Harbor Orion release access
RG-Airflow-Orion-View|Airflow Orion view access
RG-Airflow-Orion-Run|Airflow Orion run access
RG-Release-Policy-Request|Release policy request access
RG-Release-Policy-Approve|Release policy approval access
GROUPS

add_members GG-Orion-Researchers ml.engineer
add_members GG-Orion-Annotators data.annotator ml.engineer
add_members GG-Orion-Evaluators reviewer security.auditor
add_members GG-Release-Engineers release.engineer
add_members GG-Release-Approvers release.approver
add_members GG-Platform-Operators platform.operator
add_members GG-Support-Agents support.analyst
add_members GG-Communications comms.publisher
add_members GG-Finance-Operations finance.operator
add_members GG-Security-Auditors security.auditor

add_members RG-WorkHub-Orion GG-Orion-Researchers GG-Orion-Evaluators GG-Release-Engineers ml.engineer reviewer security.auditor release.engineer
add_members RG-Nextcloud-Orion-Internal GG-Orion-Researchers GG-Orion-Evaluators ml.engineer reviewer security.auditor
add_members RG-Forgejo-Orion-Read GG-Orion-Researchers GG-Orion-Evaluators GG-Release-Engineers ml.engineer reviewer security.auditor release.engineer
add_members RG-Forgejo-Orion-Contribute GG-Orion-Researchers GG-Release-Engineers ml.engineer release.engineer
add_members RG-Jupyter-Orion-Evaluation GG-Orion-Researchers GG-Orion-Evaluators ml.engineer reviewer security.auditor
add_members RG-LabelStudio-Orion-Contribute GG-Orion-Annotators data.annotator ml.engineer
add_members RG-MLflow-Orion-Read GG-Orion-Researchers GG-Orion-Evaluators ml.engineer reviewer security.auditor
add_members RG-MLflow-Orion-Maintain GG-Orion-Researchers ml.engineer
add_members RG-Harbor-Orion-Review GG-Orion-Evaluators GG-Release-Engineers reviewer security.auditor release.engineer
add_members RG-Harbor-Orion-Release GG-Release-Engineers GG-Release-Approvers release.engineer release.approver
add_members RG-Airflow-Orion-View GG-Orion-Researchers GG-Orion-Evaluators ml.engineer reviewer security.auditor
add_members RG-Airflow-Orion-Run GG-Orion-Researchers ml.engineer
add_members RG-Release-Policy-Request GG-Release-Engineers release.engineer
add_members RG-Release-Policy-Approve GG-Release-Approvers release.approver

printf 'directory role and resource groups reconciled\n'
REMOTE
