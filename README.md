# E-Ink Gallery Download

Incremental, rights-aware artwork curation for **E Ink Spectra 6** (800×480 landscape / 480×800 portrait).

## Status

**Planning / contract baseline (v0.1.0-draft).** No source adapter or unattended downloader is enabled yet. Official API, image reuse and rate-limit rules must be verified per source before live harvesting.

## Documentation

- [Software requirements](docs/SRS.md)
- [Architecture and ownership](docs/architecture.md)
- [Source integration specification template](docs/sources/SOURCE_SPEC_TEMPLATE.md)
- [Acceptance test plan](docs/acceptance.md)
- [Normalized artwork contract](schemas/artwork.schema.json)
- [Local curator decision contract](schemas/curator_decision.schema.json)

Notion: [Project SRS](https://app.notion.com/p/40349fae448081cd9b8ed95359b7a31b) · [Source registry](https://app.notion.com/p/2906d090d1be42ca9b2438948552acf2)

## Responsibility split

- **L1 (research):** source API, classification, rights and quota research with official evidence.
- **L2 (engineering):** adapters, shared gateway, persistence, download processing, tests.
- **L3 (operations):** deterministic Python execution; small local model limited to curation and daily summaries.

## Development baseline

Python 3.11+. Standard-library-only contract validation:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

No API tokens, downloaded images, SQLite state, or private NAS paths belong in this repository.

## Planned sequence

The Met source research → shared contract and deterministic MVP → SMK integration validation → modern-art sources → local-model evaluation → guarded automation.
