import unittest

from gallery_download.contracts import (
    ContractError, eligible_for_download, validate_artwork, validate_curator_decision,
)

ARTWORK = {
    "source_id": "met", "object_id": "436535", "title": "Example",
    "rights_status": "public_domain", "image_url": "https://images.example.org/a.jpg",
}


class ContractTests(unittest.TestCase):
    def test_valid_artwork(self):
        self.assertEqual(validate_artwork(ARTWORK)["source_id"], "met")

    def test_missing_rights_fails_closed(self):
        self.assertFalse(eligible_for_download({k: v for k, v in ARTWORK.items() if k != "rights_status"}, source_approved=True))

    def test_source_must_be_approved(self):
        self.assertFalse(eligible_for_download(ARTWORK, source_approved=False))
        self.assertTrue(eligible_for_download(ARTWORK, source_approved=True))

    def test_restricted_or_non_https_is_rejected(self):
        self.assertFalse(eligible_for_download({**ARTWORK, "rights_status": "restricted"}, source_approved=True))
        self.assertFalse(eligible_for_download({**ARTWORK, "image_url": "http://example.org/a.jpg"}, source_approved=True))

    def test_hallucinated_candidate_id_rejected(self):
        with self.assertRaises(ContractError):
            validate_curator_decision({"candidate_key": "unknown:2", "decision": "include", "score": 80, "reason": "nice"}, candidate_keys={"met:436535"})

    def test_invalid_model_score_rejected(self):
        with self.assertRaises(ContractError):
            validate_curator_decision({"candidate_key": "met:436535", "decision": "include", "score": True, "reason": "nice"}, candidate_keys={"met:436535"})

    def test_valid_curator_decision(self):
        decision = validate_curator_decision({"candidate_key": "met:436535", "decision": "review", "score": 50, "reason": "uncertain"}, candidate_keys={"met:436535"})
        self.assertEqual(decision["decision"], "review")


if __name__ == "__main__":
    unittest.main()
