# Portal Administration Client Specification

## Purpose

Execute explicitly authorized Portal administration commands through a network-independent transport seam.

## Requirements

### Requirement: Authorized Documented Commands

The system MUST execute publishing and access commands only when explicitly authorized by Backend API or Matchmaking and documented by Portal. It MUST fail closed for undocumented commands or unknown request shapes.

#### Scenario: Authorized publish or access command

- GIVEN an authorized, documented command
- WHEN the Backend API or Matchmaking submits it
- THEN the transport executes the corresponding Portal operation

#### Scenario: Unsupported command

- GIVEN an undocumented command or unknown access shape
- WHEN it is submitted
- THEN the transport refuses it without a Portal call

### Requirement: Real and Fake Adapter Parity

The system MUST expose equivalent public command outcomes through real and fake adapters. The fake adapter MUST support offline verification without network access.

#### Scenario: Fake adapter command

- GIVEN a documented authorized command and fake adapter
- WHEN the command is submitted
- THEN its observable outcome matches the adapter contract offline

### Requirement: Transport Authority Boundary

The system MUST NOT decide AI Brain invocation, negotiation outcome, channel lifecycle, or access policy. It MUST execute only submitted commands.

#### Scenario: Unauthorised business decision

- GIVEN a normalized event without a Backend-authorized command
- WHEN transport processing completes
- THEN no AI invocation, access change, or publication is initiated
