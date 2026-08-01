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

env["ir.config_parameter"].sudo().set_param("web.base.url", "https://business.keplerops.lab")
env.cr.commit()
print("Seeded Odoo company and administrator")
