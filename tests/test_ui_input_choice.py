import unittest

from shop_ledger.ui import add_to_ledger, choose_input


class InputChoiceTests(unittest.TestCase):
    def test_auto_asks_when_text_and_audio_exist(self):
        choice = choose_input("paid Ravi 1200", "/tmp/audio.wav", "Auto")

        self.assertEqual(choice["status"], "conflict")
        self.assertIn("Both", choice["notice"])

    def test_text_choice_uses_text_when_audio_exists(self):
        choice = choose_input("paid Ravi 1200", "/tmp/audio.wav", "Text note")

        self.assertEqual(choice["status"], "ready")
        self.assertEqual(choice["source"], "text")

    def test_auto_uses_audio_when_audio_is_only_input(self):
        choice = choose_input("", "/tmp/audio.wav", "Auto")

        self.assertEqual(choice["status"], "ready")
        self.assertEqual(choice["source"], "audio")

    def test_successful_text_add_clears_written_note(self):
        def fake_process(note, currency):
            return {
                "entries": [
                    {
                        "date": "2026-06-11",
                        "direction": "expense",
                        "counterparty": "Ravi",
                        "item": "rice bags",
                        "quantity": "",
                        "amount": 1200,
                        "currency": currency,
                        "category": "inventory",
                        "payment_status": "paid",
                        "due_date": "",
                        "confidence": 0.9,
                        "reminder": "",
                    }
                ],
                "reminders": [],
                "questions": [],
                "model_used": "fake",
            }

        output = add_to_ledger("paid Ravi 1200", None, "Auto", "LKR", [], fake_process)

        self.assertEqual(len(output[6]), 1)
        self.assertEqual(output[7]["value"], "")
        self.assertEqual(output[9]["value"], "Auto")
        self.assertIn("Added 1 row", output[10])


if __name__ == "__main__":
    unittest.main()
