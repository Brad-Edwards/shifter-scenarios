#!/usr/bin/env ruby

require "digest"
require "pathname"
require "yaml"

root = Pathname(__dir__)
atlas_path = Pathname(ARGV.fetch(0, "/tmp/ATLAS-2026.06.yaml"))
atlas_sha256 = "b771de8b1489564b2838a709c7429849a9575dbd94073928817fe1a21661e70a"
errors = []

["operation-allocation.md", "model-and-release-contract.md"].each do |name|
  runtime_copy = root.join("template/campaign-start/contracts", name)
  unless runtime_copy.exist? && File.binread(runtime_copy) == File.binread(root.join(name))
    errors << "runtime campaign contract drift: #{name}"
  end
end

sections = {}
Dir[root.join("operations-act-*.md")].each do |file|
  text = File.read(file)
  matches = []
  text.to_enum(:scan, /^(?:##|###) `(kep-m\d{2}-[a-z])`:/).each do
    matches << [Regexp.last_match.begin(0), Regexp.last_match[1]]
  end

  matches.each_with_index do |(position, id), index|
    finish = index + 1 < matches.length ? matches[index + 1][0] : text.length
    errors << "duplicate operation #{id}" if sections.key?(id)
    sections[id] = text[position...finish]
  end
end

errors << "expected 134 operations, found #{sections.length}" unless sections.length == 134
sections.each do |id, section|
  ["Difficulty", "Participant description", "Hints"].each do |field|
    errors << "#{id} missing #{field}" unless section.include?(field)
  end
  unless section.match?(/Flag \/ reset \/ QA|Evidence and flag placement/)
    errors << "#{id} missing flag/evidence contract"
  end
end

difficulties = Hash.new(0)
points = 0
sections.each do |id, section|
  match = section.match(
    /\*\*Difficulty \/ points:\*\* (Accessible|Intermediate|Advanced|Expert) \/ ([\d,]+)/
  )
  unless match
    errors << "#{id} has malformed difficulty/points"
    next
  end
  difficulties[match[1]] += 1
  points += match[2].delete(",").to_i
end

expected_difficulties = {
  "Accessible" => 40,
  "Intermediate" => 48,
  "Advanced" => 33,
  "Expert" => 13
}
errors << "difficulty drift: #{difficulties}" unless difficulties == expected_difficulties
errors << "point drift: #{points}" unless points == 31_650

flag_ids = File.read(root.join("flag-proof-ledger.md"))
  .scan(/^\| \d+ \| `(kep-m\d{2}-[a-z])` \|/)
  .flatten
unless flag_ids.length == 134 && flag_ids.uniq.length == 134
  errors << "flag ledger has #{flag_ids.length} rows and #{flag_ids.uniq.length} unique IDs"
end
(sections.keys - flag_ids).each { |id| errors << "missing flag carrier #{id}" }
(flag_ids - sections.keys).each { |id| errors << "unknown flag carrier #{id}" }

raw_prerequisites = {}
dependencies = {}
File.foreach(root.join("operation-prerequisite-graph.md")) do |line|
  match = line.match(/^\| `(kep-m\d{2}-[a-z])` \| (.*?) \|/)
  next unless match
  errors << "duplicate prerequisite row #{match[1]}" if raw_prerequisites.key?(match[1])
  raw_prerequisites[match[1]] = match[2]
  dependencies[match[1]] = match[2].scan(/kep-m\d{2}-[a-z]/).uniq
end
errors << "expected 134 prerequisite rows, found #{raw_prerequisites.length}" unless raw_prerequisites.length == 134
(dependencies.values.flatten.uniq - sections.keys).each do |id|
  errors << "unknown prerequisite reference #{id}"
end

colors = Hash.new(:white)
stack = []
visit = nil
visit = lambda do |node|
  colors[node] = :gray
  stack << node
  dependencies.fetch(node, []).each do |dependency|
    if colors[dependency] == :gray
      errors << "prerequisite cycle #{(stack[stack.index(dependency)..] + [dependency]).join(' -> ')}"
    elsif colors[dependency] == :white
      visit.call(dependency)
    end
  end
  stack.pop
  colors[node] = :black
end
sections.each_key { |id| visit.call(id) if colors[id] == :white }

route_ids = File.read(root.join("event-critical-route.md")).lines.filter_map do |line|
  match = line.match(/^\d+\. `(kep-m\d{2}-[a-z])`/)
  match && match[1]
end
unless route_ids.length == 39 && route_ids.uniq.length == 39
  errors << "critical route has #{route_ids.length} rows and #{route_ids.uniq.length} unique IDs"
end
route_ids.each do |operation|
  unless raw_prerequisites.key?(operation)
    errors << "critical route references unknown #{operation}"
    next
  end
  raw_prerequisites[operation].split(/ \+ /).each do |and_factor|
    references = and_factor.scan(/kep-m\d{2}-[a-z]/).uniq
    if !references.empty? && (references & route_ids).empty?
      errors << "critical route hides prerequisite for #{operation}: #{and_factor}"
    end
  end
end

unless atlas_path.exist?
  errors << "ATLAS source not found: #{atlas_path}"
else
  unless Digest::SHA256.file(atlas_path).hexdigest == atlas_sha256
    errors << "ATLAS source SHA-256 mismatch"
  end

  official = {}
  walk = nil
  walk = lambda do |value|
    case value
    when Hash
      if value["id"].to_s.match?(/\AAML\.T\d/) && value["name"]
        official[value["id"]] = value["name"]
      end
      value.each_value { |child| walk.call(child) }
    when Array
      value.each { |child| walk.call(child) }
    end
  end
  walk.call(YAML.load_file(atlas_path))

  ledger = {}
  File.foreach(root.join("atlas-coverage-ledger.md")) do |line|
    match = line.match(
      /^\| `(AML\.T\d+(?:\.\d+)?) ([^`]+)` \| `(kep-m\d{2}-[a-z])` \|/
    )
    next unless match
    errors << "duplicate ATLAS row #{match[1]}" if ledger.key?(match[1])
    ledger[match[1]] = [match[2], match[3]]
  end

  errors << "expected 173 official techniques, found #{official.length}" unless official.length == 173
  errors << "expected 172 ledger techniques, found #{ledger.length}" unless ledger.length == 172
  excluded = official.keys - ledger.keys
  errors << "unexpected ATLAS exclusions: #{excluded}" unless excluded == ["AML.T0010.000"]

  ledger.each do |id, (name, operation)|
    errors << "official name drift for #{id}: #{name.inspect}" unless official[id] == name
    unless sections.key?(operation)
      errors << "ATLAS row #{id} references unknown #{operation}"
      next
    end
    normalized = sections[operation].gsub(/\s+/, " ")
    unless normalized.include?("`#{id} #{name}`")
      errors << "#{operation} does not explicitly claim `#{id} #{name}`"
    end
  end
end

Dir[root.join("*.md")].each do |file|
  File.read(file).scan(/\[[^\]]+\]\(([^)]+)\)/).flatten.each do |target|
    next if target.match?(/\A(?:https?:|mailto:|#)/)
    local_target = target.sub(/#.*/, "")
    next if local_target.empty?
    resolved = Pathname(file).dirname.join(local_target).cleanpath
    errors << "broken link in #{File.basename(file)}: #{target}" unless resolved.exist?
  end
end

puts "operations=#{sections.length} difficulty=#{difficulties} points=#{points} " \
     "flags=#{flag_ids.length} graph=#{raw_prerequisites.length} route=#{route_ids.length}"

if errors.empty?
  puts "CAMPAIGN V2 DESIGN VALIDATION: PASS"
  exit 0
end

warn "CAMPAIGN V2 DESIGN VALIDATION: FAIL (#{errors.length})"
errors.each { |error| warn error }
exit 1
