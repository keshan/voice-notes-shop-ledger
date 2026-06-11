import unittest

from shop_ledger.insights import compute_metrics, followup_rows, risk_flags


ROWS = [
    {
        "direction": "expense",
        "payment_status": "paid",
        "amount": 1200,
        "currency": "LKR",
        "counterparty": "Ravi",
        "item": "rice bags",
        "category": "inventory",
        "confidence": 0.9,
    },
    {
        "direction": "income",
        "payment_status": "due",
        "amount": 7500,
        "currency": "LKR",
        "counterparty": "Nimal",
        "item": "tea packets",
        "category": "sales",
        "confidence": 0.8,
        "reminder": "Follow up with Nimal about LKR 7,500.",
    },
]


class InsightTests(unittest.TestCase):
    def test_metrics_include_cash_and_followups(self):
        metrics = compute_metrics(ROWS)

        self.assertEqual(metrics["paid_expense"], 1200)
        self.assertEqual(metrics["due_income"], 7500)
        self.assertEqual(metrics["open_followups"], 1)

    def test_followup_rows_include_script_and_priority(self):
        queue = followup_rows(ROWS)

        self.assertEqual(queue[0]["priority"], "High")
        self.assertIn("Nimal", queue[0]["script"])

    def test_risk_flags_include_high_value_due(self):
        flags = risk_flags(ROWS)

        self.assertTrue(any("High-value due item" in flag for flag in flags))


if __name__ == "__main__":
    unittest.main()
