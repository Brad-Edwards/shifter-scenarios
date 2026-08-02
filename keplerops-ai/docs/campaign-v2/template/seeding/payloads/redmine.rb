# frozen_string_literal: true

Setting.rest_api_enabled = '1'
Setting.default_language = 'en'

users = [
  {
    login: 'range-admin', firstname: 'Platform', lastname: 'Operations',
    mail: 'platform.operations@keplerops.lab', password: ENV.fetch('REDMINE_SEED_ADMIN_PASSWORD'), admin: true
  },
  {
    login: 'reviewer', firstname: 'Rina', lastname: 'Chen',
    mail: 'reviewer@keplerops.lab', password: ENV.fetch('REDMINE_SEED_REVIEWER_PASSWORD')
  },
  {
    login: 'ml.engineer', firstname: 'Maya', lastname: 'Ortiz',
    mail: 'ml.engineer@keplerops.lab', password: ENV.fetch('REDMINE_SEED_ML_PASSWORD')
  },
  {
    login: 'release.engineer', firstname: 'Elliot', lastname: 'Park',
    mail: 'release.engineer@keplerops.lab', password: ENV.fetch('REDMINE_SEED_RELEASE_PASSWORD')
  },
  {
    login: 'comms.publisher', firstname: 'Samira', lastname: 'Okafor',
    mail: 'communications@keplerops.lab', password: ENV.fetch('REDMINE_SEED_COMMS_PASSWORD')
  },
  {
    login: 'support.analyst', firstname: 'Jonas', lastname: 'Becker',
    mail: 'support@keplerops.lab', password: ENV.fetch('REDMINE_SEED_SUPPORT_PASSWORD')
  }
]

seeded_users = users.to_h do |attributes|
  password = attributes.delete(:password)
  user = User.find_or_initialize_by(login: attributes.fetch(:login))
  user.assign_attributes(attributes)
  user.status = User::STATUS_ACTIVE
  user.mail_notification = 'none'
  user.password = password
  user.password_confirmation = password
  user.must_change_passwd = false if user.respond_to?(:must_change_passwd=)
  user.save!
  [user.login, user]
end

project = Project.find_or_initialize_by(identifier: 'orion')
project.name = 'Project Orion'
project.description = 'Internal planning and delivery project for the Orion product line.'
project.is_public = false
project.inherit_members = false
project.save!
project.enabled_module_names = %w[issue_tracking time_tracking news documents files wiki calendar gantt]
project.trackers = Tracker.all
project.save!

role_by_login = {
  'reviewer' => 'Reporter',
  'ml.engineer' => 'Developer',
  'release.engineer' => 'Manager',
  'comms.publisher' => 'Reporter',
  'support.analyst' => 'Reporter'
}

Member.where(project: project, user: seeded_users.fetch('range-admin')).destroy_all

role_by_login.each do |login, role_name|
  role = Role.find_by(name: role_name) || raise("Redmine role is missing: #{role_name}")
  member = Member.find_or_initialize_by(project: project, user: seeded_users.fetch(login))
  member.roles = [role]
  member.save!
end

puts "Seeded Redmine project #{project.identifier} with #{seeded_users.length} users"
