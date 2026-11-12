"""Run: python -m unittest discover -s recon  (no network needed; Telegram is mocked)."""
import os
import tempfile
import unittest
from unittest import mock

import common
import scout


def make_program(handle, name=None, broad=True):
    return {
        "handle": handle, "name": name or handle, "url": f"https://hackerone.com/{handle}",
        "submission_state": "open", "offers_bounties": True, "response_efficiency_percentage": 80,
        "targets": {
            "in_scope": [{"asset_type": "WILDCARD" if broad else "SOURCE_CODE",
                          "eligible_for_bounty": True, "max_severity": "high"}],
            "out_of_scope": [],
        },
    }


PROGRAM = make_program("testco", "TestCo")
NARROW_PROGRAM = make_program("narrowco", "NarrowCo", broad=False)


class ScoutRun(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self._old_db_path = common.DB_PATH
        common.DB_PATH = self.db_path
        self.conn = common.db()

    def tearDown(self):
        self.conn.close()
        common.DB_PATH = self._old_db_path
        os.unlink(self.db_path)

    @mock.patch.object(common, "send_message", return_value={"result": {"message_id": 42}})
    def test_pings_qualifying_program_and_skips_narrow_one(self, send_message):
        seen, checked, pinged = scout.run([PROGRAM, NARROW_PROGRAM], self.conn)
        self.assertEqual((seen, checked, pinged), (2, 1, 1))
        send_message.assert_called_once()

        rows = {r["handle"]: r["status"] for r in self.conn.execute("SELECT handle, status FROM programs")}
        self.assertEqual(rows, {"testco": "candidate", "narrowco": "skipped"})

        approvals = self.conn.execute("SELECT program_handle, telegram_message_id FROM approvals").fetchall()
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["program_handle"], "testco")
        self.assertEqual(approvals[0]["telegram_message_id"], 42)

    @mock.patch.object(common, "send_message", return_value={"result": {"message_id": 1}})
    def test_rerun_does_not_requeue_reskip_or_reping(self, send_message):
        scout.run([PROGRAM, NARROW_PROGRAM], self.conn)
        scout.run([PROGRAM, NARROW_PROGRAM], self.conn)
        send_message.assert_called_once()
        count = self.conn.execute("SELECT COUNT(*) AS n FROM programs").fetchone()["n"]
        self.assertEqual(count, 2)

    @mock.patch.object(common, "send_message", return_value={"result": {"message_id": 1}})
    def test_large_backlog_is_rate_limited_per_run(self, send_message):
        programs = [make_program(f"co{i}") for i in range(25)]
        seen, checked, pinged = scout.run(programs, self.conn, ping_limit=10)
        self.assertEqual((seen, checked, pinged), (25, 25, 10))
        self.assertEqual(send_message.call_count, 10)

        backlog = self.conn.execute(
            "SELECT COUNT(*) AS n FROM programs WHERE status = 'candidate' AND pinged = 0"
        ).fetchone()["n"]
        self.assertEqual(backlog, 15)

        # a later run (e.g. the next day) drains more of the backlog, oldest first,
        # without re-running stage 1 or re-pinging what's already gone out
        seen2, checked2, pinged2 = scout.run([], self.conn, ping_limit=10)
        self.assertEqual((seen2, checked2, pinged2), (0, 0, 10))
        self.assertEqual(send_message.call_count, 20)


if __name__ == "__main__":
    unittest.main()
