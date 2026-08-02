#!/usr/bin/env ruby

require "set"
require "yaml"

root = File.expand_path(__dir__)
template_root = File.expand_path("..", root)
campaign_root = File.join(template_root, "campaign-start")
flow_file = File.join(root, "campaign-flows.tsv")

represented = Set.new
File.readlines(flow_file, chomp: true).each_with_index do |line, index|
  next if line.empty? || line.lstrip.start_with?("#")

  fields = line.split("\t", -1)
  raise "#{flow_file}:#{index + 1}: expected five tab-separated fields" unless fields.length == 5

  fields.first(2).each do |endpoint|
    represented << endpoint unless endpoint.start_with?("cidr:", "label:")
  end
end

required = Set.new
Dir.glob(File.join(campaign_root, "modules", "m??", "compose.overlay.yaml")).sort.each do |path|
  document = YAML.safe_load_file(path, aliases: true) || {}
  services = document.fetch("services", {})
  raise "#{path}: services must be a mapping" unless services.is_a?(Hash)

  services.each_value do |definition|
    next unless definition.is_a?(Hash)
    next if definition["container_name"].to_s.empty?
    next if definition["network_mode"] == "none"
    next unless definition["networks"]

    required << definition["container_name"].to_s
  end
end

missing = (required - represented).sort
raise "networked campaign containers lack declared flows: #{missing.join(', ')}" unless missing.empty?

puts "campaign flow coverage passed: #{required.length} networked campaign containers"
