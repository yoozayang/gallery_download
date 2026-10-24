# SRC-XXX — Source Integration Specification

- Status: research / dev-ready / live-verified / disabled
- Source ID / record URL / verified date:

## Official sources and rights
API docs, image license, automation terms, metadata vs image rights, exact evidence URLs.

## API and taxonomy
Host, auth, headers, search, pagination, official classes/departments, response sample, normalized field map.

## Usage controls
Documented per-second/day API and image limits, concurrency, Retry-After, 403, 429, 5xx, quota reset and User-Agent requirements. Unknown = unknown; never assume unlimited.

## Recovery and data model
Stable source ID, cursor validity, checkpoint, changed-since strategy, de-dup key and item states.

## Image download
Image URL formation, rights predicate, allowed hosts, sizes/formats, checksum, atomic write and restrictions.

## Verification and L2 handoff
Example object IDs, rights evidence, mocked tests, target Mac/NAS live tests, unresolved assumptions, adapter signatures and readiness gate. Default unattended automation disabled.
