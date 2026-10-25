"""Offline, no-network contract and resilience tests for SMK."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from gallery_download.smk import (
    SmkClient, SmkUnavailable, download_one, normalize_smk, retry_seconds,
)


ITEM = {
    "object_number": "KMS1",
    "titles": [{"title": "The Fall of the Titans", "language": "en"}],
    "production": [{"creator": "Cornelisz van Haarlem"}],
    "object_names": ["maleri"],
    "public_domain": True,
    "has_image": True,
    "rights_url": "https://creativecommons.org/publicdomain/mark/1.0/",
    "image_native": "https://iip.smk.dk/iiif/jp2/KMS1.jp2/full/full/0/default.jpg",
    "image_thumbnail": "https://iip-thumb.smk.dk/iiif/jp2/KMS1.jp2/full/!1024,/0/default.jpg",
}


class Response:
    def __init__(self, blob):
        self.buf = io.BytesIO(blob)
        self.headers = {"Content-Length": str(len(blob))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.buf.close()

    def read(self, size):
        return self.buf.read(size)


class SmkTests(unittest.TestCase):
    def test_public_domain_image_and_id(self):
        item = normalize_smk(ITEM)
        self.assertEqual(item["source_id"], "smk")
        self.assertEqual(item["object_id"], "KMS1")
        self.assertEqual(item["rights_status"], "public_domain")
        self.assertEqual(item["title"], "The Fall of the Titans")

    def test_missing_rights_cannot_download(self):
        self.assertIsNone(normalize_smk({**ITEM, "public_domain": False}))
        self.assertIsNone(normalize_smk({k: v for k, v in ITEM.items() if k != "public_domain"}))

    def test_missing_original_cannot_download(self):
        self.assertIsNone(normalize_smk({**ITEM, "image_native": None}))

    def test_cross_host_and_http_images_rejected(self):
        for url in ("http://iip.smk.dk/foo.jpg", "https://evil.invalid/a.jpg",
                    "https://iip.smk.dk.evil.invalid/a.jpg"):
            self.assertIsNone(normalize_smk({**ITEM, "image_native": url}))

    def test_bad_identifier_rejected(self):
        self.assertIsNone(normalize_smk({**ITEM, "object_number": "../../unsafe"}))

    def test_search_query_uses_official_filters(self):
        observed = []
        def opener(request, timeout):
            observed.append(request.full_url)
            return Response(json.dumps({"total": 2, "items": [ITEM]}).encode())
        result = SmkClient(opener=opener, interval=0).search(
            query="*", rows=2, paintings_only=True)
        self.assertEqual(len(result["items"]), 1)
        self.assertIsNone(result["next_offset"])
        self.assertIn("/art/search/", observed[0])
        self.assertIn("%5Bpublic_domain%3Atrue%5D", observed[0])
        self.assertIn("%5Bobject_names%3Amaleri%5D", observed[0])

    def test_search_next_offset(self):
        client = SmkClient(
            opener=lambda request, timeout: Response(json.dumps(
                {"total": 30, "items": [ITEM, ITEM]}).encode()), interval=0)
        self.assertEqual(client.search(rows=2)["next_offset"], 2)

    def test_search_row_limit(self):
        with self.assertRaises(ValueError):
            SmkClient(interval=0).search(rows=2001)

    def test_object_lookup_query(self):
        observed = []
        def opener(request, timeout):
            observed.append(request.full_url)
            return Response(json.dumps(ITEM).encode())
        output = SmkClient(opener=opener, interval=0).object("KMS1")
        self.assertTrue(output["public_domain"])
        self.assertIn("object_number=KMS1", observed[0])

    def test_403_stops(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 403, "blocked", {}, None)
        with self.assertRaises(SmkUnavailable):
            SmkClient(opener=opener, interval=0).object("KMS1")

    def test_429_retry_after(self):
        calls, slept = [], []
        def opener(request, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, "rate", {"Retry-After": "4"}, None)
            return Response(json.dumps(ITEM).encode())
        SmkClient(opener=opener, interval=0, sleep=slept.append).object("KMS1")
        self.assertEqual(slept, [4.0])

    def test_long_429_defers(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 429, "rate", {"Retry-After": "240"}, None)
        with self.assertRaises(SmkUnavailable):
            SmkClient(opener=opener, interval=0).object("KMS1")

    def test_single_jpeg_idempotence(self):
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            return Response(b"\xff\xd8\xff" + b"mock-image")
        client = SmkClient(opener=opener, interval=0)
        with tempfile.TemporaryDirectory() as dir:
            path1, done1 = download_one(client, ITEM, Path(dir))
            path2, done2 = download_one(client, ITEM, Path(dir))
            self.assertTrue(done1)
            self.assertFalse(done2)
            self.assertEqual(path1, path2)
            self.assertEqual(len(calls), 1)

    def test_invalid_image_magic(self):
        client = SmkClient(opener=lambda request, timeout: Response(b"<html/>"), interval=0)
        with tempfile.TemporaryDirectory() as dir:
            with self.assertRaises(ValueError):
                download_one(client, ITEM, Path(dir))

    def test_retry_seconds_invalid(self):
        self.assertEqual(retry_seconds("not-a-date", 5), 5)


if __name__ == "__main__":
    unittest.main()
