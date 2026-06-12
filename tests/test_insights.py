import unittest

from shop_ledger.insights import (
    answer_ledger_question,
    build_chart_plan,
    build_counterparty_memory_markdown,
    build_daily_brief_markdown,
    build_insight_figures,
    build_timeline_markdown,
    compute_metrics,
    counterparty_memory_cards,
    daily_brief_fallback,
    followup_rows,
    review_rows,
    risk_flags,
    timeline_figure,
    timeline_rows,
)


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
        self.assertIn("polite_script", queue[0])
        self.assertIn("friendly_script", queue[0])
        self.assertIn("firm_script", queue[0])
        self.assertIn("settle", queue[0]["firm_script"])

    def test_risk_flags_include_high_value_due(self):
        flags = risk_flags(ROWS)

        self.assertTrue(any("High-value due item" in flag for flag in flags))

    def test_chart_plan_prioritizes_due_followups(self):
        plan = build_chart_plan(ROWS)

        self.assertEqual(plan["chart"], "due_by_party")
        self.assertIn("unpaid", plan["question"].lower())

    def test_insight_figures_return_plotly_figures(self):
        figures = build_insight_figures(ROWS)

        self.assertEqual(len(figures), 3)
        self.assertTrue(all(hasattr(figure, "to_plotly_json") for figure in figures))

    def test_review_rows_include_low_confidence_entries(self):
        rows = ROWS + [
            {
                "direction": "expense",
                "payment_status": "",
                "amount": 0,
                "currency": "LKR",
                "counterparty": "",
                "item": "unknown",
                "category": "uncategorized",
                "confidence": 0.42,
            }
        ]

        queue = review_rows(rows)

        self.assertEqual(queue[0]["source_row"], 3)
        self.assertIn("Low confidence", queue[0]["issue"])
        self.assertIn("confirm", queue[0]["question"])

    def test_daily_brief_fallback_mentions_cash_and_followup(self):
        brief = daily_brief_fallback(ROWS)

        self.assertIn("Net cash", brief)
        self.assertIn("Nimal", brief)

    def test_daily_brief_markdown_wraps_model_name(self):
        markdown = build_daily_brief_markdown(ROWS, "Cash is tight today.", "model.gguf")

        self.assertIn("Today's Shop Pulse", markdown)
        self.assertIn("model.gguf", markdown)

    def test_answer_ledger_question_answers_dues(self):
        answer = answer_ledger_question(ROWS, "Who owes me most?")

        self.assertIn("Nimal", answer)
        self.assertIn("LKR 7,500", answer)

    def test_answer_ledger_question_answers_cash_spend(self):
        answer = answer_ledger_question(ROWS, "Where did cash go?")

        self.assertIn("inventory", answer)

    def test_timeline_rows_turn_entries_into_story_events(self):
        events = timeline_rows(ROWS)

        self.assertEqual(events[0]["source_row"], 1)
        self.assertIn("Ravi", events[0]["story"])
        self.assertEqual(events[1]["badge"], "Due")

    def test_timeline_markdown_and_figure_render(self):
        markdown = build_timeline_markdown(ROWS)
        figure = timeline_figure(ROWS)

        self.assertIn("Shop Pulse Timeline", markdown)
        self.assertTrue(hasattr(figure, "to_plotly_json"))

    def test_counterparty_memory_cards_surface_due_profile(self):
        cards = counterparty_memory_cards(ROWS)

        self.assertEqual(cards[0]["party"], "Nimal")
        self.assertEqual(cards[0]["trust_pulse"], "Collect first")
        self.assertIn("Follow up", cards[0]["next_message"])

    def test_counterparty_memory_markdown_renders_cards(self):
        markdown = build_counterparty_memory_markdown(ROWS)

        self.assertIn("Counterparty Memory", markdown)
        self.assertIn("Nimal", markdown)


if __name__ == "__main__":
    unittest.main()
