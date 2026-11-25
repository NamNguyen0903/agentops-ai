# ADR-0006 — Model and Search Providers

Date: 2026-11-25.

Status: PARTIALLY ACCEPTED — Development MVP only.

Authority: Owner-approved S06 Contract v1.0,
AD02, AD03, AD04 and AD07.

## Context

S04 and S05 provide verified offline workflow
baselines. S06 needs an application-owned provider
boundary and secure retrieval foundation.

Direct provider access by models would weaken
permission enforcement, reproducibility and
network security.

## Accepted decision

- Typed application-owned search/retrieval interfaces.
- Deterministic test adapters and controlled transports.
- Strict request and response validation.
- External execution disabled by default.
- Application-owned permissions and usage limits.
- Bounded I/O, retries and failure handling.
- Sanitized public errors.

## Network security requirements

Real retrieval, when separately authorized, must:

- Permit only approved public HTTP(S) destinations.
- Reject credentials and prohibited URL schemes.
- Reject private, loopback, link-local, metadata
  and other non-public IPv4/IPv6 destinations.
- Validate all relevant DNS results.
- Prevent DNS rebinding through validated destination
  binding to the actual network connection.
- Revalidate each redirect destination.
- Preserve TLS certificate and hostname verification.
- Prevent proxy or environment configuration from
  bypassing destination security policy.
- Bound duration, response size, decompression,
  redirects, retries and accepted content types.

Fetched content cannot authorize tools or change
policies, credentials, budgets or destinations.

## Alternatives

Direct unguarded provider or HTTP access:
rejected because it bypasses application controls.

Application-owned interfaces with deterministic
verification: accepted for Development MVP.

## Open decisions

- Search vendor selection.
- Vendor API contract and quota.
- Pricing, cost accounting and data retention terms.
- Vendor credentials and secret handling.
- Live external execution and smoke-test authorization.
- Live model, Bedrock region and quota selection.
- Any dependency changes requiring separate review.

A vendor-specific adapter must not be enabled or
treated as approved until these applicable gates
are resolved.

No paid API call or real external retrieval is
authorized by this ADR.

## Verification

WP02 must supply focused contract, transport,
budget, malformed-response and adversarial
security evidence.

WP04 and WP05 must verify integrated enforcement.

ADR acceptance alone does not establish runtime
implementation or network-security verification.

Production remains NOT APPROVED.
