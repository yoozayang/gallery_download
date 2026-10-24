import io
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from gallery_download.met import MetClient, SourceUnavailable, normalize_object, save_image


class Reply:
    def __init__(self, body):
        self.buf = io.BytesIO(body)
        self.headers = {"Content-Length": str(len(body))}
    def __enter__(self): return self
    def __exit__(self, *_): self.buf.close()
    def read(self, size): return self.buf.read(size)


class TestMet(unittest.TestCase):
    def test_public_domain_only(self):
        obj = {"objectID": 436535, "title": "Test", "isPublicDomain": True,
               "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/test.jpg"}
        self.assertEqual(normalize_object(obj).object_id, "436535")
        self.assertIsNone(normalize_object({**obj, "isPublicDomain": False}))
        self.assertIsNone(normalize_object({**obj, "primaryImage": "https://untrusted.invalid/x.jpg"}))

    def test_search_v11_and_window(self):
        urls = []
        def opener(req, timeout):
            urls.append(req.full_url)
            return Reply(b'{"total":4,"objectIDs":[1,2]}')
        client = MetClient(opener=opener, interval=0)
        self.assertEqual(client.search(query="flowers", limit=2, department_id=11)["next_offset"], 2)
        self.assertIn("/v1.1/search?", urls[0])
        self.assertIn("departmentId=11", urls[0])
        with self.assertRaises(ValueError):
            client.search(query="flowers", offset=9600, limit=500)

    def test_403_stops(self):
        def opener(req, timeout):
            raise HTTPError(req.full_url, 403, "blocked", {}, None)
        with self.assertRaises(SourceUnavailable):
            MetClient(opener=opener, interval=0).artwork(436535)

    def test_429_retry_after(self):
        calls, sleeps = [], []
        def opener(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                raise HTTPError(req.full_url, 429, "slow", {"Retry-After": "3"}, None)
            return Reply(b'{"objectID":436535,"isPublicDomain":false}')
        self.assertIsNone(MetClient(opener=opener, interval=0, sleep=sleeps.append).artwork(436535))
        self.assertEqual(sleeps, [3.0])

    def test_download_idempotent(self):
        jpeg = b"\xff\xd8\xff" + b"testdata"
        client = MetClient(opener=lambda req, timeout: Reply(jpeg), interval=0)
        art = normalize_object({"objectID": 436535, "isPublicDomain": True,
                                "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/test.jpg"})
        with tempfile.TemporaryDirectory() as tmp:
            p1, first = save_image(client, art, Path(tmp))
            p2, second = save_image(client, art, Path(tmp))
            self.assertEqual(p1, p2)
            self.assertTrue(first)
            self.assertFalse(second)


if __name__ == "__main__":
    unittest.main()
