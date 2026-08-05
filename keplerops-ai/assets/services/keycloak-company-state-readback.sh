#!/bin/sh
set -eu

server="${KEYCLOAK_COMPANY_STATE_ADMIN_URL:-http://127.0.0.1:8080}"
realm="${KEYCLOAK_COMPANY_STATE_REALM:-keplerops}"
client_id="${KEYCLOAK_COMPANY_STATE_CLIENT_ID:-platform-context-admin}"
import_realm=/opt/keycloak/data/import/keplerops-realm.json
expected_projection=/opt/keycloak/import-source/company-native-projection.json
expected_readback=/opt/keycloak/import-source/company-readback.json
kcadm=/opt/keycloak/bin/kcadm.sh
config=/tmp/company-state-kcadm.config

client_secret=$(
  jq -er --arg client_id "$client_id" \
    '.clients[] | select(.clientId == $client_id) | .secret' \
    "$import_realm"
)

authenticated=false
for _attempt in $(seq 1 120); do
  if "$kcadm" config credentials \
    --server "$server" \
    --realm "$realm" \
    --client "$client_id" \
    --secret "$client_secret" \
    --config "$config" >/dev/null 2>&1; then
    authenticated=true
    break
  fi
  sleep 1
done
if [ "$authenticated" != true ]; then
  echo "Keycloak company-state Admin API authentication failed" >&2
  exit 1
fi

components=$(
  "$kcadm" get components \
    -r "$realm" \
    --config "$config"
)
ldap_provider_id=$(
  printf '%s' "$components" | jq -er '
    [.[] | select(.name == "keplerops-active-directory" and .providerId == "ldap")]
    | if length == 1 then .[0].id else empty end
  '
)
username_mapper_count=$(
  printf '%s' "$components" | jq \
    --arg parent "$ldap_provider_id" \
    '[.[] | select(.parentId == $parent and .name == "username")] | length'
)
username_mapper_id=$(
  printf '%s' "$components" | jq -er \
    --arg parent "$ldap_provider_id" \
    '.[] | select(.parentId == $parent and .name == "username") | .id' \
    2>/dev/null || true
)
if [ "$username_mapper_count" -eq 0 ]; then
  mapper_payload=/tmp/keycloak-ldap-username-mapper.json
  jq -n --arg parent "$ldap_provider_id" '{
    name: "username",
    providerId: "user-attribute-ldap-mapper",
    providerType: "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
    parentId: $parent,
    config: {
      "user.model.attribute": ["username"],
      "ldap.attribute": ["samaccountname"],
      "read.only": ["true"],
      "always.read.value.from.ldap": ["true"],
      "is.mandatory.in.ldap": ["true"]
    }
  }' >"$mapper_payload"
  "$kcadm" create components \
    -r "$realm" \
    -f "$mapper_payload" \
    --config "$config" >/dev/null
  rm -f "$mapper_payload"
elif [ "$username_mapper_count" -ne 1 ]; then
  echo "Keycloak LDAP username mapper is duplicated" >&2
  exit 1
else
  mapper_payload=/tmp/keycloak-ldap-username-mapper.json
  "$kcadm" get "components/$username_mapper_id" \
    -r "$realm" \
    --config "$config" | jq '
      .config["user.model.attribute"] = ["username"] |
      .config["ldap.attribute"] = ["samaccountname"] |
      .config["read.only"] = ["true"] |
      .config["always.read.value.from.ldap"] = ["true"] |
      .config["is.mandatory.in.ldap"] = ["true"]
    ' >"$mapper_payload"
  "$kcadm" update "components/$username_mapper_id" \
    -r "$realm" \
    -f "$mapper_payload" \
    --config "$config" >/dev/null
  rm -f "$mapper_payload"
fi

groups=$(
  "$kcadm" get groups \
    -r "$realm" \
    -q 'search=Company State' \
    -q exact=true \
    -q briefRepresentation=false \
    --config "$config"
)
root_count=$(printf '%s' "$groups" | jq '[.[] | select(.name == "Company State")] | length')
if [ "$root_count" -ne 1 ]; then
  echo "Keycloak company identity group is missing or duplicated" >&2
  exit 1
fi
root_id=$(printf '%s' "$groups" | jq -er '.[] | select(.name == "Company State") | .id')
root=$(
  "$kcadm" get "groups/$root_id" \
    -r "$realm" \
    -q briefRepresentation=false \
    --config "$config"
)
children=$(
  "$kcadm" get "groups/$root_id/children" \
    -r "$realm" \
    -q briefRepresentation=false \
    --config "$config"
)

subgroups='[]'
for subgroup_id in $(printf '%s' "$children" | jq -r '.[].id'); do
  subgroup=$(
    "$kcadm" get "groups/$subgroup_id" \
      -r "$realm" \
      -q briefRepresentation=false \
      --config "$config"
  )
  roles=$(
    "$kcadm" get "groups/$subgroup_id/role-mappings/realm" \
      -r "$realm" \
      --config "$config"
  )
  normalized=$(
    jq -cn \
      --argjson subgroup "$subgroup" \
      --argjson roles "$roles" \
      '{
        name: $subgroup.name,
        attributes: ($subgroup.attributes // {}),
        realmRoles: ($roles | map(.name) | sort)
      }'
  )
  subgroups=$(
    jq -cn \
      --argjson subgroups "$subgroups" \
      --argjson normalized "$normalized" \
      '$subgroups + [$normalized]'
  )
done

observed=$(
  jq -cnS \
    --argjson root "$root" \
    --argjson subgroups "$subgroups" \
    '{
      name: $root.name,
      attributes: ($root.attributes // {}),
      subGroups: ($subgroups | sort_by(.name))
    }'
)
expected=$(jq -cS . "$expected_projection")
if [ "$observed" != "$expected" ]; then
  echo "Keycloak company identity native readback mismatch" >&2
  exit 1
fi

cat "$expected_readback"
