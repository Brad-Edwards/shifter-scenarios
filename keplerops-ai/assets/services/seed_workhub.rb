#!/usr/bin/env ruby
require "base64"
require "digest"
require "fileutils"
require "json"
require "net/http"
require "open3"
require "tmpdir"
require "uri"
require "yaml"

USER = "ml.engineer"
PASSWORD = "KeplerOps-Engineer-355!" # NOSONAR - synthetic training credential
EMAIL = "ml.engineer@keplerops.test"
BASE = URI("http://127.0.0.1:3000")
CONTENT_TYPE_HEADER = "Content-Type"
COMPANY_STATE_PATH = "/opt/keplerops/company-state.yaml"
GITEA_READBACK_PATH = "/data/gitea/company-state-gitea-readback.json"
OWNER_PREFIX = "keplerops-company-state"
CHALLENGE_REPOSITORY_DESCRIPTION = "Synthetic KeplerOps model release lab"
GIT_QUIET = "--quiet"
SEED_TOKEN = if ARGV[0]
               File.read(ARGV.fetch(0), encoding: "UTF-8").match(/(?:gitea_[A-Za-z0-9_]+|[0-9a-f]{40})/)&.to_s
             end

def http_request(method, path, body: nil, admin: false, content_type: "application/json")
  uri = BASE + path
  request = method.new(uri)
  if admin
    abort "workhub seed token missing" unless SEED_TOKEN
    request["Authorization"] = "token #{SEED_TOKEN}"
  else
    request.basic_auth(USER, PASSWORD)
  end
  request[CONTENT_TYPE_HEADER] = content_type if body
  request.body = content_type == "application/json" ? JSON.generate(body) : body if body
  Net::HTTP.start(uri.hostname, uri.port, open_timeout: 2, read_timeout: 20) do |http|
    http.request(request)
  end
end

def json_body(response, label)
  JSON.parse(response.body)
rescue JSON::ParserError => error
  abort "#{label} returned invalid JSON: #{error.message}"
end

def expect_code(response, allowed, label)
  return response if allowed.include?(response.code)

  abort "#{label} failed with HTTP #{response.code}: #{response.body.to_s[0, 500]}"
end

def load_company_state
  value = YAML.safe_load(
    File.read(COMPANY_STATE_PATH, encoding: "UTF-8"),
    permitted_classes: [],
    permitted_symbols: [],
    aliases: false
  )
  abort "company-state manifest must be a mapping" unless value.is_a?(Hash)
  %w[people projects repositories commits tickets].each do |section|
    abort "company-state #{section} must be a non-empty list" unless value[section].is_a?(Array) && !value[section].empty?
  end
  value
rescue Psych::Exception => error
  abort "company-state manifest is invalid: #{error.message}"
end

def wait_for_gitea
  20.times do
    begin
      response = Net::HTTP.get_response(BASE + "/api/v1/version")
      return if response.code == "200"
    rescue StandardError
      nil
    end
    sleep 1
  end
  abort "workhub gitea startup failed"
end

def ensure_challenge_user
  response = http_request(Net::HTTP::Get, "/api/v1/user")
  if response.code == "200"
    user = json_body(response, "workhub challenge user readback")
    unless user["login"] == USER && user["email"] == EMAIL
      abort "workhub challenge user collision"
    end
    return
  end
  expect_code(response, ["401"], "workhub challenge user preflight")

  response = http_request(
    Net::HTTP::Post,
    "/api/v1/admin/users",
    admin: true,
    body: {
      username: USER,
      password: PASSWORD,
      email: EMAIL,
      must_change_password: false,
      send_notify: false
    }
  )
  expect_code(response, %w[201 422], "workhub challenge user seed")

  response = http_request(Net::HTTP::Get, "/api/v1/user")
  expect_code(response, ["200"], "workhub challenge user authentication")
  user = json_body(response, "workhub challenge user readback")
  unless user["login"] == USER && user["email"] == EMAIL
    abort "workhub challenge user collision"
  end
end

def repository(path)
  response = http_request(Net::HTTP::Get, path)
  return nil if response.code == "404"

  expect_code(response, ["200"], "workhub repository readback")
  json_body(response, "workhub repository readback")
end

def ensure_repository(row)
  slug = row.fetch("slug")
  repository_id = row.fetch("id")
  path = "/api/v1/repos/#{USER}/#{slug}"
  existing = repository(path)
  expected_description = if repository_id == "repository-model-release"
                           CHALLENGE_REPOSITORY_DESCRIPTION
                         else
                           "[#{OWNER_PREFIX}:#{repository_id}] #{row.fetch("project_ref")}"
                         end
  if existing.nil?
    response = http_request(
      Net::HTTP::Post,
      "/api/v1/user/repos",
      body: {
        name: slug,
        private: true,
        auto_init: false,
        default_branch: row.fetch("default_branch"),
        description: expected_description
      }
    )
    expect_code(response, ["201"], "workhub repository #{repository_id} seed")
    existing = json_body(response, "workhub repository #{repository_id} seed")
  end

  expected = {
    "owner" => USER,
    "description" => expected_description,
    "private" => true,
    "default_branch" => row.fetch("default_branch")
  }
  observed = {
    "owner" => existing.dig("owner", "login"),
    "description" => existing["description"],
    "private" => existing["private"],
    "default_branch" => existing["default_branch"]
  }
  abort "workhub repository #{repository_id} is an unowned collision" unless observed == expected

  existing
end

def content_response(slug, path, branch)
  encoded_path = path.split("/").map { |part| URI.encode_www_form_component(part) }.join("/")
  response = http_request(
    Net::HTTP::Get,
    "/api/v1/repos/#{USER}/#{slug}/contents/#{encoded_path}?ref=#{URI.encode_www_form_component(branch)}"
  )
  return nil if response.code == "404"

  expect_code(response, ["200"], "workhub content #{slug}/#{path} readback")
  json_body(response, "workhub content #{slug}/#{path} readback")
end

def run_git(environment, *arguments)
  stdout, _stderr, status = Open3.capture3(environment, "git", *arguments)
  abort "workhub authenticated Git operation failed" unless status.success?

  stdout
end

def seed_content_through_git(slug:, path:, content:, message:, branch:, identity:, timestamp:)
  user = URI.encode_www_form_component(USER)
  password = URI.encode_www_form_component(PASSWORD)
  repository = URI.encode_www_form_component(slug)
  remote = "http://#{user}:#{password}@127.0.0.1:3000/#{user}/#{repository}.git"
  environment = {"GIT_TERMINAL_PROMPT" => "0"}

  Dir.mktmpdir("keplerops-workhub-seed-") do |directory|
    run_git(
      environment,
      "clone",
      GIT_QUIET,
      "--branch",
      branch,
      "--single-branch",
      remote,
      directory
    )
    target = File.expand_path(path, directory)
    abort "workhub content path escaped repository" unless target.start_with?("#{directory}/")

    FileUtils.mkdir_p(File.dirname(target))
    File.binwrite(target, content)
    run_git(environment, "-C", directory, "add", "--", path)
    commit_environment = environment.merge(
      "GIT_AUTHOR_DATE" => timestamp,
      "GIT_COMMITTER_DATE" => timestamp
    )
    run_git(
      commit_environment,
      "-C",
      directory,
      "-c",
      "user.name=#{identity.fetch(:name)}",
      "-c",
      "user.email=#{identity.fetch(:email)}",
      "commit",
      GIT_QUIET,
      "--message",
      message
    )
    sha = run_git(environment, "-C", directory, "rev-parse", "HEAD").strip
    run_git(environment, "-C", directory, "push", GIT_QUIET, "origin", "HEAD:refs/heads/#{branch}")
    sha
  end
end

def ensure_content(slug:, path:, content:, message:, branch:, identity:, timestamp:)
  existing = content_response(slug, path, branch)
  if existing
    observed = Base64.decode64(existing.fetch("content"))
    abort "workhub content #{slug}/#{path} is an unowned collision" unless observed == content
    return existing.fetch("last_commit_sha")
  end

  encoded_path = path.split("/").map { |part| URI.encode_www_form_component(part) }.join("/")
  response = http_request(
    Net::HTTP::Post,
    "/api/v1/repos/#{USER}/#{slug}/contents/#{encoded_path}",
    body: {
      content: Base64.strict_encode64(content),
      message: message,
      branch: branch,
      author: identity,
      committer: identity,
      dates: {author: timestamp, committer: timestamp}
    }
  )
  if response.code == "404" && response.body.include?("branch does not exist")
    sha = seed_content_through_git(
      slug: slug,
      path: path,
      content: content,
      message: message,
      branch: branch,
      identity: identity,
      timestamp: timestamp
    )
    observed = content_response(slug, path, branch) ||
               abort("workhub Git seed #{slug}/#{path} omitted API readback")
    decoded = Base64.decode64(observed.fetch("content"))
    abort "workhub Git seed #{slug}/#{path} readback mismatch" unless decoded == content

    return sha
  end
  expect_code(response, ["201"], "workhub content #{slug}/#{path} seed")
  json_body(response, "workhub content #{slug}/#{path} seed").dig("commit", "sha") ||
    abort("workhub content #{slug}/#{path} response omitted commit SHA")
end

def ensure_binary_package(path, content, label)
  response = http_request(
    Net::HTTP::Put,
    path,
    body: content,
    content_type: "application/octet-stream"
  )
  return if response.code == "201"

  expect_code(response, ["409"], "#{label} seed")
  readback = http_request(Net::HTTP::Get, path)
  expect_code(readback, ["200"], "#{label} collision readback")
  abort "#{label} collision has different bytes" unless Digest::SHA256.digest(readback.body) == Digest::SHA256.digest(content)
end

def pypi_request(path, package_path)
  uri = BASE + path
  request = Net::HTTP::Post.new(uri)
  request.basic_auth(USER, PASSWORD)
  file = File.open(package_path, "rb")
  request.set_form(
    [
      [":action", "file_upload"],
      ["protocol_version", "1"],
      ["metadata_version", "2.1"],
      ["name", "keplerops-eval-runtime"],
      ["version", "1.0.0"],
      ["summary", "KeplerOps trusted evaluation runtime"],
      ["filetype", "bdist_wheel"],
      ["pyversion", "py3"],
      ["sha256_digest", Digest::SHA256.file(package_path).hexdigest],
      ["content", file, {filename: File.basename(package_path), content_type: "application/octet-stream"}]
    ],
    "multipart/form-data"
  )
  Net::HTTP.start(uri.hostname, uri.port, open_timeout: 2, read_timeout: 20) do |http|
    http.request(request)
  end
ensure
  file&.close
end

def ensure_challenge_content_and_packages
  challenge_identity = {name: "Elena Vasquez", email: EMAIL}
  {
    "lab-readme.md" => ["/opt/keplerops/seed/lab-readme.md", "2026-04-06T08:00:00Z"],
    "work-items.yaml" => ["/opt/keplerops/seed/work-items.yaml", "2026-04-06T08:05:00Z"]
  }.each do |name, (source, timestamp)|
    ensure_content(
      slug: "model-release",
      path: name,
      content: File.binread(source),
      message: "Seed #{name}",
      branch: "main",
      identity: challenge_identity,
      timestamp: timestamp
    )
  end

  ensure_binary_package(
    "/api/packages/#{USER}/generic/keplerops-maintainer/1.0.0/keplerops-maintainer.sh",
    File.binread("/opt/keplerops/seed/agent-packages/keplerops-maintainer-1.0.0.sh"),
    "workhub challenge package"
  )
  {
    "1.0.0" => "/opt/keplerops/seed/model-dependencies/policy-model-clean.json",
    "2.0.0" => "/opt/keplerops/seed/model-dependencies/policy-model-poisoned.json"
  }.each do |version, source|
    ensure_binary_package(
      "/api/packages/#{USER}/generic/keplerops-policy-model/#{version}/policy-model.json",
      File.binread(source),
      "workhub model dependency #{version}"
    )
  end

  package_path = "/opt/keplerops/seed/python-packages/keplerops_eval_runtime-1.0.0-py3-none-any.whl"
  response = pypi_request("/api/packages/#{USER}/pypi", package_path)
  return if response.code == "201"

  expect_code(response, ["409"], "workhub clean runtime PyPI seed")
  readback = http_request(
    Net::HTTP::Get,
    "/api/packages/#{USER}/pypi/files/keplerops-eval-runtime/1.0.0/#{File.basename(package_path)}"
  )
  expect_code(readback, ["200"], "workhub clean runtime PyPI collision readback")
  abort "workhub clean runtime PyPI collision has different bytes" unless Digest::SHA256.hexdigest(readback.body) == Digest::SHA256.file(package_path).hexdigest
end

def owner_marker(commit_id)
  "#{OWNER_PREFIX}:#{commit_id}"
end

def commit_content(row)
  JSON.pretty_generate(
    {
      "id" => row.fetch("id"),
      "revision" => row.fetch("revision"),
      "repository_ref" => row.fetch("repository_ref"),
      "author_ref" => row.fetch("author_ref"),
      "authored_at" => row.fetch("authored_at"),
      "ticket_refs" => row.fetch("ticket_refs"),
      "dataset_refs" => row.fetch("dataset_refs"),
      "summary" => row.fetch("summary")
    }
  ) + "\n"
end

def commit_message(row)
  [
    row.fetch("summary"),
    "",
    "KeplerOps-State-ID: #{owner_marker(row.fetch("id"))}",
    "KeplerOps-Revision: #{row.fetch("revision")}"
  ].join("\n")
end

def validate_commit(slug, row, sha)
  response = http_request(Net::HTTP::Get, "/api/v1/repos/#{USER}/#{slug}/git/commits/#{sha}")
  expect_code(response, ["200"], "workhub commit #{row.fetch("id")} readback")
  commit = json_body(response, "workhub commit #{row.fetch("id")} readback")
  expected_author = row.fetch("_author")
  observed = {
    "message" => commit.dig("commit", "message"),
    "author_name" => commit.dig("commit", "author", "name"),
    "author_email" => commit.dig("commit", "author", "email"),
    "author_date" => commit.dig("commit", "author", "date")
  }
  expected = {
    "message" => commit_message(row) + "\n",
    "author_name" => expected_author.fetch("display_name"),
    "author_email" => expected_author.fetch("email"),
    "author_date" => row.fetch("authored_at")
  }
  abort "workhub commit #{row.fetch("id")} is an unowned collision" unless observed == expected
end

def ensure_revision_tag(slug, row, sha)
  revision = row.fetch("revision")
  response = http_request(
    Net::HTTP::Get,
    "/api/v1/repos/#{USER}/#{slug}/tags/#{URI.encode_www_form_component(revision)}"
  )
  if response.code == "404"
    response = http_request(
      Net::HTTP::Post,
      "/api/v1/repos/#{USER}/#{slug}/tags",
      body: {
        tag_name: revision,
        target: sha,
        message: "KeplerOps represented revision #{revision} (#{owner_marker(row.fetch("id"))})"
      }
    )
    expect_code(response, ["201"], "workhub revision tag #{revision} seed")
    return
  end

  expect_code(response, ["200"], "workhub revision tag #{revision} readback")
  tag = json_body(response, "workhub revision tag #{revision} readback")
  abort "workhub revision #{revision} is an unowned collision" unless tag.dig("commit", "sha") == sha
end

def ensure_company_commits(manifest)
  people = manifest.fetch("people").to_h { |row| [row.fetch("id"), row] }
  repositories = manifest.fetch("repositories").to_h { |row| [row.fetch("id"), row] }
  readback = []

  manifest.fetch("commits").each do |source_row|
    row = source_row.merge("_author" => people.fetch(source_row.fetch("author_ref")))
    repository_row = repositories.fetch(row.fetch("repository_ref"))
    slug = repository_row.fetch("slug")
    content = commit_content(row)
    sha = ensure_content(
      slug: slug,
      path: "company-state/#{row.fetch("id")}.json",
      content: content,
      message: commit_message(row),
      branch: repository_row.fetch("default_branch"),
      identity: {
        name: row.fetch("_author").fetch("display_name"),
        email: row.fetch("_author").fetch("email")
      },
      timestamp: row.fetch("authored_at")
    )
    validate_commit(slug, row, sha)
    ensure_revision_tag(slug, row, sha)
    readback << source_row.merge("native_revision" => sha)
  end
  readback
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

wait_for_gitea
manifest = load_company_state
ensure_challenge_user

repository_rows = manifest.fetch("repositories")
repository_rows.each { |row| ensure_repository(row) }
ensure_challenge_content_and_packages
commit_rows = ensure_company_commits(manifest)

gitea_readback = {
  "repositories" => repository_rows,
  "commits" => commit_rows
}
gitea_readback["canonical_digest"] = "sha256:#{Digest::SHA256.hexdigest(canonical_json(gitea_readback))}"
File.write(GITEA_READBACK_PATH, JSON.pretty_generate(gitea_readback) + "\n", mode: "w", perm: 0o600)
File.chmod(0o600, GITEA_READBACK_PATH)

puts JSON.generate(gitea_readback)
