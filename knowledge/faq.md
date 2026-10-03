# Quillbyte FAQ

## Getting Started

### How do I create an account?
Go to `app.quillbyte.example/signup`, enter your work email and choose a password. You will receive a confirmation email. The Pro trial starts immediately.

### How do I install the Quillbyte agent?
Run the install script from Settings > Agents, which includes your organization key. On Kubernetes, use the Helm chart `quillbyte/agent`. The agent starts sending data within about one minute.

### Which operating systems does the agent support?
Ubuntu 20.04 and newer, Debian 11 and newer, RHEL 8 and newer, macOS 12 and newer, and Windows Server 2019 and newer.

## Billing

### Can I change plans at any time?
Yes. Upgrades apply immediately and are prorated. Downgrades take effect at the next billing date.

### What payment methods do you accept?
Visa, Mastercard, American Express and SEPA direct debit. Enterprise customers can pay by invoice.

### What happens if I exceed my log quota?
Logs are still ingested and overage is billed at $0.50 per GB. You can set a hard cap in Settings > Usage to stop ingestion at the quota instead.

## Troubleshooting

### My host does not appear in Pulse. What should I check?
1. Confirm the agent is running with `quillbyte-agent status`.
2. Check outbound access to `ingest.quillbyte.example` on port 443.
3. Verify the organization key in `/etc/quillbyte/agent.yaml`.
4. Review agent logs in `/var/log/quillbyte/agent.log`.

### Why are my alerts delayed?
Alerts are evaluated every 30 seconds. Delays longer than 2 minutes are usually caused by a notification channel problem. Check the channel status under Watchtower > Channels.

### I get HTTP 429 from the API. What does it mean?
You exceeded 600 requests per minute. Wait for the number of seconds in the `Retry-After` header, then retry with exponential backoff.

## Support

### How do I contact support?
Email support@quillbyte.example or use the chat widget in the app. Pro customers get a response within 1 business day. Enterprise customers have a dedicated channel with a 1 hour response target for critical issues.
