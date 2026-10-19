# Project notes

## Decisions
- AWS: free plan with credits ($155), budget alert set (to do)
- No domain: previews use the ALB address over HTTP with path routing (/pr-N/)
- Same-repo PRs only, forks are not deployed
- Deploy by image digest, concurrency group per PR, two Terraform states (shared + per-PR)

## Fixes and problems
(add each one here with the cause and fix)
- Trivy: aquasecurity/trivy-action tags were compromised in March 2026 (CVE-2026-33634).
  CI now runs ghcr.io/aquasecurity/trivy:0.69.3 pinned, instead of a mutable action tag.
- Future hardening: pin all third-party actions to full commit SHAs.
