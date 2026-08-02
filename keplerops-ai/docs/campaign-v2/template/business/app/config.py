from __future__ import annotations

import os
from dataclasses import dataclass


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    range_id: str = env("KEPLEROPS_RANGE_ID", "template")
    adapter_token: str = env(
        "BUSINESS_ADAPTER_TOKEN", "KeplerV2-Training-Business-Adapter"
    )
    decision_signing_key: str = env(
        "ORION_DECISION_SIGNING_KEY", "KeplerV2-Training-Orion-Decision-Signing"
    )
    decision_signing_key_id: str = env(
        "ORION_DECISION_SIGNING_KEY_ID", "orion-business-decision-v1"
    )
    release_risk_release_id: str = env(
        "ORION_RELEASE_RISK_RELEASE_ID", "sha256:" + "1" * 64
    )
    release_risk_model_digest: str = env(
        "ORION_RELEASE_RISK_MODEL_DIGEST", "sha256:" + "2" * 64
    )
    release_risk_image_digest: str = env(
        "ORION_RELEASE_RISK_IMAGE_DIGEST", "sha256:" + "3" * 64
    )
    assistant_release_id: str = env("ORION_ASSISTANT_RELEASE_ID", "sha256:" + "9" * 64)
    assistant_model_digest: str = env(
        "ORION_ASSISTANT_MODEL_DIGEST", "sha256:" + "a" * 64
    )
    assistant_image_digest: str = env(
        "ORION_ASSISTANT_IMAGE_DIGEST", "sha256:" + "b" * 64
    )
    active_policy_digest: str = env("ORION_ACTIVE_POLICY_DIGEST", "sha256:" + "4" * 64)
    release_risk_url: str = env("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083")
    release_risk_model: str = env("ORION_RELEASE_RISK_MODEL", "orion-release-risk")
    assistant_url: str = env("ORION_AGENT_URL", "http://192.168.78.30:30081")
    assistant_api_key: str = env(
        "ORION_AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053"
    )
    audit_database: str = env(
        "BUSINESS_AUDIT_DATABASE", "/var/lib/keplerops-business/audit.sqlite3"
    )
    evidence_directory: str = env(
        "BUSINESS_EVIDENCE_DIRECTORY", "/var/lib/keplerops-business/evidence"
    )

    opa_url: str = env("BUSINESS_OPA_URL", "http://business-opa:8181")
    unleash_url: str = env("UNLEASH_URL", "http://unleash:4242")
    unleash_token: str = env("UNLEASH_ADMIN_TOKEN", "*:*.range-admin")
    unleash_project: str = env("UNLEASH_PROJECT", "default")
    unleash_environment: str = env("UNLEASH_ENVIRONMENT", "development")

    odoo_url: str = env("ODOO_URL", "http://odoo:8069")
    odoo_database: str = env("ODOO_DATABASE", "business")
    odoo_user: str = env("ODOO_USER", "range-admin")
    odoo_password: str = env("ODOO_PASSWORD", "KeplerV2-Training-Odoo-Admin")

    ghost_url: str = env("GHOST_INTERNAL_URL", "http://ghost:2368")
    ghost_host: str = env("GHOST_HOST", "status.keplerops.lab")
    ghost_origin: str = env("GHOST_ORIGIN", "https://status.keplerops.lab")
    ghost_user: str = env("GHOST_USER", "communications@keplerops.lab")
    ghost_password: str = env("GHOST_PASSWORD", "Gv7!qL2@nP9#xR4%wT8&mK3")

    mautic_url: str = env("MAUTIC_INTERNAL_URL", "https://advisories.keplerops.lab")
    mautic_user: str = env("MAUTIC_USER", "range-admin")
    mautic_password: str = env("MAUTIC_PASSWORD", "KeplerV2-Training-Mautic")

    zammad_url: str = env("ZAMMAD_URL", "http://zammad-nginx:8080")
    zammad_host: str = env("ZAMMAD_HOST", "support.keplerops.lab")
    zammad_user: str = env("ZAMMAD_USER", "support.analyst")
    zammad_password: str = env("ZAMMAD_PASSWORD", "KeplerV2-Training-Support")

    redmine_url: str = env("REDMINE_URL", "http://redmine:3000")
    redmine_host: str = env("REDMINE_HOST", "workhub.keplerops.lab")
    redmine_user: str = env("REDMINE_USER", "range-admin")
    redmine_password: str = env("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin")
    nextcloud_url: str = env("NEXTCLOUD_URL", "http://nextcloud")
    nextcloud_host: str = env("NEXTCLOUD_HOST", "files.keplerops.lab")
    nextcloud_user: str = env("NEXTCLOUD_USER", "range-admin")
    nextcloud_password: str = env("NEXTCLOUD_PASSWORD", "KeplerV2-Training-Nextcloud")

    rabbitmq_url: str = env("RABBITMQ_MANAGEMENT_URL", "http://rabbitmq:15672")
    rabbitmq_user: str = env("RABBITMQ_USER", "kepler")
    rabbitmq_password: str = env("RABBITMQ_PASSWORD", "KeplerV2-Training-Rabbit")
    rabbitmq_vhost: str = env("RABBITMQ_VHOST", "keplerops")
    qdrant_url: str = env("QDRANT_URL", "http://qdrant-writer:6333")

    lakefs_url: str = env("LAKEFS_URL", "http://lakefs:8000")
    lakefs_access_key: str = env("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess")
    lakefs_secret_key: str = env(
        "LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key"
    )
    lakefs_repository: str = env("LAKEFS_REPOSITORY", "orion")

    smtp_host: str = env("SMTP_HOST", "stalwart")
    smtp_port: int = int(env("SMTP_PORT", "587"))
    smtp_billing_user: str = env("SMTP_BILLING_USER", "billing")
    smtp_billing_password: str = env(
        "SMTP_BILLING_PASSWORD", "KeplerV2-Training-Synthetic-Business"
    )
    smtp_support_user: str = env("SMTP_SUPPORT_USER", "support.analyst")
    smtp_support_password: str = env(
        "SMTP_SUPPORT_PASSWORD", "KeplerV2-Training-Support"
    )

    def release_identity(self, family: str) -> tuple[str, str, str]:
        if family == "release-risk":
            return (
                self.release_risk_release_id,
                self.release_risk_model_digest,
                self.release_risk_image_digest,
            )
        if family == "assistant":
            return (
                self.assistant_release_id,
                self.assistant_model_digest,
                self.assistant_image_digest,
            )
        raise ValueError(f"unsupported Orion model family: {family}")


settings = Settings()
