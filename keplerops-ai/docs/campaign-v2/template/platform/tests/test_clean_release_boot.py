import pathlib
import unittest


PLATFORM = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = PLATFORM.parent


def source(relative: str) -> str:
    return (TEMPLATE / relative).read_text(encoding="utf-8")


class CleanReleaseBootSourceTests(unittest.TestCase):
    def test_initial_platform_deploy_is_core_only_and_never_deploys_placeholder(self) -> None:
        deploy = source("platform/scripts/deploy-to-k3s01.sh")
        install = source("platform/scripts/install-platform.sh")
        self.assertNotIn("ORION_PLACEHOLDER_IMAGE", deploy)
        self.assertNotIn('kubectl apply -k "$ROOT/gitops/orion-canary"', install)
        self.assertIn("readiness.sh --core", deploy)
        self.assertIn("computeMetadata/v1/project/project-id", deploy)
        self.assertIn("printf 'VERTEX_PROJECT=%q", deploy)

    def test_assistant_capture_resolves_secret_backed_vertex_project(self) -> None:
        capture = source("platform/scripts/capture-assistant-runtime.sh")
        self.assertIn("secret_project", capture)
        self.assertIn('.valueFrom.secretKeyRef.name == "litellm-runtime"', capture)
        self.assertIn("active Vertex proxy project is stale", capture)
        self.assertNotIn('.env[] | select(.name == "VERTEX_PROJECT") | .value |', capture)

    def test_vertex_routes_have_distinct_internal_and_edge_authentication(self) -> None:
        deploy = source("platform/scripts/deploy-to-k3s01.sh")
        install = source("platform/scripts/install-platform.sh")
        manifest = source("platform/manifests/litellm.yaml")
        proxy = source("platform/images/orion-agent/vertex_proxy.py")
        edge = source("campaign-start/modules/m06/payloads/model-edge/api.py")
        self.assertIn("partner-model-identity.env", deploy)
        self.assertIn("VERTEX_EDGE_KEY_REGISTRY_JSON", deploy)
        self.assertIn("VERTEX_INTERNAL_RANGE_ID", deploy)
        self.assertIn("VERTEX_EDGE_KEY_REGISTRY_JSON", install)
        self.assertIn("VERTEX_INTERNAL_API_KEY", manifest)
        self.assertIn('authorization, f"Bearer {INTERNAL_API_KEY}"', proxy)
        for header in (
            "x-keplerops-assertion-version",
            "x-keplerops-assertion-key-id",
            "x-keplerops-assertion-audience",
            "x-keplerops-assertion-subject",
            "x-keplerops-credential-class",
            "x-keplerops-assertion-expires-at",
        ):
            self.assertIn(header, proxy)
        self.assertIn('UPSTREAM_MODEL.removeprefix("openai/")', edge)
        self.assertNotIn("VERTEX_RANGE_ASSERTION_KEY", manifest)

    def test_m07_materialization_precedes_every_other_module(self) -> None:
        apply = source("campaign-start/apply.sh")
        bootstrap = apply.index('"${ROOT}/modules/m07/apply.sh"')
        materialize = apply.index('"${ROOT}/../scripts/materialize-clean-release.sh"')
        loop = apply.index('for module in "${modules[@]}"')
        self.assertLess(bootstrap, materialize)
        self.assertLess(materialize, loop)
        self.assertIn('[[ $(basename "${module}") == m07 ]] && continue', apply[loop:])

    def test_builder_selects_only_the_m07_baseline_lineage(self) -> None:
        build = source("platform/scripts/build-release-candidate.sh")
        self.assertIn("M07_BASELINE_EXPORT_SHA256_FILE", build)
        self.assertIn("M07_CLEAN_TRAINING_REFERENCE_FILE", build)
        self.assertIn("reference_run_id", build)
        self.assertIn("reference_model_version", build)
        self.assertIn(".info.run_id == $reference.mlflow_run_id", build)
        self.assertIn('tagged("source.export_sha256"', build)
        self.assertIn('tagged("source.commit"', build)
        self.assertIn('tagged("source.tree_sha256"', build)
        self.assertIn('tagged("provenance.signature"', build)
        self.assertIn('json.dumps(tree,sort_keys=True,separators=', build)
        self.assertNotIn("jq -cS '.tree'", build)
        self.assertNotIn('order_by:["attributes.start_time DESC"]', build)
        self.assertNotIn("sort_by(.info.start_time", build)

    def test_materialization_orders_release_before_later_campaign_modules(self) -> None:
        materialize = source("scripts/materialize-clean-release.sh")
        seed = materialize.index('seed-gitops.sh" --repository-only')
        build = materialize.index("build-release-candidate.sh")
        promote = materialize.index('"${PLATFORM_ROOT}/scripts/promote-release-candidate.sh"')
        capture = materialize.index('sudo /opt/keplerops-platform/scripts/capture-assistant-runtime.sh')
        activate = materialize.index('"${ROOT}/scripts/activate-business-model-identities.sh"')
        continuity = materialize.rindex("release-runtime-continuity.sh")
        readiness = materialize.rindex("readiness.sh")
        self.assertLess(seed, build)
        self.assertLess(build, promote)
        self.assertLess(promote, capture)
        self.assertLess(capture, activate)
        self.assertLess(activate, continuity)
        self.assertLess(continuity, readiness)
        self.assertNotIn("operation accepted", materialize.lower())
        self.assertNotIn("checkpoint", materialize.lower())

    def test_gitops_seed_is_repository_only_before_clean_promotion(self) -> None:
        seed = source("platform/scripts/seed-gitops.sh")
        materialize = source("scripts/materialize-clean-release.sh")
        self.assertIn("--repository-only", seed)
        self.assertIn("ensure_main_branch", seed)
        self.assertLess(
            materialize.index('seed-gitops.sh" --repository-only'),
            materialize.index('"${PLATFORM_ROOT}/scripts/promote-release-candidate.sh"'),
        )

    def test_full_readiness_rejects_placeholder_and_requires_exact_joins(self) -> None:
        readiness = source("platform/scripts/readiness.sh")
        for required in (
            "current-release",
            "current-assistant-release",
            'contains("placeholder") | not',
            ".status.sync.revision == $commit",
            'annotations["keplerops.lab/release-revision"]',
            'annotations["keplerops.lab/model-digest"]',
            ".spec.predictor.containers[0].image == $image",
            ".imageID | contains($digest)",
            ".mlflow_run_id == $release[0].model.mlflow_run_id",
            'model == "zai-org/glm-5-maas"',
            "active Orion assistant Secret is stale",
        ):
            self.assertIn(required, readiness)

    def test_start_all_does_not_activate_identities_before_campaign_apply(self) -> None:
        start = source("scripts/start-all.sh")
        self.assertNotIn("activate-business-model-identities.sh", start)
        self.assertLess(start.index("campaign-start/apply.sh"), start.index("scripts/check-all.sh"))
        self.assertIn("readiness.sh --core", start)

    def test_shifter_readiness_is_last_and_checks_are_non_mutating(self) -> None:
        start = source("scripts/start-all.sh")
        workstation = source("scripts/start-workstation.sh")
        check_all = source("scripts/check-all.sh")
        public = source("baseline/public-surfaces.sh")
        readiness_write = start.index('>"$SHIFTER_READY"')
        self.assertGreater(readiness_write, start.index('"$ROOT/scripts/check-all.sh"'))
        self.assertNotIn("preconfigured-range-host.ready", workstation)
        self.assertNotIn("workhub-rag.sh", check_all)
        preview_check = public.split("preview_body=", 1)[1].split("intake_body=", 1)[0]
        self.assertNotIn("--request POST", preview_check)
        self.assertNotIn("send_message", public)

    def test_workstation_does_not_expose_test_framing(self) -> None:
        compose = source("compose.workbench.yaml")
        prepare = source("scripts/prepare-workstation.sh")
        dossier = source("campaign-start/modules/m06/payloads/workbench/START-HERE.md")
        self.assertNotIn("KEPLEROPS_RANGE_INSTANCE", compose)
        self.assertNotIn("KEPLEROPS_PARTICIPANT", compose)
        self.assertNotIn("reset-generation:/run", compose)
        self.assertNotIn("Playtest", prepare)
        for term in ("participant", "backend actor", "CTF", "Shifter", "QA"):
            self.assertNotIn(term.lower(), dossier.lower())

    def test_m10_baseline_does_not_require_m09_success(self) -> None:
        apply = source("campaign-start/modules/m10/apply.sh")
        baseline_branch = apply.index('if [[ ${OPERATION} == all ]]')
        accepted_branch = apply.index("verify_accepted_release", baseline_branch)
        self.assertIn("verify_clean_platform_release", apply[baseline_branch:accepted_branch])
        self.assertNotIn("M09_ACCEPTED", apply[baseline_branch:accepted_branch])
        self.assertIn('printf \'clean-platform-release\\n\' >"${STATE_ROOT}/baseline-ready"', apply)
        self.assertNotIn("jq -r '.[].id'", apply)


if __name__ == "__main__":
    unittest.main()
