"""Run: python -m unittest discover -s recon  (no network needed; Telegram is mocked)."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import approval_bridge as bridge
import common

SCOPE = json.dumps({
    "in_scope": [{"asset_identifier": "*.example.com", "asset_type": "WILDCARD",
                  "eligible_for_bounty": True, "max_severity": "high"}],
    "out_of_scope": [],
})


class ApprovalBridge(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_path = path
        self._old_db_path = common.DB_PATH
        common.DB_PATH = self.db_path
        self.conn = common.db()
        self.conn.execute(
            "INSERT INTO programs (handle, name, url, status, scope_json, discovered_at) "
            "VALUES ('testco', 'TestCo', 'https://hackerone.com/testco', 'candidate', ?, 0)",
            (SCOPE,),
        )
        self.conn.commit()

        self._old_scope_dir = bridge.SCOPE_DIR
        self.scope_tmpdir = tempfile.mkdtemp()
        bridge.SCOPE_DIR = self.scope_tmpdir

    def tearDown(self):
        self.conn.close()
        common.DB_PATH = self._old_db_path
        os.unlink(self.db_path)
        bridge.SCOPE_DIR = self._old_scope_dir
        shutil.rmtree(self.scope_tmpdir, ignore_errors=True)

    @mock.patch.object(common, "answer_callback")
    def test_approve_writes_scope_file_and_updates_status(self, answer_callback):
        cb = {"id": "cb1", "data": "appr:testco", "from": {"username": "timsurreal"}}
        bridge.handle_callback(self.conn, cb)

        row = self.conn.execute("SELECT status, decided_by FROM programs WHERE handle = 'testco'").fetchone()
        self.assertEqual(row["status"], "approved")
        self.assertEqual(row["decided_by"], "timsurreal")

        with open(os.path.join(self.scope_tmpdir, "testco.json")) as f:
            scope = json.load(f)
        self.assertEqual(scope["handle"], "testco")
        self.assertEqual(scope["targets"]["in_scope"][0]["asset_identifier"], "*.example.com")
        answer_callback.assert_called_once()

    @mock.patch.object(common, "answer_callback")
    def test_reject_updates_status_without_scope_file(self, answer_callback):
        cb = {"id": "cb2", "data": "rej:testco", "from": {"username": "timsurreal"}}
        bridge.handle_callback(self.conn, cb)

        row = self.conn.execute("SELECT status FROM programs WHERE handle = 'testco'").fetchone()
        self.assertEqual(row["status"], "rejected")
        self.assertFalse(os.path.exists(os.path.join(self.scope_tmpdir, "testco.json")))
        answer_callback.assert_called_once()

    @mock.patch.object(common, "answer_callback")
    def test_unknown_action_is_ignored_safely(self, answer_callback):
        cb = {"id": "cb3", "data": "huh:testco", "from": {"username": "timsurreal"}}
        bridge.handle_callback(self.conn, cb)
        row = self.conn.execute("SELECT status FROM programs WHERE handle = 'testco'").fetchone()
        self.assertEqual(row["status"], "candidate")
        answer_callback.assert_called_once_with("cb3", None)


if __name__ == "__main__":
    unittest.main()
