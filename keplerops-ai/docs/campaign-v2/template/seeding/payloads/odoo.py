import os


def ensure_group(name, category, implied_groups):
    group = env["res.groups"].search(
        [("name", "=", name), ("category_id", "=", category.id)], limit=1
    )
    values = {
        "name": name,
        "category_id": category.id,
        "implied_ids": [(6, 0, [item.id for item in implied_groups])],
    }
    if group:
        group.write(values)
    else:
        group = env["res.groups"].create(values)
    return group


def ensure_rule(name, model_name, group, domain, permissions):
    model = env["ir.model"]._get(model_name)
    rule = env["ir.rule"].search(
        [("name", "=", name), ("model_id", "=", model.id)], limit=1
    )
    values = {
        "name": name,
        "model_id": model.id,
        "domain_force": domain,
        "groups": [(6, 0, [group.id])],
        "global": False,
        "active": True,
        "perm_read": permissions["read"],
        "perm_write": permissions["write"],
        "perm_create": permissions["create"],
        "perm_unlink": permissions["unlink"],
    }
    if rule:
        rule.write(values)
    else:
        rule = env["ir.rule"].create(values)
    return rule


def ensure_user(login, name, email, password, oauth_uid, provider, group, company):
    user = env["res.users"].with_context(active_test=False).search(
        [("login", "=", login)], limit=1
    )
    values = {
        "name": name,
        "login": login,
        "email": email,
        "password": password,
        "active": True,
        "share": False,
        "company_id": company.id,
        "company_ids": [(6, 0, [company.id])],
        "groups_id": [(6, 0, [group.id])],
        "oauth_provider_id": provider.id,
        "oauth_uid": oauth_uid,
    }
    if user:
        user.write(values)
    else:
        user = env["res.users"].create(values)
    return user


company = env.ref("base.main_company")
company.write(
    {
        "name": "Kepler Operations GmbH",
        "email": "operations@keplerops.lab",
        "phone": "+49 30 5550 6100",
        "website": "https://www.keplerops.lab",
    }
)

admin = env.ref("base.user_admin")
admin.write(
    {
        "name": "Range Administrator",
        "login": "range-admin",
        "email": "range-admin@keplerops.lab",
        "password": os.environ["ODOO_SEED_ADMIN_PASSWORD"],
    }
)

provider = env["auth.oauth.provider"].search(
    [("client_id", "=", os.environ["ODOO_OIDC_CLIENT_ID"])], limit=1
)
realm = os.environ["ODOO_OIDC_REALM"]
provider_values = {
    "name": "KeplerOps Identity",
    "client_id": os.environ["ODOO_OIDC_CLIENT_ID"],
    "client_secret": os.environ["ODOO_OIDC_CLIENT_SECRET"],
    "auth_endpoint": (
        f"https://id.keplerops.lab/realms/{realm}/protocol/openid-connect/auth"
    ),
    "token_endpoint": (
        f"http://10.61.20.20:8080/realms/{realm}/protocol/openid-connect/token"
    ),
    "jwks_uri": f"http://10.61.20.20:8080/realms/{realm}/protocol/openid-connect/certs",
    "validation_endpoint": (
        f"http://10.61.20.20:8080/realms/{realm}/protocol/openid-connect/userinfo"
    ),
    "end_session_endpoint": (
        f"https://id.keplerops.lab/realms/{realm}/protocol/openid-connect/logout"
    ),
    "scope": "openid email profile",
    "flow": "id_token_code",
    "body": "Log in with KeplerOps Identity",
    "css_class": "fa fa-fw fa-sign-in text-primary",
    "enabled": True,
    "sequence": 1,
}
if provider:
    provider.write(provider_values)
else:
    provider = env["auth.oauth.provider"].create(provider_values)

category = env["ir.module.category"].search(
    [("name", "=", "KeplerOps Business Roles")], limit=1
)
if not category:
    category = env["ir.module.category"].create(
        {
            "name": "KeplerOps Business Roles",
            "description": "Native business application duties for the KeplerOps range.",
            "sequence": 8,
        }
    )

base_user = env.ref("base.group_user")
invoice_group = env.ref("account.group_account_invoice")
readonly_group = env.ref("account.group_account_readonly")
operator_group = ensure_group(
    "KeplerOps Finance Operator", category, [base_user, invoice_group]
)
auditor_group = ensure_group(
    "KeplerOps Finance Auditor", category, [base_user, readonly_group]
)

company_domain = "[('company_id', '=', %d)]" % company.id
ensure_rule(
    "KeplerOps finance operator company boundary",
    "account.move",
    operator_group,
    company_domain,
    {"read": True, "write": True, "create": True, "unlink": True},
)
ensure_rule(
    "KeplerOps finance auditor company boundary",
    "account.move",
    auditor_group,
    company_domain,
    {"read": True, "write": False, "create": False, "unlink": False},
)

finance_user = ensure_user(
    "finance.operator",
    "Hana Suzuki",
    "finance.operator@keplerops.lab",
    os.environ["ODOO_FINANCE_PASSWORD"],
    os.environ["ODOO_FINANCE_SUBJECT"],
    provider,
    operator_group,
    company,
)
auditor_user = ensure_user(
    "security.auditor",
    "Darius Cole",
    "security.auditor@keplerops.lab",
    os.environ["ODOO_AUDITOR_PASSWORD"],
    os.environ["ODOO_AUDITOR_SUBJECT"],
    provider,
    auditor_group,
    company,
)

customer = env["res.partner"].search([("ref", "=", "KAI-CUSTOMER-001")], limit=1)
customer_values = {
    "name": "Acme Labs Synthetic Subsidiary",
    "ref": "KAI-CUSTOMER-001",
    "email": "billing.customer@keplerops.lab",
    "customer_rank": 1,
    "company_id": company.id,
}
if customer:
    customer.write(customer_values)
else:
    customer = env["res.partner"].create(customer_values)

product = env["product.product"].search(
    [("default_code", "=", "ORION-SERVICE-CREDIT")], limit=1
)
product_values = {
    "name": "Orion Service Adjustment",
    "default_code": "ORION-SERVICE-CREDIT",
    "list_price": 125.0,
    "standard_price": 0.0,
    "taxes_id": [(6, 0, [])],
    "supplier_taxes_id": [(6, 0, [])],
}
if product:
    product.write(product_values)
else:
    product = env["product.product"].create(product_values)

config = env["ir.config_parameter"].sudo()
config.set_param("web.base.url", "https://business.keplerops.lab")
config.set_param("web.base.url.freeze", "True")
config.set_param("auth_signup.allow_uninvited", "False")

assert provider.flow == "id_token_code"
assert finance_user.oauth_uid == os.environ["ODOO_FINANCE_SUBJECT"]
assert auditor_user.oauth_uid == os.environ["ODOO_AUDITOR_SUBJECT"]
assert invoice_group in operator_group.implied_ids
assert readonly_group in auditor_group.implied_ids
assert not operator_group.users.filtered(lambda user: user.login == "security.auditor")

env.cr.commit()
print("Seeded Odoo OIDC provider, native role groups, record rules, and business data")
