import unittest

from shop_ledger.processor import LedgerProcessor


class ProcessorTests(unittest.TestCase):
    def test_mock_processor_returns_rows(self):
        processor = LedgerProcessor(mode="mock")
        result = processor.process("paid Ravi 1200 for rice bags")

        self.assertEqual(result.model_used, "mock heuristic")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].amount, 1200)

    def test_llama_mode_falls_back_without_model(self):
        processor = LedgerProcessor(mode="llama", model_path="/missing/model.gguf")
        result = processor.process("customer Nimal owes 750")

        self.assertIn("fallback", result.model_used)
        self.assertEqual(result.entries[0].amount, 750)


if __name__ == "__main__":
    unittest.main()
