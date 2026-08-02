# frozen_string_literal: true

UserInfo.current_user_id = 1

admin_role = Role.find_by(name: 'Admin') || raise('Zammad Admin role is missing')
agent_role = Role.find_by(name: 'Agent') || raise('Zammad Agent role is missing')
customer_role = Role.find_by(name: 'Customer') || raise('Zammad Customer role is missing')

# SAML authenticates the user; Zammad remains authoritative for authorization.
users = [
  {
    login: 'range-admin', firstname: 'Range', lastname: 'Administrator',
    email: 'range-admin@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_ADMIN_PASSWORD'), roles: [admin_role, agent_role]
  },
  {
    login: 'reviewer', firstname: 'Rina', lastname: 'Chen',
    email: 'reviewer@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_REVIEWER_PASSWORD'), roles: [customer_role]
  },
  {
    login: 'ml.engineer', firstname: 'Maya', lastname: 'Ortiz',
    email: 'ml.engineer@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_ML_PASSWORD'), roles: [customer_role]
  },
  {
    login: 'release.engineer', firstname: 'Elliot', lastname: 'Park',
    email: 'release.engineer@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_RELEASE_PASSWORD'), roles: [customer_role]
  },
  {
    login: 'comms.publisher', firstname: 'Samira', lastname: 'Okafor',
    email: 'comms.publisher@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_COMMS_PASSWORD'), roles: [customer_role]
  },
  {
    login: 'support.analyst', firstname: 'Jonas', lastname: 'Becker',
    email: 'support.analyst@keplerops.lab', password: ENV.fetch('ZAMMAD_SEED_SUPPORT_PASSWORD'), roles: [agent_role]
  }
]

seeded_users = users.to_h do |attributes|
  password = attributes.delete(:password)
  roles = attributes.delete(:roles)
  user = User.find_or_initialize_by(login: attributes.fetch(:login))
  user.assign_attributes(attributes)
  user.active = true
  user.login_failed = 0
  user.password = password
  user.save!
  user.roles = roles
  user.save!
  [user.login, user]
end

group = Group.find_or_initialize_by(name: 'Orion Support')
group.note = 'Support queue for routine Project Orion requests.'
group.active = true
group.save!

%w[range-admin support.analyst].each do |login|
  membership = UserGroup.find_or_initialize_by(user_id: seeded_users.fetch(login).id, group_id: group.id)
  membership.access = 'full'
  membership.save!
end
UserGroup.where(group_id: group.id)
         .where.not(user_id: seeded_users.values_at('range-admin', 'support.analyst').map(&:id))
         .destroy_all

Setting.set('fqdn', 'support.keplerops.lab')
Setting.set('http_type', 'https')
Setting.set('auth_third_party_auto_link_at_inital_login', true)
Setting.set('auth_saml_credentials', {
              display_name: 'KeplerOps identity',
              idp_sso_target_url: ENV.fetch('ZAMMAD_SAML_IDP_URL'),
              idp_slo_service_url: ENV.fetch('ZAMMAD_SAML_IDP_URL'),
              idp_cert: ENV.fetch('ZAMMAD_SAML_IDP_CERTIFICATE'),
              idp_cert_fingerprint: '',
              name_identifier_format: 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
              uid_attribute: 'email'
            })
Setting.set('auth_saml', true)
Setting.set('system_init_done', true)
Rails.cache.clear

puts "Seeded Zammad SAML and native access for #{seeded_users.length} users"
