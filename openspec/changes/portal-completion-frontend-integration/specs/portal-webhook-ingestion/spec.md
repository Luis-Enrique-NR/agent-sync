# Delta for Portal Webhook Ingestion

## MODIFIED Requirements

### Requirement: Verified Webhook Admission

The system MUST obtain the webhook secret server-side via a concrete `WebhookSecretFetcher` class that reads the `PORTAL_SECRET_KEY` environment variable, calls `GET https://api.useportal.co/v1/webhooks/secret` with Bearer auth on first access, caches the secret in memory, and invalidates the cache to re-fetch on any signature verification failure. The system MUST validate `portal-signature` before parsing or accepting a request. Validation MUST use the timestamped HMAC-SHA256 protocol over the exact raw request bytes, constant-time comparison, and a configured timestamp tolerance. A missing, unavailable, or 404 secret MUST fail closed.

(Previously: secret was obtained via a Protocol-only stub; no concrete implementation existed. All test fixtures used `FakeSecret` returning `"t"`.)

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

#### Scenario: Signature failure triggers secret re-fetch

- GIVEN a previously cached webhook secret
- WHEN a webhook request fails HMAC signature verification
- THEN the cached secret is invalidated and re-fetched from Portal before the next verification attempt

## ADDED Requirements

### Requirement: EDA Handler Inspects PortalOutcome Before ACK/FAIL

The system MUST inspects the `PortalOutcome` returned by outbound Portal publish operations in `NegotiationHandler._handle_message_published()`. When the outcome is `PortalRetryable` (HTTP 429 or 5xx) or `PortalUncertain` (timeout), the handler MUST re-raise an exception so the consumer calls `bus.fail()`. When the outcome is `PortalRejected`, the handler MUST log and continue, allowing `bus.ack()`.

#### Scenario: Retryable publish failure triggers fail

- GIVEN a Portal publish returns `PortalRetryable`
- WHEN the handler inspects the outcome
- THEN an exception propagates to the consumer, which calls `bus.fail(delivery, ...)`

#### Scenario: Timeout triggers fail

- GIVEN a Portal publish returns `PortalUncertain`
- WHEN the handler inspects the outcome
- THEN an exception propagates to the consumer for retry via `bus.fail()`

#### Scenario: Permanent rejection is acked

- GIVEN a Portal publish returns `PortalRejected`
- WHEN the handler inspects the outcome
- THEN the rejection is logged and execution continues to `bus.ack(delivery)`
