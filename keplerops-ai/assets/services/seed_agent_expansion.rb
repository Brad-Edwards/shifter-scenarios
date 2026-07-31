#!/usr/bin/env ruby
require "net/http"
require "uri"

base = URI("http://127.0.0.1:3000")
uri = base + "/api/packages/ml.engineer/generic/keplerops-maintainer/1.0.0/keplerops-maintainer.sh"
request = Net::HTTP::Put.new(uri)
request.basic_auth("ml.engineer", "KeplerOps-Engineer-355!") # NOSONAR - synthetic training credential
request["Content-Type"] = "application/octet-stream"
request.body = File.binread("/opt/keplerops/seed/agent-packages/keplerops-maintainer-1.0.0.sh")
response = Net::HTTP.start(uri.hostname, uri.port, open_timeout: 2, read_timeout: 10) do |http|
  http.request(request)
end
abort "agent expansion package seed failed" unless ["201", "409"].include?(response.code)
