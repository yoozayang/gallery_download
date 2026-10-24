# Acceptance tests

| Test | Pass criterion |
|---|---|
| unknown rights / bad URL / disabled source | no image download |
| HTTP 429 + Retry-After | defer until permitted |
| recurring HTTP 403 | disable source; no bypass |
| daily API/image quota | stop affected source until next legal window |
| crash mid-page | persisted candidates processed before next page |
| crash during image transfer | .part not counted completed |
| duplicate execution | no duplicate download or Notion page |
| NAS missing / Notion failure | retry unfinished stage only |
| invalid LLM JSON, score or candidate ID | safe review, no direct action |
| final image | exact resolution and undistorted aspect ratio |

MVP release gate: official policy evidence, real Mac/NAS network download and hash/dimensions, durable Gateway rate and resume tests. Unit mocks alone are insufficient.
