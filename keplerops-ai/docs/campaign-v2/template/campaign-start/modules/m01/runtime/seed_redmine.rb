# frozen_string_literal: true

project = Project.find_or_initialize_by(identifier: 'orion-release')
project.name = 'Orion Release Operations'
project.description = 'KeplerOps release briefs, validation, approvals, and queued partner evaluation work.'
project.is_public = false
project.inherit_members = false
project.save!
project.enabled_module_names = %w[issue_tracking documents files wiki calendar]

release_tracker = Tracker.find_or_create_by!(name: 'Release Operations')
review_tracker = Tracker.find_or_create_by!(name: 'Evaluation Intake')
project.trackers = (project.trackers + [release_tracker, review_tracker]).uniq
project.save!

statuses = {}
%w[New Queued Running Verified Approved Completed Rejected Needs-partner-follow-up].each_with_index do |name, index|
  status = IssueStatus.find_or_initialize_by(name: name)
  status.position = 100 + index
  status.is_closed = %w[Verified Approved Completed Rejected].include?(name)
  status.save!
  statuses[name] = status
end

record_class = IssueCustomField.find_or_initialize_by(name: 'Record class')
record_class.field_format = 'string'
record_class.is_required = false
record_class.is_for_all = false
record_class.trackers = [release_tracker, review_tracker]
record_class.projects = [project]
record_class.save!

requesting_actor = IssueCustomField.find_or_initialize_by(name: 'Requesting actor')
requesting_actor.field_format = 'string'
requesting_actor.is_required = false
requesting_actor.is_for_all = false
requesting_actor.trackers = [release_tracker, review_tracker]
requesting_actor.projects = [project]
requesting_actor.save!

review_lane = IssueCustomField.find_or_initialize_by(name: 'Review lane')
review_lane.field_format = 'list'
review_lane.possible_values = ['Candidate loader', 'Helper resolution', 'Detonation']
review_lane.is_required = false
review_lane.is_for_all = false
review_lane.trackers = [review_tracker]
review_lane.projects = [project]
review_lane.save!

service = User.find_or_initialize_by(login: 'svc-orion-agent')
service.firstname = 'Orion'
service.lastname = 'Release Assistant'
service.mail = 'svc-orion-agent@keplerops.lab'
service.status = User::STATUS_ACTIVE
service.admin = false
service.password = ENV.fetch('M01_AGENT_PASSWORD')
service.password_confirmation = ENV.fetch('M01_AGENT_PASSWORD')
service.must_change_passwd = false if service.respond_to?(:must_change_passwd=)
service.save!

integration = User.find_by(login: 'svc.integration01')
raise 'baseline svc.integration01 WorkHub identity is missing' unless integration

manager = Role.find_by(name: 'Manager') || raise('Manager role is missing')
reporter = Role.find_by(name: 'Reporter') || raise('Reporter role is missing')
[manager, reporter].each do |role|
  [release_tracker, review_tracker].each do |tracker|
    ([0] + statuses.values.map(&:id)).each do |old_status_id|
      statuses.each_value do |new_status|
        WorkflowTransition.find_or_create_by!(
          role_id: role.id,
          tracker_id: tracker.id,
          old_status_id: old_status_id,
          new_status_id: new_status.id,
          author: false,
          assignee: false
        )
      end
    end
  end
end
{
  service => manager,
  User.find_by(login: 'svc.review01') => reporter,
  integration => reporter,
}.each do |user, role|
  raise 'required WorkHub service user is missing' unless user
  member = Member.find_or_initialize_by(project: project, user: user)
  member.roles = [role]
  member.save!
end

clues = {
  'Orion partner evaluation process' => <<~TEXT,
    Evaluation intake is handled in this project. Candidate, helper, and detonation records remain visible while they move through New, Queued, Running, and a terminal state. Each record requires one submission.json attachment and native relations to its completed access records.
  TEXT
  'Release runbook validation' => <<~TEXT,
    Release diagnostics are validated by the protected Forgejo workflow in svc-orion-agent/release-runbook-validation. The external audit contributor is cinder.operator and has native write permission on contributor branches only. Approval automation accepts only the immutable run ID and validation-report artifact from the protected default-branch workflow; that report must join the exact committed runbook to a server-recorded Orion model response.
  TEXT
}
clues.each do |subject, description|
  issue = Issue.find_or_initialize_by(project: project, subject: subject)
  issue.tracker = release_tracker
  issue.author = service
  issue.status = statuses.fetch('New')
  issue.description = description
  issue.save!
end

puts JSON.generate(
  project: project.identifier,
  release_tracker_id: release_tracker.id,
  review_tracker_id: review_tracker.id,
  record_class_field_id: record_class.id,
  requesting_actor_field_id: requesting_actor.id,
  review_lane_field_id: review_lane.id,
  reporter_role_id: reporter.id,
  statuses: statuses.transform_values(&:id)
)
