import textwrap
from pathlib import Path

import pytest

from orc.state import IllegalTransition, transition
from orc.ticket import parse, write_frontmatter


def make_ticket(tmp_path: Path, status: str):
    content = textwrap.dedent(f"""\
        ---
        id: T-st
        title: "State test"
        status: {status}
        ---

        Body.
    """)
    p = tmp_path / "ticket.md"
    p.write_text(content, encoding="utf-8")
    return parse(p)


class TestLegalTransitions:
    def test_ready_to_in_progress(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        transition(t, "in_progress")
        assert t.status == "in_progress"

    def test_ready_to_blocked(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        transition(t, "blocked")
        assert t.status == "blocked"

    def test_in_progress_to_done(self, tmp_path):
        t = make_ticket(tmp_path, "in_progress")
        transition(t, "done")
        assert t.status == "done"

    def test_in_progress_to_escalated(self, tmp_path):
        t = make_ticket(tmp_path, "in_progress")
        transition(t, "escalated")
        assert t.status == "escalated"

    def test_in_progress_to_ready(self, tmp_path):
        t = make_ticket(tmp_path, "in_progress")
        transition(t, "ready")
        assert t.status == "ready"

    def test_blocked_to_ready(self, tmp_path):
        t = make_ticket(tmp_path, "blocked")
        transition(t, "ready")
        assert t.status == "ready"

    def test_escalated_to_done(self, tmp_path):
        t = make_ticket(tmp_path, "escalated")
        transition(t, "done")
        assert t.status == "done"

    def test_escalated_to_ready(self, tmp_path):
        t = make_ticket(tmp_path, "escalated")
        transition(t, "ready")
        assert t.status == "ready"

    def test_any_to_failed(self, tmp_path):
        for status in ("ready", "in_progress", "blocked", "escalated"):
            t = make_ticket(tmp_path, status)
            transition(t, "failed")
            assert t.status == "failed"


class TestIllegalTransitions:
    def test_done_to_anything_raises(self, tmp_path):
        for target in ("ready", "in_progress", "blocked", "escalated"):
            t = make_ticket(tmp_path, "done")
            with pytest.raises(IllegalTransition):
                transition(t, target)

    def test_failed_to_anything_raises(self, tmp_path):
        for target in ("ready", "in_progress", "blocked", "escalated", "done"):
            t = make_ticket(tmp_path, "failed")
            with pytest.raises(IllegalTransition):
                transition(t, target)

    def test_ready_to_done_raises(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        with pytest.raises(IllegalTransition):
            transition(t, "done")

    def test_ready_to_escalated_raises(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        with pytest.raises(IllegalTransition):
            transition(t, "escalated")

    def test_blocked_to_in_progress_raises(self, tmp_path):
        t = make_ticket(tmp_path, "blocked")
        with pytest.raises(IllegalTransition):
            transition(t, "in_progress")

    def test_blocked_to_done_raises(self, tmp_path):
        t = make_ticket(tmp_path, "blocked")
        with pytest.raises(IllegalTransition):
            transition(t, "done")

    def test_escalated_to_in_progress_raises(self, tmp_path):
        t = make_ticket(tmp_path, "escalated")
        with pytest.raises(IllegalTransition):
            transition(t, "in_progress")

    def test_escalated_to_blocked_raises(self, tmp_path):
        t = make_ticket(tmp_path, "escalated")
        with pytest.raises(IllegalTransition):
            transition(t, "blocked")


class TestTransitionWritesFile:
    def test_transition_persists_to_file(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        transition(t, "in_progress")
        t2 = parse(t.path)
        assert t2.status == "in_progress"

    def test_transition_body_unchanged(self, tmp_path):
        t = make_ticket(tmp_path, "ready")
        body_before = t.body
        transition(t, "in_progress")
        t2 = parse(t.path)
        assert t2.body == body_before
