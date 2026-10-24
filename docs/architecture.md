# Architecture and ownership

- **L1 GPT-6:** official API/category/license/limit research and per-source integration specs.
- **L2 Coding Agent:** adapters, Gateway, quota/checkpoint, SQLite, image pipeline, sync, tests.
- **L3:** deterministic Python executes; local small model classifies bounded candidates and summarizes daily statuses. It never calls source APIs or changes policy.

```text
Scheduler → Gateway → Source Adapter → NormalizedArtwork → Rights/Quality
                                              ↓
                                        Optional Curator
                                              ↓
Download → Pillow → Local/NAS → Notion outbox
```

Adapter owns source-specific search/detail/rights mappings. Gateway owns HTTP client limits (per source and API/image host), queues, recoverable checkpoints, failures and persistence. Shared IIIF/image code is reusable.

Proposed state: `source_state(source_id, query_key, cursor, quota_window, used, next_eligible_at)`; `artwork_jobs(source_id, object_id, rights_status, decision, status, path, sha256, last_error)`. Persist all candidates from a page before checkpoint advancement. Image downloads use .part + validate + atomic rename. Sync stage independent.

**Implementation state:** only the pure contract validators and research notes are baseline; full Gateway remains future work.
