# SRC-001 — The Metropolitan Museum of Art

- Research: 2026-10-25 (Asia/Taipei)
- **L1:** eligible for controlled Public Domain / CC0 image downloads
- **Engineering:** integration specification ready; live client and full Gateway validation pending
- **Unattended operation:** disabled until acceptance criteria pass

## Official references
- API: https://metmuseum.github.io/
- Open Access: https://www.metmuseum.org/hubs/open-access
- Image resources: https://www.metmuseum.org/policies/image-resources
- Museum terms: https://www.metmuseum.org/policies/terms-and-conditions
- Example record: https://collectionapi.metmuseum.org/public/collection/v1/objects/436535
- Example original: https://images.metmuseum.org/CRDImages/ep/original/DP-42549-001.jpg
- Notion integration spec: https://app.notion.com/p/40349fae44808198b240faa86de8bd2b

## Endpoints
| Purpose | GET endpoint |
|---|---|
| Department lookup | `https://collectionapi.metmuseum.org/public/collection/v1/departments` |
| Paginated search | `https://collectionapi.metmuseum.org/public/collection/v1.1/search` |
| Object detail | `https://collectionapi.metmuseum.org/public/collection/v1/objects/{objectID}` |
| ID listing | `https://collectionapi.metmuseum.org/public/collection/v1/objects` |

Search params: q optional, departmentId, hasImages, tags, title, medium, dateBegin, dateEnd, offset (default 0), limit (default 100, max 500). `offset + limit <= 10000`. Legacy /v1/search was retired 2026-10-01. Full enumeration: /v1/objects or Open Access dataset rather than exceeding paginated search window. Search ordering is not durable; persist IDs per page before checkpoint advance.

Candidate departments from Met docs: Asian Art (6), Drawings and Prints (9), European Paintings (11), Photographs (19), Modern Art (21). Confirm against live departments response. Detail fields: department, classification, objectName, medium, tags, artistDisplayName, period, culture, objectBeginDate.

## Rights and imagery
No API key or registration. `hasImages=true` is **not** a rights check; only accept a detail response with `isPublicDomain === true` and nonempty HTTPS `primaryImage` at `images.metmuseum.org`. `primaryImageSmall` is for previews; original JPEG from `primaryImage`. Open Access image data is offered under CC0; preserve the source record and rights evidence.

## Quota / controls
Official API documentation asks for **no more than 80 requests/second**. Official per-day quota **not stated**; avoid inventing one. 80/s is a ceiling, not operating target. Proposed *local safety default* is 1 concurrent request / at least 2 seconds apart (0.5 req/s), independently throttled API and image hosts. Production Gateway additionally needs configurable daily request/byte caps, persistent next_eligible_at, 429 Retry-After, bounded backoff and repeated 403 shutdown; never evade blocks.

## Mapping / checkpoint
`objectID → object_id:string`, `artistDisplayName → artist`, `primaryImage → image_url`, `objectURL → source_url`, source_id=`met`, rights_status=`public_domain` only after verified flag. SQLite uniqueness `(source_id, object_id)`, supplementary checksum/pHash. Commit page cursor only after all returned IDs are durably queued; if cursor changes, re-enumerate IDs with de-duplication.

## Acceptance status
- [x] Official fields, search migration and rights gate researched
- [x] Example ID 436535, Vincent van Gogh, *Wheat Field with Cypresses* and original image URL identified
- [ ] Live GET/search/object/image smoke test on target Mac/NAS
- [ ] End-to-end SHA256, output dimensions, idempotent resume, image and API budgets
- [ ] Notion failure and quota tests before `Auto Collection=true`

Mocked reference-client testing is not a substitute for live network and persistent Gateway tests.
