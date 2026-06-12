import unittest
from unittest.mock import patch

from shop_ledger.llama_backend import LlamaLedgerBackend
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

    def test_llama_backend_uses_readable_model_label(self):
        label = "unsloth/gemma-4-12b-it-GGUF / gemma-4-12b-it-UD-Q4_K_XL.gguf / llama.cpp"
        with patch.dict("os.environ", {"LLAMA_MODEL_LABEL": label}):
            backend = LlamaLedgerBackend(model_path="/models/model.gguf")

        self.assertEqual(backend.model_label, label)


if __name__ == "__main__":
    unittest.main()
