# Portal Webhook Ingestion Specification

## Purpose

Authenticate Portal webhooks and turn supported events into transport envelopes without making domain decisions.

## Requirements

### Requirement: Verified Webhook Admission

The system MUST obtain the webhook secret server-side, MAY cache it, and MUST validate `portal-signature` before parsing or accepting a request. Validation MUST use the timestamped HMAC-SHA256 protocol over the exact raw request bytes, constant-time comparison, and a configured timestamp tolerance. A missing, unavailable, or 404 secret MUST fail closed.

#### Scenario: Valid exact-body signature

- GIVEN raw signed Portal bytes and a current timestamp
- WHEN the signature matches those exact bytes
- THEN the request is admitted for normalization

#### Scenario: Invalid signature

- GIVEN altered bytes, a missing header, or an invalid signature
- WHEN the request is received
- THEN it is rejected before parsing or enqueueing

#### Scenario: Stale signature

- GIVEN a valid signature outside the configured tolerance
- WHEN the request is received
- THEN it is rejected before parsing or enqueueing

### Requirement: Supported Event Normalization

The system MUST normalize only `message.published` and `message.retracted` into versioned typed envelopes identified by the top-level Portal event `id`. It MUST NOT normalize unsupported event types. A retraction MUST be audit-only and MUST NOT automatically roll back negotiation.

#### Scenario: Published event

- GIVEN a verified `message.published` event
- WHEN it is accepted
- THEN one typed envelope is submitted to the durable bus

#### Scenario: Retraction event

- GIVEN a verified `message.retracted` event
- WHEN it is accepted
- THEN an audit envelope is submitted without rollback action

#### Scenario: Unsupported event

- GIVEN a verified event with another type
- WHEN it is received
- THEN no typed transport envelope is accepted
