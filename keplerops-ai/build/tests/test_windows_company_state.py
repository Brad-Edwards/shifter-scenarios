from __future__ import annotations

import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = PACK_ROOT / "build"
GCP_ROOT = BUILD_ROOT / "gcp"


class WindowsCompanyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        cls.bootstrap = (GCP_ROOT / "windows-bootstrap.ps1.tpl").read_text(
            encoding="utf-8"
        )
        cls.reset = (BUILD_ROOT / "reset.sh").read_text(encoding="utf-8")

    def test_terraform_passes_the_authored_document_as_data(self) -> None:
        self.assertIn(
            'yamldecode(file("${path.module}/../../assets/content/company-state/company-state.yaml"))',
            self.terraform,
        )
        self.assertIn(
            "company_state_b64 = base64encode(jsonencode(local.company_state))",
            self.terraform,
        )
        self.assertIn(
            '[Convert]::FromBase64String("${company_state_b64}")',
            self.bootstrap,
        )
        self.assertIn("ConvertFrom-Json", self.bootstrap)

    def test_ad_materialization_uses_authored_identity_and_endpoint_metadata(self) -> None:
        for source in (
            "$CompanyState.teams",
            "$CompanyState.people",
            "$CompanyState.service_identities",
            "$CompanyState.endpoints",
        ):
            self.assertIn(source, self.bootstrap)
        for command in (
            "New-ADGroup",
            "Set-ADGroup",
            "New-ADUser",
            "Set-ADAccountPassword",
            "Enable-ADAccount",
            "Set-ADUser",
            "Add-ADGroupMember",
            "Set-ADComputer",
        ):
            self.assertIn(command, self.bootstrap)
        self.assertIn("$person.display_name `", self.bootstrap)
        self.assertIn("$person.title `", self.bootstrap)
        self.assertIn("$team.name `", self.bootstrap)
        self.assertIn("-ManagedBy (Get-ADUser $lead.username)", self.bootstrap)
        self.assertIn("DisplayName = $Endpoint.hostname", self.bootstrap)
        self.assertIn("Location = $team.name", self.bootstrap)
        self.assertIn("FindDomainController()", self.bootstrap)
        self.assertIn("-Server $directoryServer", self.bootstrap)
        self.assertIn("-Credential $Credential", self.bootstrap)

        for identity in (
            '"qa.intern" = "ad-qa-password"',
            '"ml.engineer" = "ad-ml-engineer-password"',
            '"release.manager" = "ad-release-manager-password"',
            '"guardrail.admin"',
            '"svc.keycloak"',
        ):
            self.assertIn(identity, self.bootstrap)
        self.assertIn(
            "Set-ADAccountPassword -Identity $user -Reset -NewPassword $password",
            self.bootstrap,
        )
        self.assertIn(
            "Set-ADUser -Identity $user -PasswordNeverExpires $true",
            self.bootstrap,
        )

    def test_smb_files_have_native_acls_and_represented_timestamps(self) -> None:
        for contract in (
            "New-SmbShare",
            "Security.AccessControl.DirectorySecurity",
            "Security.AccessControl.FileSecurity",
            "Set-Acl",
            "SetCreationTimeUtc",
            "SetLastWriteTimeUtc",
            "SetLastAccessTimeUtc",
            "$CompanyState.files",
            "Test-AuthoredAcl",
        ):
            self.assertIn(contract, self.bootstrap)

    def test_endpoint_profiles_use_windows_profile_and_certificate_surfaces(self) -> None:
        for contract in (
            "[KeplerOpsNativeProfile]::LogonUser(",
            "[KeplerOpsNativeProfile]::LoadUserProfile(",
            "$identity.Impersonate()",
            "StoreLocation]::CurrentUser",
            "[KeplerOpsNativeProfile]::UnloadUserProfile(",
            "Get-CimInstance Win32_UserProfile",
            "PSReadLine\\ConsoleHost_history.txt",
            'Join-Path $profilePath ".gitconfig"',
            "Microsoft\\Windows\\Recent",
            "Cert:\\LocalMachine\\Root",
            "certificate-context.json",
        ):
            self.assertIn(contract, self.bootstrap)
        self.assertNotIn("New-ScheduledTaskPrincipal", self.bootstrap)
        self.assertNotIn("Register-ScheduledTask", self.bootstrap)

    def test_reset_reconstructs_the_packed_host_and_three_windows_disks(self) -> None:
        self.assertIn(
            "-replace='google_compute_instance.range_host[0]'",
            self.reset,
        )
        for host in (
            "ad-dc-01",
            "workforce-workstation-01",
            "ml-workstation-01",
        ):
            self.assertIn(
                f'-replace=\'google_compute_disk.windows_guest["{host}"]\'',
                self.reset,
            )
        self.assertNotIn("google_compute_instance.host", self.reset)
        self.assertIn("http://192.168.77.1:8080/metadata/instance/id", self.reset)
        self.assertIn("guest-attributes/$host/readback", self.reset)
        self.assertIn('"instance_id": expected_id', self.reset)
        self.assertIn('"windows_domain_readback"', self.reset)
        self.assertLess(
            self.reset.index("replace_nested_range"),
            self.reset.index('"$BUILD_ROOT/health-check.sh"'),
        )


if __name__ == "__main__":
    unittest.main()
