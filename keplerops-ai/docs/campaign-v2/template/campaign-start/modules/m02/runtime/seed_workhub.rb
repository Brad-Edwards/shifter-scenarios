# frozen_string_literal: true

project = Project.find_or_initialize_by(identifier: 'orion-package-review')
project.name = 'Orion Package Documentation Review'
project.description = 'Private, bounded records for the disposable documentation-review workstation.'
project.is_public = false
project.inherit_members = false
project.save!
project.enabled_module_names = %w[issue_tracking]

tracker = Tracker.find_or_create_by!(name: 'Package Documentation Review')
project.trackers = (project.trackers + [tracker]).uniq
project.save!

reviewer = User.find_or_initialize_by(login: 'orion.package-review')
reviewer.firstname = 'Orion'
reviewer.lastname = 'Package Reviewer'
reviewer.mail = 'orion.package-review@keplerops.lab'
reviewer.status = User::STATUS_ACTIVE
reviewer.admin = false
reviewer.password = ENV.fetch('M02_WORKHUB_REVIEW_PASSWORD')
reviewer.password_confirmation = ENV.fetch('M02_WORKHUB_REVIEW_PASSWORD')
reviewer.must_change_passwd = false if reviewer.respond_to?(:must_change_passwd=)
reviewer.save!

reporter = Role.find_by(name: 'Reporter') || raise('Reporter role is missing')
membership = Member.find_or_initialize_by(project: project, user: reviewer)
membership.roles = [reporter]
membership.save!

clue = Issue.find_or_initialize_by(project: project, subject: 'Disposable documentation reviewer scope')
clue.tracker = tracker
clue.author = reviewer
clue.status = IssueStatus.where(is_closed: false).order(:position).first
clue.description = 'This identity can read and create records only in this private package-documentation review project. A completed review receives its own ordinary issue.'
clue.save!

puts JSON.generate(project: project.identifier, reviewer: reviewer.login, clue_issue_id: clue.id)
