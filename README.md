# iMouseGuard

iMouseGuard is a real-time behavioral alerting system for ZoneMinder-based animal surveillance workflows. The project receives events from ZoneMinder Event Server, enriches them with API metadata, evaluates behavioral conditions, and delivers notifications through configured channels.

## Project Scope

- Ingest ZoneMinder Event Server messages over WebSocket.
- Enrich events with monitor and event metadata via ZoneMinder API.
- Apply behavioral alert logic and rule-based filtering.
- Deliver alerts to supported messaging channels.
- Provide analysis scripts for historical event data.

## Repository Structure

- iMouseGuard/bin/: runtime scripts and alert processing components.
- iMouseGuard/config/: service and integration configuration files.
- iMouseGuard/env/: environment variable templates and deployment settings.
- iMouseGuard/dev/: manual testing utilities and local trigger tools.
- iMouseGuard/analysis/: event analysis scripts and generated reports.
- iMouseGuard/docs/: supporting documentation for rules and experiments.
- zmeventnotification/: upstream Event Server vendor source retained for integration.

## Quick Start

1. Prepare Python and ZoneMinder dependencies.
2. Configure environment values in iMouseGuard/env/prod.env.
3. Start the ZoneMinder Event Server.
4. Run the forwarder and hook scripts from iMouseGuard/bin/.
5. Verify output in iMouseGuard/logs/.

## Security and Confidentiality

- Do not commit secrets, tokens, or credentials.
- Restrict access to runtime environment files.
- Review notification endpoints before production use.

## License

This repository is proprietary and confidential.

No person or organization is permitted to use, copy, modify, distribute, publish, sublicense, or create derivative works from any part of this repository without prior written permission from the copyright holder.

See the LICENSE file for full terms.