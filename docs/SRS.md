# Software Requirements Specification

Version: 0.1.0-draft · Status: Baseline

## Scope
Incremental Public Domain / CC0 image collection for Spectra 6 (800×480 landscape / 480×800 portrait), Mac/NAS storage, SQLite operational state and Notion catalog. Modern geometric/Art Deco/poster/Japanese-print styles prioritized; classical works remain in scope.

## Functional Requirements
| ID | Requirement | Acceptance |
|---|---|---|
| FR-001 | Only validated sources with reviewed automation policy may run | unapproved sources issue zero requests |
| FR-002 | Adapters normalize work IDs, title, image and rights | adapter conformance tests |
| FR-003 | Explicit PD/CC0 rights and eligible image required before download | missing/unknown rights rejected |
| FR-004 | Per-host/source budgets, Retry-After, 403/429 handling | simulated quota and block tests |
| FR-005 | Durable queued IDs and page checkpoints | resume without missed work |
| FR-006 | De-duplicate by (source_id, object_id), checksum/pHash optionally | same work not downloaded twice |
| FR-007 | Correct orientation, LANCZOS scaling, matte and color mode | 800×480 / 480×800 outputs |
| FR-008 | Independent download/process/Notion sync status | sync outage doesn't re-download |
| FR-009 | Local curator returns strictly validated decision JSON | invalid response moves to review |
| FR-010 | Daily summary, exception and curator queues | parseable outputs |
| FR-011 | Configurable sources, dry-run, resume, max-items | CLI/config tests |

## Nonfunctional Requirements
| ID | Requirement |
|---|---|
| NFR-001 | Unknown source policy or rights disables unattended processing |
| NFR-002 | Respect server quotas; never work around blocks; cautious concurrency |
| NFR-003 | Idempotent restart across network, crash, NAS and Notion errors |
| NFR-004 | Persist provenance, rights evidence, timestamps and errors |
| NFR-005 | Isolate failures; degrade safely when the small model is unavailable |
| NFR-006 | No secrets, images, database state or NAS details in Git |

## Phases
M0 researched Met/SMK sources; M1 Met deterministic end-to-end MVP; M2 SMK validates adapter; M3 local curation and summaries; M4 guarded scheduled automation.

Notion SRS: https://app.notion.com/p/40349fae448081cd9b8ed95359b7a31b
