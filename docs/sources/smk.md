# SRC-002 — SMK National Gallery of Denmark

Research date: 2026-10-25 (Asia/Taipei)  
Decision: **ACCEPT FOR DEVELOPMENT**, not cleared for unattended collection.  
Registry: https://app.notion.com/p/40349fae448081c6ac26e3ba0f5db9b4  
Detailed Notion specification: https://app.notion.com/p/40449fae44808146b48ae8011dcd3508

## Official sources

- [SMK REST API / examples](https://www.smk.dk/en/article/smk-api/)
- [Swagger](https://api.smk.dk/api/v1/docs/)
- [SMK reuse guidance](https://blog.smk.dk/how-to-do-things-with-data-creative-re-use-of-smks-digitized-collection)
- [SMK rights policy](https://connect.smk.dk/om/rettigheder)
- [Three major museum collections](https://www.smk.dk/section/om-smk/)
- [Collection subject areas](https://www.smk.dk/article/samlingen/)

## Endpoint contract

| Task | URL | Inputs |
|---|---|---|
| Search | `https://api.smk.dk/api/v1/art/search/` | `keys`, `filters`, `offset`, `rows`, `lang` |
| Get object | `https://api.smk.dk/api/v1/art/` | `object_number=KMS1&lang=en` |
| Optional enrichment | `https://enrichment.api.smk.dk/api/enrichment/KMS1?lang=en` | color palette, image tags |
| Image | per-object `image_native` | IIIF or download path as supplied; no URL guessing |

Official browse example:

```text
https://api.smk.dk/api/v1/art/search/?keys=*&filters=[has_image:true],[object_names:maleri],[public_domain:true]&offset=0&rows=30&lang=en
```

Official default `rows=10`; maximum `rows=2000`; reference code defaults to 20. Search returns item records; use `object_number` as durable ID. `offset` is not a stable snapshot cursor: persist all discovered IDs before advancing; scan overlapping windows periodically and de-duplicate.

## Museum taxonomy vs API fields

Official three major collections:
1. Royal Collection of Paintings and Sculpture (paintings/sculptures)
2. Royal Collection of Graphic Art (prints, drawings, works on paper)
3. Royal Cast Collection (plaster casts)

Relevant focus areas: European 1300–1800, Danish/Nordic 1750–1900, Danish/International after 1900, French 1900–1930. These are **museum groupings, not confirmed API enum values**. The officially documented `[object_names:maleri]` means paintings; other object_names must be learned from live fixtures, not inferred.

## Rights gate (non-negotiable)

`public_domain is True` plus a nonempty HTTPS image belonging to SMK. Default requires `image_native` for download; `image_thumbnail` is reference/preview only. Missing rights, missing original image, or unexpected host → reject. Preserve `rights_url` and source metadata. Public Domain Mark (PDM) is a status identifier, **not a CC0 legal waiver**. Modern works may be copyrighted regardless of date/style. Do not treat every API record as eligible.

## Mapping, pending live fixture verification

`object_number → object_id`, `titles/title → title`, `production creator → artist`, `object_names → source_category`, `image_native → image_url`, `public_domain → rights_status: public_domain`. Source_id=`smk`. `enrichment_url` / `colors_palette` should be optional and budgeted separately.

## Usage and reliability

- Public API examples do not require an API key. Open access covers PD digital images.
- **No official numeric per-second or daily quota located. Do not claim unlimited.**
- Research sample safety setting only: 1 request at a time, minimum 2 seconds between requests, 20 records/page, no bulk image download.
- Host budgets needed separately for `api.smk.dk`, `enrichment.api.smk.dk`, `iip.smk.dk`, `iip-thumb.smk.dk`.
- Respect `Retry-After` on HTTP 429; HTTP 403 stops source; 5xx bounded retries. No rotation/proxy bypass.
- For production: persistent next-eligible time, bytes/day, requests/day, queued IDs, SQLite resume, atomic image writes and Notion outbox.

## Verification ledger

| Check | Status |
|---|---|
| Official REST search and details patterns | VERIFIED FROM DOCS |
| Public-domain image reuse policy | VERIFIED FROM DOCS |
| Basic filters, default and max rows | VERIFIED FROM DOCS |
| Numeric rate/daily quota | NOT PUBLISHED; leave unset |
| Live `items`/object detail shape and IIIF image URL | **PENDING LIVE FIXTURE** |
| Mac/NAS real JPEG and dimensions | PENDING |
| Offline mock unit tests | CI VALIDATION |
| Persistent Gateway quotas/checkpoint | NOT IMPLEMENTED |

## L2 single-record live commands

```sh
python -m gallery_download.smk --object-number KMS1
python -m gallery_download.smk --query '*' --limit 5
# Only after policy & host review, explicit one-object test:
python -m gallery_download.smk --object-number KMS1 --download --out ./Artworks
```

Reference adapter is not a production harvest engine. First verify KMS1 response and original availability; failures are evidence and must not trigger probing at scale.
