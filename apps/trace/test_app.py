"""Run: python -m unittest discover -s apps/trace  (no network needed)."""
import unittest

from app import PROBES, caddy_hop_ms, classify_entry, run_probes


class Trace(unittest.TestCase):
    def test_entry_path(self):
        self.assertEqual(classify_entry({"Tailscale-User-Login": "someone@example.com"}), "tailscale")
        self.assertEqual(classify_entry({}), "internet")

    def test_caddy_hop(self):
        self.assertEqual(caddy_hop_ms("1000", 1002.5), 2.5)
        self.assertEqual(caddy_hop_ms("1005", 1000.0), 0.0)  # clock jitter never goes negative
        self.assertIsNone(caddy_hop_ms(None, 1000.0))
        self.assertIsNone(caddy_hop_ms("not-a-number", 1000.0))

    def test_probes_report_failures_without_raising(self):
        def fake(host, port):
            if host == "10.0.1.10":
                raise TimeoutError
            return 4.2
        res = {r["id"]: r for r in run_probes(fake)}
        self.assertEqual(len(res), len(PROBES))
        self.assertTrue(res["internet"]["ok"])
        self.assertEqual(res["internet"]["ms"], 4.2)
        self.assertFalse(res["worker"]["ok"])
        self.assertIn("hasn't launched", res["worker"]["note"])


if __name__ == "__main__":
    unittest.main()
