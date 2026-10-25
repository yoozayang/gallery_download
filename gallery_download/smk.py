"""SMK L1 reference adapter: bounded metadata queries and optional one-image smoke test.

This is NOT a durable collector. Do not schedule or run unattended until the
production Gateway's persisted quotas, policies and recovery checks are complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contracts import eligible_for_download

API = "https://api.smk.dk/api/v1"
ALLOWED_IMAGE_HOSTS = frozenset({"iip.smk.dk", "iip-thumb.smk.dk", "api.smk.dk"})
UA = "gallery-download-research/0.1 (https://github.com/yoozayang/gallery_download)"
ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


class SmkUnavailable(RuntimeError):
    """Stop the smoke test and review source policy or try again later."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SmkUnavailable(f"HTTP {code} redirect requires manual host review")


def _allowed_image(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_IMAGE_HOSTS and not (
        parsed.username or parsed.password or parsed.port not in (None, 443)
    )


def _text_from_titles(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                for key in ("title", "value", "text"):
                    candidate = item.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
    return ""


def _artist(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("creator", "name", "value"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(value, list):
        return next((x for item in value if (x := _artist(item))), "")
    return ""


def normalize_smk(record: dict[str, Any]) -> dict[str, Any] | None:
    """Fail closed on rights, original availability, object ID and image origin."""
    if not isinstance(record, dict) or record.get("public_domain") is not True:
        return None
    object_number = record.get("object_number")
    if not isinstance(object_number, str) or not ID_PATTERN.fullmatch(object_number):
        return None
    image = record.get("image_native")
    if not _allowed_image(image):
        return None
    title = _text_from_titles(record.get("titles")) or _text_from_titles(record.get("title"))
    if not title:
        return None
    names = record.get("object_names")
    category = _text_from_titles(names) if isinstance(names, (list, str)) else ""
    artwork = {
        "source_id": "smk",
        "object_id": object_number,
        "title": title,
        "artist": _artist(record.get("production")) or _artist(record.get("creator")),
        "source_category": category,
        "source_url": f"https://open.smk.dk/artwork/image/{object_number}",
        "image_url": image,
        "rights_status": "public_domain",
    }
    return artwork if eligible_for_download(artwork, source_approved=True) else None


def retry_seconds(value: str | None, default: float) -> float:
    if not value:
        return default
    if value.isdecimal():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return default
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return default


class SmkClient:
    def __init__(self, *, opener=None, interval: float = 2.0,
                 sleep=time.sleep, monotonic=time.monotonic):
        if interval < 0:
            raise ValueError("interval cannot be negative")
        self.opener = opener or build_opener(NoRedirect()).open
        self.interval = interval
        self.sleep = sleep
        self.monotonic = monotonic
        self.last_request: float | None = None

    def _get(self, url: str, *, limit_bytes: int = 3_000_000, attempts: int = 3) -> bytes:
        for attempt in range(attempts):
            if self.last_request is not None:
                delay = self.interval - (self.monotonic() - self.last_request)
                if delay > 0:
                    self.sleep(delay)
            self.last_request = self.monotonic()
            try:
                request = Request(url, headers={"User-Agent": UA})
                with self.opener(request, timeout=25) as response:
                    length = response.headers.get("Content-Length")
                    if length and int(length) > limit_bytes:
                        raise ValueError("response exceeds configured byte cap")
                    data = response.read(limit_bytes + 1)
                    if len(data) > limit_bytes:
                        raise ValueError("response exceeds configured byte cap")
                    return data
            except HTTPError as exc:
                if exc.code in (401, 403):
                    raise SmkUnavailable(f"HTTP {exc.code}: stop source") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise
                delay = retry_seconds(exc.headers.get("Retry-After"), 5 * (2 ** attempt))
                if attempt == attempts - 1 or delay > 120:
                    raise SmkUnavailable(f"HTTP {exc.code}: defer to next run") from exc
                self.sleep(delay)
            except URLError as exc:
                if attempt == attempts - 1:
                    raise SmkUnavailable("network unavailable") from exc
                self.sleep(5 * (2 ** attempt))
        raise AssertionError("unreachable")

    def search(self, *, query: str = "*", offset: int = 0,
               rows: int = 20, paintings_only: bool = False) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if offset < 0 or not 1 <= rows <= 2000:
            raise ValueError("SMK rows must be 1..2000 and offset nonnegative")
        filters = ["[has_image:true]", "[public_domain:true]"]
        if paintings_only:
            filters.append("[object_names:maleri]")
        params = {"keys": query, "filters": ",".join(filters),
                  "offset": offset, "rows": rows, "lang": "en"}
        url = f"{API}/art/search/?{urlencode(params)}"
        data = json.loads(self._get(url))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("unexpected SMK search shape; save live fixture")
        items = data["items"]
        if not all(isinstance(item, dict) for item in items):
            raise ValueError("unexpected SMK search item")
        total = data.get("total")
        next_offset = offset + len(items) if len(items) == rows and (
            type(total) is not int or offset + len(items) < total
        ) else None
        return {"items": items, "total": total, "next_offset": next_offset}

    def object(self, object_number: str) -> dict[str, Any]:
        if not isinstance(object_number, str) or not ID_PATTERN.fullmatch(object_number):
            raise ValueError("invalid SMK object_number")
        url = f"{API}/art/?{urlencode({'object_number': object_number, 'lang': 'en'})}"
        data = json.loads(self._get(url))
        if not isinstance(data, dict):
            raise ValueError("unexpected SMK object response")
        return data


def download_one(client: SmkClient, record: dict[str, Any], out: Path) -> tuple[Path, bool]:
    """Explicitly approved single JPEG test; durable multi-source use belongs to Gateway."""
    work = normalize_smk(record)
    if work is None:
        raise ValueError("work is not eligible for download")
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(out / "gallery_history.db")
    try:
        db.execute("CREATE TABLE IF NOT EXISTS smoke_downloads "
                   "(source TEXT, object_id TEXT, path TEXT, sha256 TEXT, "
                   "PRIMARY KEY(source,object_id))")
        row = db.execute("SELECT path,sha256 FROM smoke_downloads WHERE source=? AND object_id=?",
                         (work["source_id"], work["object_id"])).fetchone()
        if row and Path(row[0]).is_file():
            path = Path(row[0])
            if hashlib.sha256(path.read_bytes()).hexdigest() == row[1]:
                return path, False
        data = client._get(work["image_url"], limit_bytes=24_000_000)
        if not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("image is not a JPEG")
        path = out / f"smk_{work['object_id']}.jpg"
        with tempfile.NamedTemporaryFile(mode="wb", dir=out, suffix=".part", delete=False) as file:
            file.write(data)
            temp = Path(file.name)
        try:
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        db.execute("INSERT OR REPLACE INTO smoke_downloads VALUES(?,?,?,?)",
                   ("smk", work["object_id"], str(path.resolve()), hashlib.sha256(data).hexdigest()))
        db.commit()
        return path, True
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SMK single-object research smoke test")
    parser.add_argument("--object-number", default="KMS1")
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--download", action="store_true",
                        help="explicitly download one PD original; do not schedule")
    parser.add_argument("--out", type=Path, default=Path("Artworks"))
    args = parser.parse_args()
    client = SmkClient()
    if args.query is not None:
        result = client.search(query=args.query, rows=args.limit)
        print(json.dumps({"total": result["total"], "count": len(result["items"]),
                          "next_offset": result["next_offset"]}, indent=2))
        return
    raw = client.object(args.object_number)
    work = normalize_smk(raw)
    if work is None:
        raise SystemExit("No approved public-domain image_native; inspect original response")
    print(json.dumps(work, indent=2, ensure_ascii=False))
    if args.download:
        path, new = download_one(client, raw, args.out)
        print(json.dumps({"path": str(path), "downloaded": new}))


if __name__ == "__main__":
    main()
