require "digest"
require "json"
require "net/http"
require "uri"
require "yaml"

COMPANY_STATE_PATH = "/opt/keplerops/company-state.yaml"
GITEA_READBACK_PATH = "/data/gitea/company-state-gitea-readback.json"
WORKHUB_READBACK_PATH = "/usr/src/redmine/sqlite/company-workhub-readback.json"
REDMINE_TOKEN_PATH = "/usr/src/redmine/sqlite/platform-context-redmine-key"
OWNER_PREFIX = "keplerops-company-state"
GITEA_BASE = URI("http://127.0.0.1:3000")
REDMINE_BASE = URI("http://127.0.0.1:3001")
GITEA_USER = "ml.engineer"
GITEA_PASSWORD = "KeplerOps-Engineer-355!" # NOSONAR - synthetic training credential
STATUS_NAMES = {
  "open" => "New",
  "in-review" => "Feedback",
  "closed" => "Closed",
  "abandoned" => "Rejected"
}.freeze

def load_company_state
  value = YAML.safe_load(
    File.read(COMPANY_STATE_PATH, encoding: "UTF-8"),
    permitted_classes: [],
    permitted_symbols: [],
    aliases: false
  )
  abort "company-state manifest must be a mapping" unless value.is_a?(Hash)
  value
rescue Psych::Exception => error
  abort "company-state manifest is invalid: #{error.message}"
end

def owner_marker(object_id)
  "KeplerOps-State-ID: #{OWNER_PREFIX}:#{object_id}"
end

def ensure_challenge_redmine_state
  project = Project.find_or_create_by!(identifier: "keplerops-model-release") do |item|
    item.name = "KeplerOps model release"
  end
  project.update!(is_public: true)
  tracker = Tracker.first
  project.trackers << tracker unless project.trackers.include?(tracker)
  anonymous = Role.anonymous
  anonymous.add_permission!(:view_issues) unless anonymous.has_permission?(:view_issues)
  anonymous.add_permission!(:add_issues) unless anonymous.has_permission?(:add_issues)
  Setting.rest_api_enabled = "1"
  api_user = User.find_by!(login: "admin")
  api_token = Token.find_or_create_by!(user: api_user, action: "api")
  File.write(REDMINE_TOKEN_PATH, api_token.value + "\n", mode: "w", perm: 0o600)
  File.chmod(0o600, REDMINE_TOKEN_PATH)
  Issue.find_or_create_by!(project: project, subject: "Evaluate student adapter") do |item|
    item.tracker = tracker
    item.priority = IssuePriority.default
    item.author = User.active.first
  end
end

def ensure_redmine_user(row)
  display_parts = row.fetch("display_name").split(" ", 2)
  expected = {
    firstname: display_parts.fetch(0),
    lastname: display_parts.fetch(1, "."),
    mail: row.fetch("email")
  }
  user = User.find_by(login: row.fetch("username"))
  if user
    observed = {firstname: user.firstname, lastname: user.lastname, mail: user.mail}
    abort "Redmine user #{row.fetch("username")} collision does not match company identity" unless observed == expected
    return user
  end

  user = User.new(
    login: row.fetch("username"),
    firstname: expected.fetch(:firstname),
    lastname: expected.fetch(:lastname),
    mail: expected.fetch(:mail),
    status: Principal::STATUS_ACTIVE
  )
  user.generate_password = true
  user.save!
  user
end

def project_description(row)
  [
    owner_marker(row.fetch("id")),
    "Owner team: #{row.fetch("owner_team_ref")}",
    "Represented start: #{row.fetch("started_at")}"
  ].join("\n")
end

def ensure_company_project(row, tracker)
  identifier = row.fetch("id")
  project = Project.find_by(identifier: identifier)
  if project && !project.description.to_s.include?(owner_marker(identifier))
    abort "Redmine project #{identifier} is an unowned collision"
  end
  project ||= Project.new(identifier: identifier)
  project.assign_attributes(
    name: row.fetch("name"),
    description: project_description(row),
    is_public: false,
    status: Project::STATUS_ACTIVE
  )
  project.save!
  project.trackers << tracker unless project.trackers.include?(tracker)
  represented_time = Time.iso8601(row.fetch("started_at"))
  project.update_columns(created_on: represented_time, updated_on: represented_time)
  project
end

def ticket_subject(row, commits)
  summaries = row.fetch("commit_refs").map { |commit_ref| commits.fetch(commit_ref).fetch("summary") }
  detail = if summaries.empty?
             "Review #{row.fetch("dataset_refs").join(", ")}"
           else
             summaries.join("; ")
           end
  "#{row.fetch("key")}: #{detail}"
end

def ticket_description(row, commits)
  commit_lines = row.fetch("commit_refs").map do |commit_ref|
    commit = commits.fetch(commit_ref)
    "#{commit.fetch("revision")} (#{commit_ref})"
  end
  [
    owner_marker(row.fetch("id")),
    "Stable key: #{row.fetch("key")}",
    "Commit refs: #{commit_lines.empty? ? "none" : commit_lines.join(", ")}",
    "Dataset refs: #{row.fetch("dataset_refs").empty? ? "none" : row.fetch("dataset_refs").join(", ")}",
    "Model refs: #{row.fetch("model_refs").empty? ? "none" : row.fetch("model_refs").join(", ")}",
    "Represented state: #{row.fetch("status")}"
  ].join("\n")
end

def ensure_company_ticket(row, projects, users, commits, statuses, tracker)
  marker = owner_marker(row.fetch("id"))
  matches = Issue.where("description LIKE ?", "%#{ActiveRecord::Base.sanitize_sql_like(marker)}%").to_a
  abort "Redmine ticket #{row.fetch("id")} has duplicate owned objects" if matches.length > 1

  expected_subject = ticket_subject(row, commits)
  Issue.where("subject LIKE ?", "#{row.fetch("key")}: %").where.not(id: matches.map(&:id)).find_each do
    abort "Redmine ticket #{row.fetch("key")} is an unowned collision"
  end

  issue = matches.first || Issue.new
  issue.assign_attributes(
    project: projects.fetch(row.fetch("project_ref")),
    tracker: tracker,
    priority: IssuePriority.default,
    author: users.fetch(row.fetch("assignee_ref")),
    assigned_to: users.fetch(row.fetch("assignee_ref")),
    subject: expected_subject,
    description: ticket_description(row, commits),
    status: statuses.fetch(row.fetch("status")),
    done_ratio: row.fetch("status") == "closed" ? 100 : 0
  )
  issue.save!
  created_at = Time.iso8601(row.fetch("created_at"))
  updated_at = Time.iso8601(row.fetch("updated_at"))
  issue.update_columns(
    created_on: created_at,
    updated_on: updated_at,
    closed_on: row.fetch("status") == "closed" ? updated_at : nil
  )
  issue
end

def apply_represented_ticket_times(rows)
  rows.each do |row|
    marker = owner_marker(row.fetch("id"))
    issue = Issue.find_by!("description LIKE ?", "%#{ActiveRecord::Base.sanitize_sql_like(marker)}%")
    created_at = Time.iso8601(row.fetch("created_at"))
    updated_at = Time.iso8601(row.fetch("updated_at"))
    Issue.where(id: issue.id).update_all(
      created_on: created_at,
      updated_on: updated_at,
      closed_on: row.fetch("status") == "closed" ? updated_at : nil
    )
  end
end

def materialize_company_state(manifest)
  ensure_challenge_redmine_state
  tracker = Tracker.first || abort("Redmine default tracker is missing")
  statuses = STATUS_NAMES.to_h do |state, name|
    [state, IssueStatus.find_by(name: name) || abort("Redmine status #{name} is missing")]
  end
  users = manifest.fetch("people").to_h do |row|
    [row.fetch("id"), ensure_redmine_user(row)]
  end
  projects = manifest.fetch("projects").to_h do |row|
    [row.fetch("id"), ensure_company_project(row, tracker)]
  end
  commits = manifest.fetch("commits").to_h { |row| [row.fetch("id"), row] }
  manifest.fetch("tickets").each do |row|
    ensure_company_ticket(row, projects, users, commits, statuses, tracker)
  end
  apply_represented_ticket_times(manifest.fetch("tickets"))
end

def http_json(base, path, token: nil, basic_auth: nil)
  uri = base + path
  request = Net::HTTP::Get.new(uri)
  request["X-Redmine-API-Key"] = token if token
  request.basic_auth(*basic_auth) if basic_auth
  response = Net::HTTP.start(uri.hostname, uri.port, open_timeout: 2, read_timeout: 10) do |http|
    http.request(request)
  end
  abort "WorkHub readback #{path} failed with HTTP #{response.code}" unless response.code == "200"
  JSON.parse(response.body)
rescue JSON::ParserError => error
  abort "WorkHub readback #{path} returned invalid JSON: #{error.message}"
end

def same_timestamp?(observed, expected)
  Time.iso8601(observed).utc == Time.iso8601(expected).utc
rescue ArgumentError
  false
end

def verify_redmine_projects(manifest, token)
  manifest.fetch("projects").each do |row|
    payload = http_json(
      REDMINE_BASE,
      "/projects/#{URI.encode_www_form_component(row.fetch("id"))}.json",
      token: token
    ).fetch("project")
    valid = payload["identifier"] == row.fetch("id") &&
            payload["name"] == row.fetch("name") &&
            payload["description"] == project_description(row) &&
            payload["status"] == Project::STATUS_ACTIVE &&
            same_timestamp?(payload["created_on"], row.fetch("started_at"))
    abort "Redmine project #{row.fetch("id")} readback mismatch" unless valid
  end
end

def verify_redmine_tickets(manifest, token)
  commits = manifest.fetch("commits").to_h { |row| [row.fetch("id"), row] }
  people = manifest.fetch("people").to_h { |row| [row.fetch("id"), row] }
  projects = manifest.fetch("projects").to_h { |row| [row.fetch("id"), row] }
  observed = {}
  projects.each_key do |project_id|
    query = URI.encode_www_form(project_id: project_id, status_id: "*", limit: 100)
    payload = http_json(REDMINE_BASE, "/issues.json?#{query}", token: token)
    payload.fetch("issues").each do |issue|
      manifest.fetch("tickets").each do |row|
        observed[row.fetch("id")] = issue if issue["description"].to_s.include?(owner_marker(row.fetch("id")))
      end
    end
  end

  manifest.fetch("tickets").each do |row|
    issue = observed.fetch(row.fetch("id")) { abort "Redmine ticket #{row.fetch("id")} is absent from API readback" }
    assignee = people.fetch(row.fetch("assignee_ref"))
    valid = issue["subject"] == ticket_subject(row, commits) &&
            issue["description"].to_s.gsub("\r\n", "\n") == ticket_description(row, commits) &&
            issue.dig("project", "name") == projects.fetch(row.fetch("project_ref")).fetch("name") &&
            issue.dig("status", "name") == STATUS_NAMES.fetch(row.fetch("status")) &&
            issue.dig("assigned_to", "name") == assignee.fetch("display_name") &&
            same_timestamp?(issue["created_on"], row.fetch("created_at")) &&
            same_timestamp?(issue["updated_on"], row.fetch("updated_at"))
    abort "Redmine ticket #{row.fetch("id")} readback mismatch" unless valid
  end
end

def verify_gitea(manifest)
  seed_readback = JSON.parse(File.read(GITEA_READBACK_PATH, encoding: "UTF-8"))
  native_revisions = seed_readback.fetch("commits").to_h do |row|
    [row.fetch("id"), row.fetch("native_revision")]
  end
  repositories = manifest.fetch("repositories").to_h { |row| [row.fetch("id"), row] }
  people = manifest.fetch("people").to_h { |row| [row.fetch("id"), row] }

  manifest.fetch("repositories").each do |row|
    payload = http_json(
      GITEA_BASE,
      "/api/v1/repos/#{GITEA_USER}/#{row.fetch("slug")}",
      basic_auth: [GITEA_USER, GITEA_PASSWORD]
    )
    valid = payload["name"] == row.fetch("slug") &&
            payload.dig("owner", "login") == GITEA_USER &&
            payload["private"] == true &&
            payload["default_branch"] == row.fetch("default_branch")
    abort "Gitea repository #{row.fetch("id")} readback mismatch" unless valid
  end

  manifest.fetch("commits").each do |row|
    repository_row = repositories.fetch(row.fetch("repository_ref"))
    sha = native_revisions.fetch(row.fetch("id"))
    payload = http_json(
      GITEA_BASE,
      "/api/v1/repos/#{GITEA_USER}/#{repository_row.fetch("slug")}/git/commits/#{sha}",
      basic_auth: [GITEA_USER, GITEA_PASSWORD]
    )
    author = people.fetch(row.fetch("author_ref"))
    expected_message = [
      row.fetch("summary"),
      "",
      "KeplerOps-State-ID: #{OWNER_PREFIX}:#{row.fetch("id")}",
      "KeplerOps-Revision: #{row.fetch("revision")}"
    ].join("\n") + "\n"
    valid = payload["sha"] == sha &&
            payload.dig("commit", "message") == expected_message &&
            payload.dig("commit", "author", "name") == author.fetch("display_name") &&
            payload.dig("commit", "author", "email") == author.fetch("email") &&
            same_timestamp?(payload.dig("commit", "author", "date"), row.fetch("authored_at"))
    abort "Gitea commit #{row.fetch("id")} readback mismatch" unless valid
  end
end

def canonical_json(value)
  normalized = case value
               when Hash
                 value.keys.sort.to_h { |key| [key, canonical_json(value.fetch(key))] }
               when Array
                 value.map { |item| canonical_json(item) }
               else
                 value
               end
  JSON.generate(normalized)
end

def readback_company_state(manifest)
  token = File.read(REDMINE_TOKEN_PATH, encoding: "UTF-8").strip
  abort "Redmine API token is missing" if token.empty?
  verify_gitea(manifest)
  verify_redmine_projects(manifest, token)
  verify_redmine_tickets(manifest, token)

  items = []
  {
    "project" => "projects",
    "repository" => "repositories",
    "commit" => "commits",
    "ticket" => "tickets"
  }.each do |kind, section|
    manifest.fetch(section).each { |row| items << row.merge("kind" => kind) }
  end
  result = {
    "content_id" => "company-workhub-state",
    "format" => "keplerops-company-state-v1",
    "items" => items,
    "canonical_digest" => "sha256:#{Digest::SHA256.hexdigest(canonical_json(items))}"
  }
  File.write(WORKHUB_READBACK_PATH, JSON.pretty_generate(result) + "\n", mode: "w", perm: 0o600)
  File.chmod(0o600, WORKHUB_READBACK_PATH)
  puts JSON.generate(result)
end

manifest = load_company_state
case ARGV.fetch(0, "materialize")
when "materialize"
  materialize_company_state(manifest)
when "readback"
  readback_company_state(manifest)
else
  abort "unknown Redmine company-state mode"
end
