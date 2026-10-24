# E-Ink Gallery Download

Incremental Public Domain / CC0 image curation for **E Ink Spectra 6** (800×480 landscape / 480×800 portrait).

**Status:** specification / research smoke-test baseline. No production Gateway or unattended collection is enabled. The Met has a bounded single-object client; live download from Mac/NAS remains to be tested.

## Documents
- [SRS](docs/SRS.md) · [Architecture](docs/architecture.md) · [Acceptance](docs/acceptance.md)
- [The Met integration specification](docs/sources/met.md) · [Source template](docs/sources/SOURCE_SPEC_TEMPLATE.md)
- [Artwork schema](schemas/artwork.schema.json) · [Curator decision schema](schemas/curator_decision.schema.json)
- [Notion SRS](https://app.notion.com/p/40349fae448081cd9b8ed95359b7a31b) · [Source registry](https://app.notion.com/p/2906d090d1be42ca9b2438948552acf2)

## Role ownership
L1 GPT-6 researches each API/policy and produces integration specifications. L2 Coding Agent develops Gateway and adapters, with tests. L3 deterministic Python executes; local small model scores candidates and reviews daily summaries.

## Test locally (Python 3.11+; standard library)
```sh
python -m unittest discover -s tests -v
python -m gallery_download.met --object-id 436535
# Explicitly download a single rights-eligible item:
python -m gallery_download.met --object-id 436535 --download --out ./Artworks
```

The Met client is a research smoke test, not a persistent multi-source scheduler or compliant production rate manager. Do not schedule automated downloads until source policy, Gateway quotas, durable checkpoints and acceptance tests pass.

No API keys, user images, local SQLite or NAS paths belong in this repository.
