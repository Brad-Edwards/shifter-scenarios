"""Compare the authored pack with the private source oracle, without cloud effects."""

from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from raes import parse_sdl, parse_sdl_file
from raes.instantiate import instantiate_scenario
from raes_contracts.explicitness import ExplicitnessClass
from raes_env_packs.digest import validate_pack_content_manifest
from raes_processor.compiler import compile_scenario_runtime_model

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "kontakte-sm-sa"
DESIGN = REPO / "docs/technical/plans/276-kontakte-sm-sa"
AUTH = "nodes.cloud.project.runtime.identity_authorities.range-iam"
SCOPE = AUTH + ".resource_scopes.range-project"
APP = "nodes.cloud.project.runtime.platform_applications.secret-manager"
BINDING_TYPES = (
    "google_project_iam_member",
    "google_service_account_iam_member",
    "google_secret_manager_secret_iam_member",
)


@pytest.fixture(scope="module")
def scenario():
    return parse_sdl_file(PACK / "sdl/kontakte-sm-sa.sdl.yaml")


@pytest.fixture(scope="module")
def oracle():
    return json.loads((DESIGN / "oracle-inventory.json").read_text())


def assert_cloud_parity(scenario, oracle):
    source = oracle["resources"]
    assert set(source) == set(BINDING_TYPES) | {
        "google_service_account",
        "google_secret_manager_secret",
        "google_secret_manager_secret_version",
        "google_project_iam_audit_config",
    }
    cloud = scenario.nodes["cloud.project"].runtime
    assert len(cloud.identity_authorities) == 1
    assert len(cloud.platform_applications) == 1
    assert not cloud.software_components
    authority = cloud.identity_authorities[0]
    application = cloud.platform_applications[0]
    assert not authority.identity_uses
    assert len(authority.resource_scopes) == 1
    scope = authority.resource_scopes[0]
    assert scope.provider == "gcp"
    assert scope.scope_kind == "project"
    assert not scope.native_id
    assert application.resource_scope_ref == SCOPE
    assert application.product == "GCP Secret Manager"

    by_account = {v["account_id"]: v for v in source["google_service_account"].values()}
    local = [s for s in authority.subjects if s.resource_scope_ref == SCOPE]
    assert len(local) == len(by_account) == 44
    assert {s.name: s.display_name for s in local} == {
        name: account["display_name"] for name, account in by_account.items()
    }
    assert all(s.kind.value == "service_account" for s in local)
    members = {
        AUTH + ".subjects." + s.subject_id: "serviceAccount:"
        + s.name
        + "@"
        + by_account[s.name]["project"]
        + ".iam.gserviceaccount.com"
        for s in local
    }
    outside = [
        s
        for s in authority.subjects
        if not s.resource_scope_ref and s.kind.value != "role"
    ]
    assert len(outside) == 71
    assert {s.name for s in outside} == {
        p["placeholder"] for p in oracle["external_principals"]
    }
    for subject in outside:
        assert subject.origin.value == "operator"
        assert subject.name == subject.principal_name
        prefix = subject.name.partition(":")[0]
        kind = {
            "user": "user",
            "group": "group",
            "serviceAccount": "service_account",
        }.get(prefix, "service_principal")
        if ".svc.id.goog[" in subject.name:
            kind = "service_principal"
        assert subject.kind.value == kind
        members[AUTH + ".subjects." + subject.subject_id] = subject.name
    roles = {
        AUTH + ".subjects." + s.subject_id: s.name
        for s in authority.subjects
        if s.kind.value == "role"
    }
    assert set(roles.values()) == {
        b["role"] for kind in BINDING_TYPES for b in source[kind].values()
    }
    assert len(authority.subjects) == len(local) + len(outside) + len(roles)

    entries = getattr(application, "secrets")
    native_secrets = {s.native_id: s for s in entries}
    assert len(native_secrets) == len(entries) == 391
    assert set(native_secrets) == {
        v["secret_id"] for v in source["google_secret_manager_secret"].values()
    }
    for secret in entries:
        assert secret.resource_scope_ref == SCOPE
        assert secret.replication.provider == "gcp-secret-manager"
        assert secret.replication.mode == "automatic"
        assert not secret.replication.replicas
        assert secret.replication.kms_key_name is None
        assert len(secret.versions) == 1
        version = secret.versions[0]
        assert version.state == "enabled"
        assert not version.payload_content_ref
        assert not secret.consumers

    attachments = {SCOPE: ("project", "")}
    attachments.update(
        {AUTH + ".subjects." + s.subject_id: ("service_account", s.name) for s in local}
    )
    attachments.update(
        {
            ".".join((APP, "secrets", s.secret_id)): ("secret", s.native_id)
            for s in entries
        }
    )
    actual = Counter()
    for policy in authority.policies:
        access = policy.resource_access
        assert access is not None
        assert not access.inherited_from_ref
        attachment = attachments[access.attachment_ref]
        for binding in access.bindings:
            assert binding.effect == "allow"
            assert not binding.actions
            assert binding.condition is None
            assert binding.resource_refs == [access.attachment_ref]
            for ref in binding.principal_refs:
                actual[(*attachment, roles[binding.role_ref], members[ref])] += 1
    expected = Counter()
    for kind in BINDING_TYPES:
        for binding in source[kind].values():
            if kind == "google_project_iam_member":
                attachment = ("project", "")
            elif kind == "google_service_account_iam_member":
                key = binding["service_account_id"].split(".")[1]
                attachment = (
                    "service_account",
                    source["google_service_account"][key]["account_id"],
                )
            else:
                key = binding["secret_id"].split(".")[1]
                attachment = (
                    "secret",
                    source["google_secret_manager_secret"][key]["secret_id"],
                )
            expected[(*attachment, binding["role"], binding["member"])] += 1
    assert actual == expected
    assert sum(actual.values()) == 562
    expected_audit = Counter(
        (a["service"], log["log_type"])
        for a in source["google_project_iam_audit_config"].values()
        for log in a["audit_log_config"]
    )
    assert Counter((a.service, a.log_type) for a in scope.audit_logs) == expected_audit
    assert all(not a.exempted_principal_refs for a in scope.audit_logs)


def test_exact_cloud_source_parity(scenario, oracle):
    assert_cloud_parity(scenario, oracle)


def test_workstation_and_only_source_file_are_preserved(scenario, oracle):
    raw = (DESIGN / "workstation-oracle.sdl.yaml").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == oracle["sources"]["shifter-pack/sdl/kontakte-sm-sa.sdl.yaml"]["sha256"]
    )
    document = yaml.safe_load(raw)
    document["agents"]["participant"]["affiliations"] = [
        document["agents"]["participant"].pop("entity")
    ]
    expected = parse_sdl(yaml.safe_dump(document))
    assert set(scenario.nodes) == {"lan", "workstation", "cloud.project"}
    for name in ("lan", "workstation"):
        assert scenario.nodes[name] == expected.nodes[name]
    for section in (
        "infrastructure",
        "content",
        "entities",
        "accounts",
        "agents",
        "relationships",
        "variables",
    ):
        assert getattr(scenario, section) == getattr(expected, section)
    assert set(scenario.content) == {"foothold-key"}
    constraints = scenario.expansion_provenance.realization_constraints
    assert len(constraints) == 1
    assert constraints[0].field_pointer == "/nodes/workstation"
    assert constraints[0].domain.value == "virtual-machine"


def test_parameter_defaults_remain_nonexact_after_instantiation(scenario):
    concrete = instantiate_scenario(scenario)
    explicitness = {
        r.model_path: r for r in concrete.instantiation_provenance.explicitness
    }
    subjects = concrete.nodes["cloud.project"].runtime.identity_authorities[0].subjects
    for index, subject in enumerate(subjects):
        prefix = (
            "nodes.cloud.project.runtime.identity_authorities[0].subjects["
            + str(index)
            + "]"
        )
        if subject.origin.value == "operator":
            for field in ("name", "principal_name"):
                record = explicitness[prefix + "." + field]
                assert record.classification == ExplicitnessClass.CONSTRAINED
                assert len(record.parameters) == 1
        elif subject.resource_scope_ref:
            assert (
                explicitness[prefix + ".display_name"].classification
                == ExplicitnessClass.EXACT
            )
    assert concrete.content["foothold-key"].text == "PLACEHOLDER-REPLACED-PER-RUN"


def test_compiler_retains_cloud_requirements(scenario, oracle):
    model = compile_scenario_runtime_model(scenario)
    assert not [d for d in model.diagnostics if d.is_error]
    assert_cloud_parity(model.realization_instance, oracle)


def test_manifest_binds_every_pack_file():
    validate_pack_content_manifest(PACK)


@pytest.fixture(scope="module")
def client_schema(oracle):
    schema = json.loads((PACK / "docs/client-input.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    properties = schema["properties"]
    assert set(properties["principal_map"]["required"]) == {
        p["placeholder"] for p in oracle["external_principals"]
    }
    resources = oracle["resources"]
    assert set(properties["secret_values"]["properties"]) == {
        s["secret_id"] for s in resources["google_secret_manager_secret"].values()
    }
    assert set(properties["foothold_service_account"]["enum"]) == {
        s["account_id"] for s in resources["google_service_account"].values()
    }
    return schema


@pytest.mark.parametrize(
    "case,accepted",
    [
        ("missing-values", True),
        ("empty-string", True),
        ("supplied-string", True),
        ("null-value", False),
        ("unknown-secret", False),
        ("missing-principal", False),
        ("unknown-principal", False),
        ("wrong-kind", False),
        ("extra-account", False),
        ("missing-account", False),
        ("project-override", False),
    ],
)
def test_client_inputs(client_schema, case, accepted):
    properties = client_schema["properties"]
    members = properties["principal_map"]["required"]
    secret = next(iter(properties["secret_values"]["properties"]))
    document = {
        "principal_map": {p: p for p in members},
        "foothold_service_account": properties["foothold_service_account"]["enum"][0],
    }
    if case == "empty-string":
        document["secret_values"] = {secret: ""}
    elif case == "supplied-string":
        document["secret_values"] = {secret: "synthetic"}
    elif case == "null-value":
        document["secret_values"] = {secret: None}
    elif case == "unknown-secret":
        document["secret_values"] = {"unknown-secret": "synthetic"}
    elif case == "missing-principal":
        document["principal_map"].pop(members[0])
    elif case == "unknown-principal":
        document["principal_map"]["unknown"] = "user:example@example.invalid"
    elif case == "wrong-kind":
        document["principal_map"][members[0]] = "wrong-kind:value"
    elif case == "extra-account":
        document["foothold_service_account"] = "extra-account"
    elif case == "missing-account":
        document.pop("foothold_service_account")
    elif case == "project-override":
        document["project"] = "unregistered-project"
    assert (
        not list(Draft202012Validator(client_schema).iter_errors(document))
    ) == accepted


def test_client_template_requires_completion(client_schema):
    template = json.loads((PACK / "docs/client-input.template.json").read_text())
    assert set(template["principal_map"]) == set(
        client_schema["properties"]["principal_map"]["required"]
    )
    assert list(Draft202012Validator(client_schema).iter_errors(template))


@pytest.mark.parametrize(
    "change",
    [
        "drop-binding",
        "display-name",
        "principal",
        "role",
        "secret-id",
        "replication",
        "version-state",
        "audit-type",
        "extra-account",
    ],
)
def test_parity_detects_changes_to_authored_state(scenario, oracle, change):
    mutated = scenario.model_copy(deep=True)
    cloud = mutated.nodes["cloud.project"].runtime
    authority = cloud.identity_authorities[0]
    binding = authority.policies[0].resource_access.bindings[0]
    secret = getattr(cloud.platform_applications[0], "secrets")[0]
    if change == "drop-binding":
        authority.policies[0].resource_access.bindings.pop()
    elif change == "display-name":
        authority.subjects[0].display_name = "changed"
    elif change == "principal":
        binding.principal_refs = []
    elif change == "role":
        role = next(s for s in authority.subjects if s.kind.value == "role")
        role.name = "roles/viewer"
    elif change == "secret-id":
        secret.native_id = "changed"
    elif change == "replication":
        secret.replication.mode = "user-managed"
    elif change == "version-state":
        secret.versions[0].state = "disabled"
    elif change == "audit-type":
        authority.resource_scopes[0].audit_logs[0].log_type = "DATA_WRITE"
    else:
        authority.subjects.append(authority.subjects[0].model_copy())
    with pytest.raises(AssertionError):
        assert_cloud_parity(mutated, oracle)
