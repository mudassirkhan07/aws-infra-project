# Project notes

## Decisions
- AWS: free plan with credits ($155), budget alert set (to do)
- No domain: previews use the ALB address over HTTP with path routing (/pr-N/)
- Same-repo PRs only, forks are not deployed
- Deploy by image digest, concurrency group per PR, two Terraform states (shared + per-PR)

## Fixes and problems
(add each one here with the cause and fix)
