import os
import textwrap
from pathlib import Path

import pytest

from orc.ticket import MalformedTicket, Ticket, parse, write_frontmatter


SAMPLE_TICKET = textwrap.dedent("""\
    ---
    id: T-001
    title: "Sample ticket"
    status: ready
    complexity: medium
    criticality: high
    tier: 1
    retry_budget: 3
    escalate_to: null
    depends_on: [T-000]
    parallel_safe: true
    night_batch: false
    review: false
    github_issue: 42
    branch: task/T-001-sample
    verify:
      - pytest tests/ -q
      - ruff check orc/
    ---

    # Body text here

    Some content with a --- line in the middle that should not confuse the parser.

    ---

    More body.
""")


MINIMAL_TICKET = textwrap.dedent("""\
    ---
    id: T-002
    title: "Minimal"
    status: ready
    ---

    Body only.
""")


INLINE_LIST_TICKET = textwrap.dedent("""\
    ---
    id: T-003
    title: "Inline list"
    status: blocked
    depends_on: [T-001, T-002]
    verify: [pytest tests/ -q]
    ---

    Body.
""")


MALFORMED_TICKET = textwrap.dedent("""\
    ---
    id: T-bad
    title: Missing closing fence
    status: ready
""")


def write_tmp(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestParse:
    def test_all_field_types(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)

        assert t.id == "T-001"
        assert t.title == "Sample ticket"
        assert t.status == "ready"
        assert t.complexity == "medium"
        assert t.criticality == "high"
        assert t.tier == 1
        assert t.retry_budget == 3
        assert t.escalate_to is None
        assert t.depends_on == ["T-000"]
        assert t.parallel_safe is True
        assert t.night_batch is False
        assert t.review is False
        assert t.github_issue == 42
        assert t.branch == "task/T-001-sample"
        assert t.verify == ["pytest tests/ -q", "ruff check orc/"]
        assert t.path == p

    def test_body_preserved_verbatim(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        assert "# Body text here" in t.body
        assert "---" in t.body
        assert "More body." in t.body

    def test_minimal_ticket(self, tmp_path):
        p = write_tmp(tmp_path, "t002.md", MINIMAL_TICKET)
        t = parse(p)
        assert t.id == "T-002"
        assert t.status == "ready"
        assert t.depends_on == []
        assert t.verify == []

    def test_inline_list(self, tmp_path):
        p = write_tmp(tmp_path, "t003.md", INLINE_LIST_TICKET)
        t = parse(p)
        assert t.depends_on == ["T-001", "T-002"]
        assert t.verify == ["pytest tests/ -q"]

    def test_malformed_raises(self, tmp_path):
        p = write_tmp(tmp_path, "bad.md", MALFORMED_TICKET)
        with pytest.raises(MalformedTicket):
            parse(p)

    def test_unknown_key_ignored(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: T-010
            title: "With unknown"
            status: ready
            unknown_key: some value
            ---

            Body.
        """)
        p = write_tmp(tmp_path, "t010.md", content)
        t = parse(p)
        assert t.id == "T-010"

    def test_body_dashes_not_confused(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        body_lines = t.body.splitlines()
        assert any("---" in line for line in body_lines)

    def test_empty_file_raises(self, tmp_path):
        p = write_tmp(tmp_path, "empty.md", "")
        with pytest.raises(MalformedTicket):
            parse(p)

    def test_missing_id_raises(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            title: "No ID"
            status: ready
            ---

            Body.
        """)
        p = write_tmp(tmp_path, "noid.md", content)
        with pytest.raises(MalformedTicket):
            parse(p)


class TestWriteFrontmatter:
    def test_status_change_body_identical(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        original_body = t.body

        t.status = "in_progress"
        write_frontmatter(t)

        t2 = parse(p)
        assert t2.status == "in_progress"
        assert t2.body == original_body

    def test_body_bytes_identical(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        body_bytes_before = t.body.encode("utf-8")

        t.status = "done"
        write_frontmatter(t)

        t2 = parse(p)
        body_bytes_after = t2.body.encode("utf-8")
        assert body_bytes_before == body_bytes_after

    def test_atomic_write(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        t.status = "in_progress"
        write_frontmatter(t)
        assert p.exists()
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_round_trip_preserves_all_fields(self, tmp_path):
        p = write_tmp(tmp_path, "t001.md", SAMPLE_TICKET)
        t = parse(p)
        t.status = "in_progress"
        write_frontmatter(t)

        t2 = parse(p)
        assert t2.id == t.id
        assert t2.title == t.title
        assert t2.tier == t.tier
        assert t2.retry_budget == t.retry_budget
        assert t2.depends_on == t.depends_on
        assert t2.verify == t2.verify
        assert t2.parallel_safe == t.parallel_safe
        assert t2.night_batch == t.night_batch
        assert t2.escalate_to == t.escalate_to
