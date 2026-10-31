"""Regression guard: research quotes must not silently become executable."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MarketDataProvenanceRegressionTests(unittest.TestCase):
    def test_scanner_uses_market_data_provider_not_synthetic_price_arrays(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        scanner = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_scanner")
        calls = [
            node for node in ast.walk(scanner)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "get_live_market_data"
        ]
        self.assertTrue(calls, "Scanner must obtain quotes from the market data provider")
        for assignment in ast.walk(scanner):
            if isinstance(assignment, ast.Assign):
                for target in assignment.targets:
                    if isinstance(target, ast.Name) and target.id in {"prices", "volumes"}:
                        self.assertFalse(
                            isinstance(assignment.value, (ast.List, ast.Tuple)),
                            "Scanner must not use synthetic prices/volumes",
                        )

    def test_yahoo_data_is_explicitly_research_only(self):
        source = (ROOT / "engines/market_data_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        provider = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_live_market_data")
        source_segment = ast.get_source_segment(source, provider)
        self.assertIn('"RESEARCH_ONLY"', source_segment)
        self.assertIn('"execution_eligible": False', source_segment)

    def test_missing_quote_skips_signal_pipeline(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        scanner = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_scanner")
        self.assertTrue(any(
            isinstance(node, ast.If)
            and any(isinstance(child, ast.Continue) for child in node.body)
            and "not prices or not volumes" in (ast.get_source_segment(source, node.test) or "")
            for node in ast.walk(scanner)
        ), "Missing quote must skip downstream scoring")


if __name__ == "__main__":
    unittest.main()
