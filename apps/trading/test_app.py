"""Run: python -m unittest discover -s apps/trading  (no network needed)."""
import json
import unittest

from app import NotPaper, build_summary

CONFIG = {"dry_run": True, "strategy": "S", "timeframe": "1h", "exchange": "okx", "stake_currency": "USDT",
          "jwt_secret_key": "nope", "api_server": {"password": "nope"}}
PROFIT = {"closed_trade_count": 3, "winrate": 1 / 3, "profit_factor": 0.5, "best_pair": "BNB/USDT"}
BALANCE = {"starting_capital": 1000.0, "total": 950.0, "starting_capital_pct": -5.0}


def trade(i, profit_abs, is_open=False):
    return {"trade_id": i, "pair": f"P{i}/USDT", "is_open": is_open, "open_timestamp": i * 10,
            "close_timestamp": None if is_open else i * 10 + 5, "profit_pct": profit_abs / 10,
            "profit_abs": profit_abs, "exit_reason": "roi", "amount": 1.0, "fee_open": 0.001}


class Summary(unittest.TestCase):
    def test_equity_curve_and_drawdown(self):
        s = build_summary(CONFIG, PROFIT, BALANCE, [], [trade(2, -100), trade(1, 50), trade(3, 0)])
        self.assertEqual([v for _, v in s["equity"]], [1000.0, 1050.0, 950.0, 950.0])
        self.assertEqual(s["summary"]["max_drawdown_pct"], round(100 / 1050 * 100, 1))
        self.assertEqual([t["pair"] for t in s["recent"]], ["P3/USDT", "P2/USDT", "P1/USDT"])
        self.assertEqual(s["equity"][-1][1], BALANCE["total"])  # curve ends at the wallet balance

    def test_open_trades_not_in_equity(self):
        s = build_summary(CONFIG, PROFIT, BALANCE, [trade(9, 5, True)], [trade(1, 10), trade(9, 5, True)])
        self.assertEqual(len(s["equity"]), 2)
        self.assertEqual(s["open"][0]["pair"], "P9/USDT")

    def test_only_whitelisted_fields(self):
        out = json.dumps(build_summary(CONFIG, PROFIT, BALANCE, [], [trade(1, 10)]))
        for leaked in ("nope", "password", "jwt", "amount", "fee_open", "trade_id"):
            self.assertNotIn(leaked, out)

    def test_refuses_live_bot(self):
        for dry in (False, None):
            with self.subTest(dry_run=dry), self.assertRaises(NotPaper):
                build_summary({**CONFIG, "dry_run": dry}, PROFIT, BALANCE, [], [])


if __name__ == "__main__":
    unittest.main()
