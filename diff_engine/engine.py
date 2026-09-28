"""JurisMon Diff Engine.

Sub-Task 3.2:
Computes precise statutory diffs between two snapshots (Yesterday vs Today).
Generates added, removed, and modified clauses, complete with similarity
scores and inline word-level deltas.
"""

import difflib
import re
from typing import List, Dict, Tuple, Optional
from diff_engine.models import DiffPayload, ClauseDiff, Clause, WordDelta
from diff_engine.section_splitter import SectionSplitter


class DiffEngine:
    """Computes statutory diffs between municipal document snapshots."""

    def __init__(self, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold

    def compare(self, old_text: str, new_text: str) -> DiffPayload:
        """
        Calculates diffs between yesterday's snapshot (old_text) and today's (new_text).
        """
        old_clauses, old_strategy = SectionSplitter.split(old_text or "")
        new_clauses, new_strategy = SectionSplitter.split(new_text or "")

        strategy_used = "section" if (old_strategy == "section" or new_strategy == "section") else "paragraph"

        old_map: Dict[str, Clause] = {self._normalize_key(c.identifier): c for c in old_clauses}
        new_map: Dict[str, Clause] = {self._normalize_key(c.identifier): c for c in new_clauses}

        added: List[ClauseDiff] = []
        removed: List[ClauseDiff] = []
        modified: List[ClauseDiff] = []

        all_keys = list(dict.fromkeys(list(old_map.keys()) + list(new_map.keys())))

        for key in all_keys:
            in_old = key in old_map
            in_new = key in new_map

            if in_old and not in_new:
                old_c = old_map[key]
                removed.append(
                    ClauseDiff(
                        change_type="removed",
                        identifier=old_c.identifier,
                        section_number=old_c.section_number,
                        old_text=old_c.text,
                        new_text=None,
                        similarity_score=0.0,
                    )
                )
            elif in_new and not in_old:
                new_c = new_map[key]
                added.append(
                    ClauseDiff(
                        change_type="added",
                        identifier=new_c.identifier,
                        section_number=new_c.section_number,
                        old_text=None,
                        new_text=new_c.text,
                        similarity_score=0.0,
                    )
                )
            else:
                # Exists in both: check if text changed
                old_c = old_map[key]
                new_c = new_map[key]
                old_content = old_c.text.strip()
                new_content = new_c.text.strip()

                if old_content != new_content:
                    sim = difflib.SequenceMatcher(None, old_content, new_content).ratio()
                    word_deltas = self._compute_word_deltas(old_content, new_content)

                    modified.append(
                        ClauseDiff(
                            change_type="modified",
                            identifier=new_c.identifier,
                            section_number=new_c.section_number,
                            old_text=old_content,
                            new_text=new_content,
                            similarity_score=round(sim, 3),
                            word_deltas=word_deltas,
                        )
                    )

        # Build clean summary
        summary_parts = []
        if added:
            summary_parts.append(f"{len(added)} clause(s) added")
        if removed:
            summary_parts.append(f"{len(removed)} clause(s) removed")
        if modified:
            summary_parts.append(f"{len(modified)} clause(s) modified")

        summary = ", ".join(summary_parts) if summary_parts else "No statutory changes detected"

        return DiffPayload(
            strategy_used=strategy_used,
            total_added=len(added),
            total_removed=len(removed),
            total_modified=len(modified),
            added=added,
            removed=removed,
            modified=modified,
            summary=summary,
        )

    @staticmethod
    def _normalize_key(identifier: str) -> str:
        """Normalizes section identifier for stable key matching."""
        clean = identifier.strip().lower()
        # Remove extra whitespace and punctuation
        clean = re.sub(r"[\s\:\.\-_–—]+", " ", clean)
        return clean.strip()

    @staticmethod
    def _compute_word_deltas(old_text: str, new_text: str) -> List[WordDelta]:
        """Computes fine-grained word-level statutory diffs."""
        old_words = re.findall(r"\S+|\n", old_text)
        new_words = re.findall(r"\S+|\n", new_text)

        matcher = difflib.SequenceMatcher(None, old_words, new_words)
        deltas: List[WordDelta] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                deltas.append(WordDelta(operation="equal", text=" ".join(old_words[i1:i2])))
            elif tag == "delete":
                deltas.append(WordDelta(operation="delete", text=" ".join(old_words[i1:i2])))
            elif tag == "insert":
                deltas.append(WordDelta(operation="insert", text=" ".join(new_words[j1:j2])))
            elif tag == "replace":
                deltas.append(WordDelta(operation="delete", text=" ".join(old_words[i1:i2])))
                deltas.append(WordDelta(operation="insert", text=" ".join(new_words[j1:j2])))

        return [d for d in deltas if d.text.strip()]
