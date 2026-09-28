"""JurisMon Diff Engine Models.

Sub-Task 3.3:
Defines strict structured schemas for statutory clauses, word-level deltas,
and complete diff payloads stored in Supabase and queried by the Search UI.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class WordDelta(BaseModel):
    """Represents inline token-level statutory edits (e.g. '25 feet' -> '30 feet')."""
    operation: str = Field(..., description="'insert', 'delete', or 'equal'")
    text: str


class Clause(BaseModel):
    """Represents an extracted statutory section or paragraph clause."""
    identifier: str = Field(..., description="Unique heading or index (e.g. '§ 12-401. Setbacks' or 'Paragraph 3')")
    section_number: Optional[str] = Field(None, description="Normalized section numbering (e.g. '12-401')")
    title: Optional[str] = Field(None, description="Extracted clause title")
    text: str = Field(..., description="Full clean text of the statutory clause")
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class ClauseDiff(BaseModel):
    """Represents an individual clause difference between two snapshots."""
    change_type: str = Field(..., description="'added', 'removed', or 'modified'")
    identifier: str
    section_number: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    similarity_score: Optional[float] = Field(None, description="Text similarity ratio from 0.0 to 1.0")
    word_deltas: Optional[List[WordDelta]] = Field(default_factory=list, description="Inline word-level changes")


class DiffPayload(BaseModel):
    """Full structured JSON output stored in the database and queried by users."""
    strategy_used: str = Field(..., description="'section' or 'paragraph'")
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0
    added: List[ClauseDiff] = Field(default_factory=list)
    removed: List[ClauseDiff] = Field(default_factory=list)
    modified: List[ClauseDiff] = Field(default_factory=list)
    summary: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
