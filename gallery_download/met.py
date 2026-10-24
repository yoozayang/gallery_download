"""The Met bounded research client. No unattended scheduler or production quota manager."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BASE = "https://collectionapi.metmuseum.org/public/collection"
IMAGE_HOST = "images.metmuseum.org"
UA = "gallery-download-research/0.1 (https://github.com/yoozayang/gallery_download)"


class SourceUnavailable(RuntimeError):
    """Block, rate-limit or outage requiring pause or later retry."""


def _retry_seconds(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    if value.isdecimal():
        return float(value)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return fallback
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return fallback


@dataclass(frozen=True)
class Artwork:
    source_id: str
    object_id: str
    title: str
    artist: str
    department: str
    classification: str
    tags: tuple[str, ...]
    object_url: str
    image_url: str
    image_preview_url: str
    rights: str


def normalize_object(payload: dict) -> Artwork | None:
    """Accept only a PD object with an HTTPS original hosted by The Met."""
    if payload.get("isPublicDomain") is not True or not payload.get("primaryImage"):
        return None
    image_url = payload["primaryImage"]
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or parsed.hostname != IMAGE_HOST:
        return None
    raw_id = payload.get("objectID")
    if type(raw_id) is not int or raw_id < 1:
        return None
    return Artwork(
        source_id="met",
        object_id=str(raw_id),
        title=str(payload.get("title") or ""),
        artist=str(payload.get("artistDisplayName") or ""),
        department=str(payload.get("department") or ""),
        classification=str(payload.get("classification") or ""),
        tags=tuple(str(v.get("term")) for v in payload.get("tags") or []
                   if isinstance(v, dict) and v.get("term")),
        object_url=str(payload.get("objectURL") or
                       f"https://www.metmuseum.org/art/collection/search/{raw_id}"),
        image_url=image_url,
        image_preview_url=str(payload.get("primaryImageSmall") or ""),
        rights="CC0",
    )


class MetClient:
    def __init__(self, *, base: str = BASE, interval: float = 2.0,
                 opener=urlopen, sleep=time.sleep, monotonic=time.monotonic):
        if interval < 0:
            raise ValueError("interval must be >= 0")
        self.base = base.rstrip("/")
        self.interval = interval  # local safety default: 0.5 requests/s
        self.open = opener
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request: float | None = None

    def _get(self, url: str, *, max_bytes: int = 32_000_000, attempts: int = 3) -> bytes:
        for attempt in range(attempts):
            if self._last_request is not None:
                pause = self.interval - (self.monotonic() - self._last_request)
                if pause > 0:
                    self.sleep(pause)
            self._last_request = self.monotonic()
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,image/jpeg"})
            try:
                with self.open(req, timeout=25) as res:
                    length = res.headers.get("Content-Length")
                    if length and int(length) > max_bytes:
                        raise ValueError("response exceeds byte cap")
                    body = res.read(max_bytes + 1)
                    if len(body) > max_bytes:
                        raise ValueError("response exceeds byte cap")
                    return body
            except HTTPError as exc:
                if exc.code in (401, 403):
                    raise SourceUnavailable(f"HTTP {exc.code}: stop and review source policy") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise
                wait = _retry_seconds(exc.headers.get("Retry-After"), min(5 * 2**attempt, 60))
                if attempt == attempts - 1:
                    raise SourceUnavailable(f"HTTP {exc.code}: paused after retries") from exc
                if wait > 300:
                    raise SourceUnavailable(f"HTTP {exc.code}: defer Retry-After={wait:.0f}s") from exc
                self.sleep(wait)
            except URLError as exc:
                if attempt == attempts - 1:
                    raise SourceUnavailable("network unavailable: retry next run") from exc
                self.sleep(min(5 * 2**attempt, 60))
        raise AssertionError("unreachable")

    def departments(self) -> list[dict]:
        return json.loads(self._get(f"{self.base}/v1/departments"))["departments"]

    def search(self, *, query: str, offset: int = 0, limit: int = 20,
               department_id: int | None = None) -> dict:
        if not query.strip():
            raise ValueError("research client requires a query")
        if offset < 0 or not 1 <= limit <= 500 or offset + limit > 10000:
            raise ValueError("Met v1.1 search: offset + limit must be <=10000")
        params = {"q": query, "hasImages": "true", "offset": offset, "limit": limit}
        if department_id is not None:
            params["departmentId"] = department_id
        result = json.loads(self._get(f"{self.base}/v1.1/search?{urlencode(params)}"))
        total = int(result.get("total") or 0)
        return {
            "total": total,
            "object_ids": result.get("objectIDs") or [],
            "next_offset": offset + limit if offset + limit < min(total, 10000) else None,
        }

    def artwork(self, object_id: int) -> Artwork | None:
        if type(object_id) is not int or object_id < 1:
            raise ValueError("object_id must be positive integer")
        return normalize_object(json.loads(self._get(f"{self.base}/v1/objects/{object_id}")))


def save_image(client: MetClient, artwork: Artwork, directory: Path) -> tuple[Path, bool]:
    """Explicit one-object smoke test with SQLite idempotence, not production queue."""
    directory.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(directory / "gallery_history.db")
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS downloads "
            "(source TEXT, object_id TEXT, file TEXT, sha256 TEXT, completed_at TEXT, "
            "PRIMARY KEY(source, object_id))"
        )
        row = conn.execute(
            "SELECT file, sha256 FROM downloads WHERE source=? AND object_id=?",
            (artwork.source_id, artwork.object_id)
        ).fetchone()
        if row and Path(row[0]).is_file():
            path = Path(row[0])
            if hashlib.sha256(path.read_bytes()).hexdigest() == row[1]:
                return path, False
        blob = client._get(artwork.image_url)
        if not blob.startswith(b"\xff\xd8\xff"):
            raise ValueError("download response is not JPEG")
        path = directory / f"{artwork.source_id}_{artwork.object_id}.jpg"
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as temp:
            temp.write(blob)
            partial = Path(temp.name)
        try:
            os.replace(partial, path)
        finally:
            partial.unlink(missing_ok=True)
        conn.execute(
            "INSERT OR REPLACE INTO downloads VALUES (?,?,?,?,?)",
            (artwork.source_id, artwork.object_id, str(path.resolve()),
             hashlib.sha256(blob).hexdigest(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return path, True
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Met single-object research smoke test")
    parser.add_argument("--object-id", type=int, default=436535)
    parser.add_argument("--download", action="store_true", help="explicit download of one CC0 image")
    parser.add_argument("--out", type=Path, default=Path("Artworks"))
    parser.add_argument("--query", help="paginated metadata-only search")
    parser.add_argument("--department-id", type=int)
    args = parser.parse_args()
    client = MetClient()
    if args.query:
        print(json.dumps(client.search(query=args.query, department_id=args.department_id), indent=2))
        return
    artwork = client.artwork(args.object_id)
    if artwork is None:
        raise SystemExit("Object is not Public Domain with an eligible Met original")
    print(json.dumps(artwork.__dict__, ensure_ascii=False, indent=2))
    if args.download:
        path, created = save_image(client, artwork, args.out)
        print(json.dumps({"path": str(path), "downloaded": created}))


if __name__ == "__main__":
    main()
