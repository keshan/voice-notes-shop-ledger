import unittest
from tempfile import NamedTemporaryFile

from shop_ledger.processor import extract_document_text, prepare_document_input
from shop_ledger.ui import add_to_ledger, choose_input


class InputChoiceTests(unittest.TestCase):
    def test_auto_asks_when_text_and_audio_exist(self):
        choice = choose_input("paid Ravi 1200", "/tmp/audio.wav", None, "Auto")

        self.assertEqual(choice["status"], "conflict")
        self.assertIn("Multiple inputs", choice["notice"])

    def test_text_choice_uses_text_when_audio_exists(self):
        choice = choose_input("paid Ravi 1200", "/tmp/audio.wav", None, "Text note")

        self.assertEqual(choice["status"], "ready")
        self.assertEqual(choice["source"], "text")

    def test_auto_uses_audio_when_audio_is_only_input(self):
        choice = choose_input("", "/tmp/audio.wav", None, "Auto")

        self.assertEqual(choice["status"], "ready")
        self.assertEqual(choice["source"], "audio")

    def test_auto_uses_document_when_document_is_only_input(self):
        choice = choose_input("", None, "/tmp/receipt.pdf", "Auto")

        self.assertEqual(choice["status"], "ready")
        self.assertEqual(choice["source"], "document")

    def test_document_text_extraction_reads_plain_text_files(self):
        with NamedTemporaryFile("w", suffix=".txt") as handle:
            handle.write("paid Ravi 1200 for rice bags")
            handle.flush()

            text = extract_document_text(handle.name)

        self.assertIn("Ravi", text)

    def test_document_image_preparation_creates_data_url(self):
        from PIL import Image

        with NamedTemporaryFile(suffix=".png") as handle:
            Image.new("RGB", (8, 8), color="white").save(handle.name)

            document = prepare_document_input(handle.name)

        self.assertEqual(document["kind"], "image")
        self.assertTrue(document["image_urls"][0].startswith("data:image/jpeg;base64,"))

    def test_successful_text_add_clears_written_note(self):
        def fake_process(note, currency, image_urls=None):
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

        output = add_to_ledger("paid Ravi 1200", None, None, "Auto", "LKR", [], fake_process)

        self.assertEqual(len(output[6]), 1)
        self.assertEqual(output[7]["value"], "")
        self.assertEqual(output[10]["value"], "Auto")
        self.assertIn("Added 1 row", output[11])

    def test_successful_document_add_sends_image_urls_and_clears_file(self):
        captured = {}

        def fake_process(note, currency, image_urls=None):
            captured["note"] = note
            captured["image_urls"] = image_urls
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

        with NamedTemporaryFile("w", suffix=".txt") as handle:
            handle.write("paid Ravi 1200 for rice bags")
            handle.flush()

            output = add_to_ledger("", None, handle.name, "Document", "LKR", [], fake_process)

        self.assertIn("paid Ravi", captured["note"])
        self.assertIsNone(captured["image_urls"])
        self.assertEqual(output[9]["value"], None)
        self.assertIn("Added 1 row", output[11])


if __name__ == "__main__":
    unittest.main()
