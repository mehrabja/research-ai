# Security Policy

Research AI handles user accounts, workspaces, research documents, source URLs, AI-provider integrations, and potentially sensitive research content. Security reports are welcome and should be handled privately.

## Supported versions

Until the first public release, only the current default branch is in scope for security fixes. Once tagged releases exist, the latest supported release will be identified here.

## Reporting a vulnerability

Please do not open a public issue, discussion, or pull request for a suspected vulnerability.

Use GitHub's private vulnerability reporting feature from the repository's Security tab when it is enabled. If that option is not available, contact the repository owner through a private channel first and ask for a secure reporting route; do not disclose exploit details publicly while waiting for a channel.

Include, where safe:

- A concise description and affected component.
- Reproduction steps or a proof of concept that does not access another person's data.
- The impact and any preconditions.
- Suggested mitigation, if known.

Do not attach real API keys, passwords, private documents, or personal data to a report. Redact logs and identifiers.

## Areas of particular interest

- Authentication, session refresh, password reset, and OAuth flows.
- Workspace, project, file, and report ownership checks.
- Server-side request forgery in source/document fetching and redirect handling.
- File upload, storage access, and extraction boundaries.
- Secret handling, logs, and error responses.
- Billing webhooks, idempotency, and usage records.
- Prompt injection or unsafe handling of untrusted source content in agent or AI workflows.
- Dependency and GitHub Actions supply-chain issues.

## Response and disclosure

The maintainer will acknowledge and triage reports as soon as reasonably practical. No fixed response or remediation SLA is promised at this stage. Please allow time for investigation and a coordinated fix before public disclosure.

Once a fix is available, the maintainer may publish an advisory and release notes describing the affected versions, impact, and remediation. Do not publish a proof of concept or exploit details before coordination.
