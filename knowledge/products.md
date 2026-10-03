# Quillbyte Products

## Pulse (Metrics Monitoring)
Pulse collects metrics from servers, containers and applications and shows them on dashboards. It supports alerting based on thresholds or anomaly detection.

Key features:
- Agent for Linux, macOS and Windows
- Native Kubernetes integration
- 15-second default metric resolution
- Anomaly detection alerts (Pro plan and above)
- Retention of 30 days on Starter, 13 months on Pro

## Trailhead (Log Search)
Trailhead ingests application and infrastructure logs and makes them searchable in seconds. It uses a query language called QBQL (Quillbyte Query Language).

Example QBQL query:
`service:checkout level:error | last 1h | count by region`

Key features:
- Ingestion via agent, HTTP API or syslog
- Live tail for streaming logs
- Saved searches and shared views
- Log retention of 7 days on Starter, 30 days on Pro, custom on Enterprise

## Watchtower (Incident Response)
Watchtower manages on-call schedules, escalation policies and incident timelines. It connects to Pulse and Trailhead so alerts open incidents automatically.

Key features:
- Schedules with rotations and overrides
- Escalation after 5 minutes by default if an alert is not acknowledged
- Notifications by SMS, phone call, email and push
- Slack and Microsoft Teams integration
- Automatic postmortem templates

## Integrations
Quillbyte integrates with AWS, Google Cloud, Azure, GitHub, GitLab, Slack, Microsoft Teams, Jira and PagerDuty (for migration). Custom integrations can be built using the REST API at `https://api.quillbyte.example/v2`.

## API Basics
- Authentication uses a bearer token created under Settings > API Keys.
- Rate limit is 600 requests per minute per organization.
- Exceeding the limit returns HTTP 429 with a `Retry-After` header.
