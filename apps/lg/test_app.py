"""Run: python -m unittest discover apps/lg  (no network needed)."""
import unittest

from app import Rejected, build_command, resolve_public


class TargetValidation(unittest.TestCase):
    def test_rejects_non_public_addresses(self):
        for t in ["10.0.0.165", "10.0.1.10", "127.0.0.1", "169.254.169.254", "100.112.185.21",
                  "192.168.1.1", "0.0.0.0", "::1", "fd7a:115c:a1e0::1", "224.0.0.1", "localhost"]:
            with self.subTest(t=t), self.assertRaises(Rejected):
                resolve_public(t)

    def test_rejects_flags_and_shell_text(self):
        for t in ["-c 100", "--help", "a;b", "$(id)", "a b", "x" * 300, ""]:
            with self.subTest(t=t), self.assertRaises(Rejected):
                build_command("ping", t)

    def test_public_ip_passes_through_unchanged(self):
        self.assertEqual(build_command("ping", " 1.1.1.1 "), ["ping", "-c", "4", "-W", "2", "1.1.1.1"])
        self.assertEqual(build_command("mtr", "8.8.8.8")[-1], "8.8.8.8")

    def test_dns(self):
        self.assertEqual(build_command("dns", "example.com", "MX")[-2:], ["example.com", "MX"])
        with self.assertRaises(Rejected):
            build_command("dns", "example.com", "AXFR")
        with self.assertRaises(Rejected):
            build_command("dns", "-x", "A")

    def test_unknown_tool(self):
        with self.assertRaises(Rejected):
            build_command("nmap", "1.1.1.1")


if __name__ == "__main__":
    unittest.main()
