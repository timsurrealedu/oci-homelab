"""Run: python -m unittest discover -s recon  (no network needed)."""
import unittest

from filters import passes_structural_filter

BASE = {
    "handle": "x", "submission_state": "open", "offers_bounties": True,
    "response_efficiency_percentage": 80,
    "targets": {"in_scope": [{"asset_type": "WILDCARD", "eligible_for_bounty": True, "max_severity": "critical"}]},
}


class StructuralFilter(unittest.TestCase):
    def test_passes_good_program(self):
        ok, reasons = passes_structural_filter(BASE)
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

    def test_rejects_closed_submissions(self):
        ok, reasons = passes_structural_filter({**BASE, "submission_state": "closed"})
        self.assertFalse(ok)
        self.assertIn("not accepting submissions", reasons)

    def test_rejects_no_bounty_vdp(self):
        ok, reasons = passes_structural_filter({**BASE, "offers_bounties": False})
        self.assertFalse(ok)

    def test_rejects_low_response_efficiency(self):
        ok, reasons = passes_structural_filter({**BASE, "response_efficiency_percentage": 10})
        self.assertFalse(ok)

    def test_rejects_no_broad_scope(self):
        narrow = {**BASE, "targets": {"in_scope": [{"asset_type": "SOURCE_CODE", "eligible_for_bounty": True}]}}
        ok, reasons = passes_structural_filter(narrow)
        self.assertFalse(ok)

    def test_scope_asset_not_eligible_for_bounty_does_not_count(self):
        narrow = {**BASE, "targets": {"in_scope": [{"asset_type": "WILDCARD", "eligible_for_bounty": False}]}}
        ok, reasons = passes_structural_filter(narrow)
        self.assertFalse(ok)

    def test_missing_response_efficiency_does_not_fail(self):
        ok, reasons = passes_structural_filter({**BASE, "response_efficiency_percentage": None})
        self.assertTrue(ok, reasons)


if __name__ == "__main__":
    unittest.main()
