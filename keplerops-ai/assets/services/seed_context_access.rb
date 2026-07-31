#!/usr/bin/env ruby
require "json"
require "net/http"
require "uri"

USER = "ml.engineer"
PASSWORD = "KeplerOps-Engineer-355!" # NOSONAR - synthetic training credential
TOKEN_PATH = "/data/gitea/platform-context-gitea-token"
BASE = URI("http://127.0.0.1:3000")

exit 0 if File.file?(TOKEN_PATH) && File.size?(TOKEN_PATH)

uri = BASE + "/api/v1/users/#{USER}/tokens"
request = Net::HTTP::Post.new(uri)
request.basic_auth(USER, PASSWORD)
request["Content-Type"] = "application/json"
request.body = JSON.dump(
  name: "platform-context",
  scopes: ["read:repository", "write:repository", "read:user"]
)
response = Net::HTTP.start(uri.hostname, uri.port, open_timeout: 2, read_timeout: 5) do |http|
  http.request(request)
end
abort "platform context Gitea token creation failed" unless response.code == "201"

payload = JSON.parse(response.body)
token = payload["sha1"] || payload["token"]
abort "platform context Gitea token missing" unless token.is_a?(String) && !token.empty?
File.write(TOKEN_PATH, token + "\n", mode: "w", perm: 0o600)
File.chmod(0o600, TOKEN_PATH)
