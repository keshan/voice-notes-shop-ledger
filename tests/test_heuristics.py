import unittest

from shop_ledger.heuristics import heuristic_extract


class HeuristicExtractionTests(unittest.TestCase):
    def test_extracts_multiple_rows_and_due_reminder(self):
        result = heuristic_extract(
            "paid Ravi 1200 for rice bags, customer Nimal owes 750 for tea packets"
        )

        self.assertEqual(len(result.entries), 2)
        self.assertEqual(result.entries[0].amount, 1200)
        self.assertEqual(result.entries[0].direction, "expense")
        self.assertEqual(result.entries[1].amount, 750)
        self.assertEqual(result.entries[1].payment_status, "due")
        self.assertTrue(result.reminders)

    def test_missing_amount_adds_question(self):
        result = heuristic_extract("paid Ravi for rice bags")

        self.assertEqual(result.entries[0].amount, 0)
        self.assertTrue(result.questions)


if __name__ == "__main__":
    unittest.main()
