"""Comprehensive Unit Tests for Day 3: Section Splitter & Statutory Diff Engine."""

import unittest
from diff_engine.engine import DiffEngine
from diff_engine.section_splitter import SectionSplitter


class TestDiffEngine(unittest.TestCase):

    def test_section_splitter_with_section_symbols(self):
        text = """
§ 101-1. Purpose.
This ordinance establishes zoning restrictions in residential districts.

§ 101-2. Permitted Uses.
Single family dwellings and accessory structures are permitted.
"""
        clauses, strategy = SectionSplitter.split(text)
        self.assertEqual(strategy, "section")
        self.assertEqual(len(clauses), 2)
        self.assertIn("§ 101-1", clauses[0].identifier)
        self.assertIn("§ 101-2", clauses[1].identifier)

    def test_section_splitter_with_sec_and_article(self):
        text = """
Article I. General Provisions.
All development shall conform to the comprehensive plan.

Sec. 12-4. Off-Street Parking.
Commercial spaces shall provide one parking space per 250 square feet.

Chapter 5. Environmental Protection.
Stormwater retention basins are required for major subdivisions.
"""
        clauses, strategy = SectionSplitter.split(text)
        self.assertEqual(strategy, "section")
        self.assertEqual(len(clauses), 3)
        self.assertIn("Article I", clauses[0].identifier)
        self.assertIn("Sec. 12-4", clauses[1].identifier)
        self.assertIn("Chapter 5", clauses[2].identifier)

    def test_section_splitter_fallback_to_paragraphs(self):
        text = """
The board met on Tuesday at 7 PM to discuss municipal zoning.

A motion was made to review commercial setback requirements.

The meeting adjourned at 8:30 PM.
"""
        clauses, strategy = SectionSplitter.split(text)
        self.assertEqual(strategy, "paragraph")
        self.assertEqual(len(clauses), 3)
        self.assertEqual(clauses[0].identifier, "Paragraph 1")
        self.assertEqual(clauses[1].identifier, "Paragraph 2")

    def test_diff_engine_detects_added_removed_and_modified_clauses(self):
        old_text = """
§ 12-1. Setbacks.
Front yard setback shall be a minimum of 25 feet.

§ 12-2. Height Limits.
Maximum structure height is 35 feet.

§ 12-3. Obsolete Clause.
This section is hereby repealed.
"""

        new_text = """
§ 12-1. Setbacks.
Front yard setback shall be a minimum of 30 feet.

§ 12-2. Height Limits.
Maximum structure height is 35 feet.

§ 12-4. Solar Panels.
Rooftop solar installations are permitted by right.
"""

        engine = DiffEngine()
        diff = engine.compare(old_text, new_text)

        self.assertEqual(diff.strategy_used, "section")
        self.assertEqual(diff.total_added, 1)
        self.assertEqual(diff.total_removed, 1)
        self.assertEqual(diff.total_modified, 1)

        self.assertTrue(any("§ 12-4" in item.identifier for item in diff.added))
        self.assertTrue(any("§ 12-3" in item.identifier for item in diff.removed))
        self.assertTrue(any("§ 12-1" in item.identifier for item in diff.modified))
        self.assertIn("1 clause(s) added", diff.summary)

    def test_diff_engine_computes_word_level_deltas(self):
        old_text = """
§ 50-1. Fencing.
Residential fences shall not exceed 6 feet in height.

§ 50-2. Buffer.
A landscape buffer of 10 feet is required.
"""

        new_text = """
§ 50-1. Fencing.
Residential fences shall not exceed 8 feet in height.

§ 50-2. Buffer.
A landscape buffer of 10 feet is required.
"""

        engine = DiffEngine()
        diff = engine.compare(old_text, new_text)

        self.assertEqual(diff.total_modified, 1)
        mod_clause = diff.modified[0]
        self.assertIn("§ 50-1", mod_clause.identifier)
        self.assertGreater(mod_clause.similarity_score, 0.8)

        # Check word-level deltas
        operations = [d.operation for d in mod_clause.word_deltas]
        deleted_texts = [d.text for d in mod_clause.word_deltas if d.operation == "delete"]
        inserted_texts = [d.text for d in mod_clause.word_deltas if d.operation == "insert"]

        self.assertIn("delete", operations)
        self.assertIn("insert", operations)
        self.assertTrue(any("6" in t for t in deleted_texts))
        self.assertTrue(any("8" in t for t in inserted_texts))

    def test_diff_engine_identical_snapshots(self):
        text = """
§ 1-1. Title.
This code shall be known as the Municipal Land Use Code.

§ 1-2. Authority.
Enacted under statutory police powers.
"""
        engine = DiffEngine()
        diff = engine.compare(text, text)
        self.assertEqual(diff.total_added, 0)
        self.assertEqual(diff.total_removed, 0)
        self.assertEqual(diff.total_modified, 0)
        self.assertEqual(diff.summary, "No statutory changes detected")


if __name__ == "__main__":
    unittest.main()
