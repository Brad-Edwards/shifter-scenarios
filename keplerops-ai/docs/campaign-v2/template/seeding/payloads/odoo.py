company = env.ref("base.main_company")
company.write({
    "name": "Kepler Operations GmbH",
    "email": "operations@keplerops.lab",
    "phone": "+49 30 5550 6100",
    "website": "https://www.keplerops.lab",
})

admin = env.ref("base.user_admin")
admin.write({
    "name": "Range Administrator",
    "login": "range-admin",
    "email": "range-admin@keplerops.lab",
    "password": __import__("os").environ["ODOO_SEED_ADMIN_PASSWORD"],
})

customer = env["res.partner"].search([("ref", "=", "KAI-CUSTOMER-001")], limit=1)
customer_values = {
    "name": "Acme Labs Synthetic Subsidiary",
    "ref": "KAI-CUSTOMER-001",
    "email": "billing.customer@keplerops.lab",
    "customer_rank": 1,
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

env["ir.config_parameter"].sudo().set_param("web.base.url", "https://business.keplerops.lab")
env.cr.commit()
print("Seeded Odoo company, administrator, synthetic customer, and service product")
