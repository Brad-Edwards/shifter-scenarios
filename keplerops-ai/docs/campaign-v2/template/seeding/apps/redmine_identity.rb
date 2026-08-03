# frozen_string_literal: true

require 'net/ldap'
require 'openssl'

ldap_host = ENV.fetch('REDMINE_SEED_LDAP_HOST')
ldap_port = Integer(ENV.fetch('REDMINE_SEED_LDAP_PORT', '636'), 10)
users_dn = ENV.fetch('REDMINE_SEED_LDAP_USERS_DN')
groups_dn = ENV.fetch('REDMINE_SEED_LDAP_GROUPS_DN')

role_mappings = {
  'RG-WorkHub-Orion' => {
    role: 'Orion Reader',
    source_role: nil,
    permissions: %i[
      view_issues save_queries view_gantt view_calendar view_time_entries
      view_news view_documents view_wiki_pages view_wiki_edits view_messages
      view_files browse_repository view_changesets
    ]
  },
  'GG-Orion-Researchers' => {
    role: 'Orion Researcher', source_role: 'Developer'
  },
  'GG-Orion-Evaluators' => {
    role: 'Orion Reviewer', source_role: 'Reporter'
  },
  'GG-Release-Engineers' => {
    role: 'Orion Release Manager', source_role: 'Manager'
  }
}.freeze

staff = {
  'reviewer' => ['Rina', 'Chen'],
  'ml.engineer' => ['Maya', 'Ortiz'],
  'data.annotator' => ['Imani', 'Brooks'],
  'release.engineer' => ['Elliot', 'Park'],
  'release.approver' => ['Priya', 'Nair'],
  'platform.operator' => ['Luca', 'Bianchi'],
  'support.analyst' => ['Jonas', 'Becker'],
  'comms.publisher' => ['Samira', 'Okafor'],
  'finance.operator' => ['Hana', 'Suzuki'],
  'security.auditor' => ['Darius', 'Cole']
}.freeze

workhub_group_dn = "CN=RG-WorkHub-Orion,#{groups_dn}"
auth_source = AuthSourceLdap.find_or_initialize_by(name: 'KeplerOps Active Directory')
auth_source.assign_attributes(
  host: ldap_host,
  port: ldap_port,
  account: ENV.fetch('REDMINE_SEED_LDAP_USER_BIND'),
  account_password: '',
  base_dn: users_dn,
  attr_login: 'sAMAccountName',
  attr_firstname: 'givenName',
  attr_lastname: 'sn',
  attr_mail: 'mail',
  onthefly_register: false,
  tls: true,
  verify_peer: true,
  timeout: 5,
  filter: "(&(objectCategory=person)(objectClass=user)(memberOf=#{workhub_group_dn}))"
)
auth_source.save!

ldap = Net::LDAP.new(
  host: ldap_host,
  port: ldap_port,
  encryption: {
    method: :simple_tls,
    tls_options: {verify_mode: OpenSSL::SSL::VERIFY_PEER}
  },
  auth: {
    method: :simple,
    username: ENV.fetch('REDMINE_SEED_LDAP_SYNC_BIND_DN'),
    password: ENV.fetch('REDMINE_SEED_LDAP_SYNC_BIND_PASSWORD')
  }
)
raise 'Redmine provisioning adapter could not bind to Active Directory' unless ldap.bind

directory_users = {}
group_logins = role_mappings.to_h do |group_name, _mapping|
  group_dn = "CN=#{group_name},#{groups_dn}"
  group_entry = ldap.search(
    base: groups_dn,
    filter: Net::LDAP::Filter.eq('cn', group_name),
    attributes: %w[cn]
  )
  unless group_entry&.any?
    raise "Required Active Directory group is missing: #{group_name}"
  end

  filter = Net::LDAP::Filter.eq('objectClass', 'user') &
           Net::LDAP::Filter.eq('memberOf', group_dn)
  logins = []
  search_result = ldap.search(
    base: users_dn,
    filter: filter,
    attributes: %w[sAMAccountName givenName sn mail]
  ) do |entry|
    login = entry[:sAMAccountName].first.to_s.downcase
    next if login.empty?

    directory_users[login] = {
      firstname: entry[:givenName].first.to_s,
      lastname: entry[:sn].first.to_s,
      mail: entry[:mail].first.to_s
    }
    logins << login
  end
  unless search_result
    message = ldap.get_operation_result.message
    raise "Active Directory group query failed for #{group_name}: #{message}"
  end
  [group_name, logins.uniq.sort]
end

ensure_user = lambda do |login, attributes|
  fallback_names = staff.fetch(login, [login, 'User'])
  firstname = attributes[:firstname].presence || fallback_names.first
  lastname = attributes[:lastname].presence || fallback_names.last
  mail = attributes[:mail].presence || "#{login}@keplerops.lab"
  user = User.find_or_initialize_by(login: login)
  user.assign_attributes(
    firstname: firstname,
    lastname: lastname,
    mail: mail,
    admin: false,
    status: User::STATUS_ACTIVE,
    auth_source: auth_source,
    mail_notification: 'none'
  )
  user.must_change_passwd = false if user.respond_to?(:must_change_passwd=)
  user.save!
  user
end

staff.each do |login, names|
  directory_users[login] ||= {
    firstname: names.first,
    lastname: names.last,
    mail: "#{login}@keplerops.lab"
  }
end
users_by_login = directory_users.to_h do |login, attributes|
  [login, ensure_user.call(login, attributes)]
end

roles = role_mappings.to_h do |_group_name, mapping|
  role = Role.find_or_initialize_by(name: mapping.fetch(:role))
  source_role_name = mapping[:source_role]
  if source_role_name
    source_role = Role.find_by(name: source_role_name) ||
                  raise("Redmine role is missing: #{source_role_name}")
    role.assign_attributes(
      assignable: source_role.assignable,
      issues_visibility: source_role.issues_visibility,
      users_visibility: source_role.users_visibility,
      time_entries_visibility: source_role.time_entries_visibility,
      permissions: source_role.permissions
    )
  else
    role.assign_attributes(
      assignable: true,
      issues_visibility: 'all',
      users_visibility: 'members_of_visible_projects',
      time_entries_visibility: 'all',
      permissions: mapping.fetch(:permissions)
    )
  end
  role.save!
  if source_role_name
    WorkflowRule.copy(nil, source_role, nil, role)
  else
    WorkflowRule.where(role_id: role.id).delete_all
  end
  [mapping.fetch(:role), role]
end

project = Project.find_by(identifier: 'orion') || raise('Redmine Orion project is missing')
role_mappings.each do |group_name, mapping|
  group = Group.find_or_initialize_by(lastname: group_name)
  group.save!
  desired_users = group_logins.fetch(group_name).map do |login|
    users_by_login.fetch(login)
  end
  group.users = desired_users

  member = Member.find_or_initialize_by(project: project, user_id: group.id)
  member.roles = [roles.fetch(mapping.fetch(:role))]
  member.save!
end

users_by_login.each_value do |user|
  member = Member.find_by(project: project, user_id: user.id)
  next unless member

  member.member_roles.where(inherited_from: nil).destroy_all
  member.destroy if member.persisted? && member.roles.reload.empty?
end

puts "Reconciled Redmine LDAP source and #{role_mappings.length} Orion role mappings"
