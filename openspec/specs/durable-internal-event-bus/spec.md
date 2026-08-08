# Durable Internal Event Bus Specification

## Purpose

Preserve accepted transport envelopes for restart-safe, at-least-once Backend API processing.

## Requirements

### Requirement: Atomic Durable Acceptance

The system MUST use Redis as the internal durable bus. It MUST atomically record a Portal event ID and its pending envelope so that a delivery is accepted once or not accepted at all.

#### Scenario: Duplicate delivery

- GIVEN a pending envelope for Portal event ID `E`
- WHEN another verified delivery with ID `E` arrives
- THEN exactly one pending envelope remains

#### Scenario: Atomic failure

- GIVEN a verified event cannot be durably accepted
- WHEN acceptance is attempted
- THEN neither its ID nor a pending envelope is recorded

### Requirement: Restart-Safe Consumption

The system MUST retain pending envelopes through API and worker restarts. A consumer MUST acknowledge only completed work; failed or unacknowledged work MUST remain observable for retry or failure handling.

#### Scenario: Restart survival

- GIVEN an accepted envelope has not been acknowledged
- WHEN the API or worker restarts
- THEN a consumer can receive that envelope

#### Scenario: Acknowledge and failure

- GIVEN a consumer receives an envelope
- WHEN processing succeeds or fails
- THEN only success removes it from pending delivery
