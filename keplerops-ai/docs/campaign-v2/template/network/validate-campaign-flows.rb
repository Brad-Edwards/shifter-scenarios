#!/usr/bin/env ruby

require "set"
require "yaml"

root = File.expand_path(__dir__)
template_root = File.expand_path("..", root)
campaign_root = File.join(template_root, "campaign-start")
flow_file = File.join(root, "campaign-flows.tsv")

compose_files = Dir.glob(File.join(template_root, "compose*.yaml")) +
  Dir.glob(File.join(campaign_root, "modules", "m??", "compose.overlay.yaml")) +
  [File.join(campaign_root, "compose.overlay.yaml")]
known_containers = Set.new
compose_files.uniq.sort.each do |path|
  next unless File.file?(path)

  document = YAML.safe_load_file(
    path,
    permitted_classes: [Symbol],
    aliases: true,
  ) || {}
  document.fetch("services", {}).each_value do |definition|
    next unless definition.is_a?(Hash)

    container = definition["container_name"].to_s
    known_containers << container unless container.empty?
  end
end

represented = Set.new
declared_flows = Set.new
source_pattern = /\A(?:[a-zA-Z0-9_.-]+|label:[a-zA-Z0-9_.\/-]+=[*a-zA-Z0-9_.-]+|cidr:[0-9.]+\/[0-9]+)\z/
destination_pattern = /\A(?:[a-zA-Z0-9_.-]+|cidr:[0-9.]+\/[0-9]+)\z/
File.readlines(flow_file, chomp: true).each_with_index do |line, index|
  next if line.empty? || line.lstrip.start_with?("#")

  fields = line.split("\t", -1)
  raise "#{flow_file}:#{index + 1}: expected five tab-separated fields" unless fields.length == 5
  raise "#{flow_file}:#{index + 1}: flow purpose is empty" if fields.fetch(4).strip.empty?
  raise "#{flow_file}:#{index + 1}: invalid source #{fields.fetch(0)}" unless fields.fetch(0).match?(source_pattern)
  raise "#{flow_file}:#{index + 1}: invalid destination #{fields.fetch(1)}" unless fields.fetch(1).match?(destination_pattern)
  raise "#{flow_file}:#{index + 1}: invalid protocol #{fields.fetch(2)}" unless %w[tcp udp].include?(fields.fetch(2))

  flow_key = fields.first(4)
  raise "#{flow_file}:#{index + 1}: duplicate flow #{flow_key.join(' ')}" if declared_flows.include?(flow_key)
  declared_flows << flow_key

  fields.first(2).each_with_index do |endpoint, endpoint_index|
    next if endpoint.start_with?("cidr:")
    next if endpoint_index.zero? && endpoint.start_with?("label:")

    raise "#{flow_file}:#{index + 1}: unknown container #{endpoint}" unless known_containers.include?(endpoint)
    represented << endpoint
  end

  fields.fetch(3).split(",").each do |port|
    number = Integer(port, 10)
    raise "#{flow_file}:#{index + 1}: invalid port #{port}" unless number.between?(1, 65_535)
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
