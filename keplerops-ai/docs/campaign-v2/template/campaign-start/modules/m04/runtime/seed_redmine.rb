require 'base64'
require 'json'

operation = ENV.fetch('M04_OPERATION')
payload = JSON.parse(Base64.decode64(ENV.fetch('M04_PAYLOAD')))
project = Project.find_by!(identifier: 'orion')
author = User.find_by(login: 'release.engineer') || User.find_by!(admin: true)
tracker = Tracker.find_by(name: 'Task') || Tracker.first
status = IssueStatus.where(is_closed: false).first
priority = IssuePriority.default || IssuePriority.first

records = {
  'kep-m04-h' => lambda { {
    subject: payload.fetch('ledger'),
    description: (payload.fetch('authoritative_entries').map { |entry| "#{entry['name']}: #{entry['status']} (#{entry['final_date'] || 'no approved release'})" } + [payload.fetch('explicit_exclusion')]).join("\n")
  } },
  'kep-m04-i' => lambda { {
    subject: payload.fetch('subject'),
    description: <<~TEXT
      Renderer revision: #{payload.fetch('renderer_revision')}
      Known failure conditions: #{payload.fetch('documented_conditions').join('; ')}.
      Compare externally submitted cases with a normal request in Jaeger. Do not
      invoke a mutating tool while investigating parser behavior.
    TEXT
  } },
  'kep-m04-j' => lambda { {
    subject: payload.fetch('subject'),
    description: <<~TEXT
      The signed manifest is a starting hypothesis. Verify one protected knowledge
      collection and one read-only MCP tool using distinct fresh trace IDs.
      Declared knowledge: #{payload.dig('signed_manifest', 'knowledge_hypotheses').join(', ')}
      Declared tools: #{payload.dig('signed_manifest', 'tool_hypotheses').join(', ')}
    TEXT
  } },
  'kep-m04-k' => lambda { {
    subject: 'Release assistant dry-run route review',
    description: <<~TEXT
      Workflow: #{payload.fetch('workflow_id')}
      Submit the non-production fixture through WorkHub and correlate these hops:
      #{payload.fetch('expected_hops').join(' -> ')}.
      Production mutation is not permitted.
    TEXT
  } }
}

record = records.fetch(operation).call
issue = Issue.find_or_initialize_by(project: project, subject: record.fetch(:subject))
issue.tracker = tracker
issue.author = author
issue.status = status
issue.priority = priority
issue.description = record.fetch(:description)
issue.save!
puts "WorkHub record reconciled: #{issue.id} #{issue.subject}"
