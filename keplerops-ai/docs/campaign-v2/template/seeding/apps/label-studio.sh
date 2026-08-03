#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly LABEL_STUDIO_CONTAINER=kep-v2-label-studio
readonly LABEL_STUDIO_GROUP=RG-LabelStudio-Orion-Contribute
readonly LABEL_STUDIO_ADMIN_EMAIL=annotation.admin@keplerops.lab

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

account_json() {
  local username=$1
  case "${username}" in
    data.annotator)
      jq -cn '{
        username:"data.annotator",
        email:"data.annotator@keplerops.lab",
        first_name:"Data",
        last_name:"Annotator",
        password:"KeplerV2-Training-Annotator"
      }'
      ;;
    ml.engineer)
      jq -cn '{
        username:"ml.engineer",
        email:"ml.engineer@keplerops.lab",
        first_name:"ML",
        last_name:"Engineer",
        password:"KeplerV2-Training-MLEngineer"
      }'
      ;;
    *)
      die "no Label Studio local credential is defined for ${username}"
      ;;
  esac
}

main() {
  require_command docker
  require_command jq
  require_service keycloak
  docker inspect "${LABEL_STUDIO_CONTAINER}" >/dev/null 2>&1 ||
    die "Label Studio container is unavailable: ${LABEL_STUDIO_CONTAINER}"

  retry 60 2 kcadm config credentials \
    --server http://localhost:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null ||
    die "Keycloak admin authentication failed"

  local group_id members accounts username
  group_id="$(kcadm get groups -r "${KEYCLOAK_REALM}" \
    -q "search=${LABEL_STUDIO_GROUP}" |
    jq -er --arg group "${LABEL_STUDIO_GROUP}" \
      '.[] | select(.name == $group) | .id' | head -n1)"
  members="$(kcadm get "groups/${group_id}/members" -r "${KEYCLOAK_REALM}" \
    -q first=0 -q max=1000)"
  accounts='[]'
  while IFS= read -r username; do
    [[ -n ${username} ]] || continue
    accounts="$(jq -cn --argjson current "${accounts}" \
      --argjson account "$(account_json "${username}")" \
      '$current + [$account]')"
  done < <(jq -r '.[].username' <<<"${members}" | sort -u)
  [[ $(jq 'length' <<<"${accounts}") -gt 0 ]] ||
    die "Label Studio contributor group has no members"

  docker exec -i \
    --env "KEPLER_LABEL_ACCOUNTS=${accounts}" \
    --env "KEPLER_LABEL_ADMIN=${LABEL_STUDIO_ADMIN_EMAIL}" \
    "${LABEL_STUDIO_CONTAINER}" sh -ec '
      manage=$(python -c '\''import label_studio, pathlib; print(pathlib.Path(label_studio.__file__).with_name("manage.py"))'\'')
      exec python "$manage" shell
    ' <<'PY'
import json
import os

from organizations.models import Organization, OrganizationMember
from users.models import User


accounts = json.loads(os.environ["KEPLER_LABEL_ACCOUNTS"])
admin_email = os.environ["KEPLER_LABEL_ADMIN"]
organization = Organization.objects.first()
if organization is None:
    raise RuntimeError("Label Studio organization is unavailable")

allowed_emails = []
for account in accounts:
    user, _ = User.objects.get_or_create(email=account["email"])
    user.username = account["username"]
    user.first_name = account["first_name"]
    user.last_name = account["last_name"]
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.active_organization = organization
    user.set_password(account["password"])
    user.save()
    membership, _ = OrganizationMember.objects.get_or_create(
        user=user, organization=organization
    )
    if membership.deleted_at is not None:
        membership.deleted_at = None
        membership.save(update_fields=["deleted_at"])
    allowed_emails.append(user.email)

User.objects.exclude(email=admin_email).exclude(email__in=allowed_emails).update(
    is_active=False
)

active_participants = set(
    User.objects.filter(is_active=True)
    .exclude(email=admin_email)
    .values_list("email", flat=True)
)
if active_participants != set(allowed_emails):
    raise RuntimeError("Label Studio active-user set differs from the AD resource group")

print(
    "Label Studio binary contributor access reconciled: "
    + ", ".join(sorted(active_participants))
)
PY

  log "Label Studio CE contributor accounts match ${LABEL_STUDIO_GROUP}; no RBAC role is claimed"
}

main "$@"
