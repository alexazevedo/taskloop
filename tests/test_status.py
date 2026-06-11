import pytest
from pathlib import Path
from unittest.mock import patch

from orc.cli import cmd_status, build_parser

FIXTURE_REPO = Path(__file__).parent / "fixtures" / "repo"


def _capture_status(repo_path: Path) -> list[str]:
    parser = build_parser()
    args = parser.parse_args(["--repo", str(repo_path), "status"])
    lines: list[str] = []
    with patch("orc.cli.human", side_effect=lines.append):
        cmd_status(args)
    return lines


def test_status_renders_tickets_in_id_order():
    lines = _capture_status(FIXTURE_REPO)
    output = "\n".join(lines)
    pos_001 = output.find("T-001")
    pos_002 = output.find("T-002")
    pos_003 = output.find("T-003")
    assert pos_001 < pos_002 < pos_003


def test_status_shows_headers():
    lines = _capture_status(FIXTURE_REPO)
    header = lines[0]
    for col in ("ID", "TITLE", "STATUS", "TIER", "ATTEMPTS", "WAVE"):
        assert col in header


def test_status_empty_repo(tmp_path):
    (tmp_path / "tasks").mkdir()
    lines = _capture_status(tmp_path)
    output = "\n".join(lines)
    assert "WIP: 0" in output or "No tickets" in output


def test_status_wip_count():
    lines = _capture_status(FIXTURE_REPO)
    output = "\n".join(lines)
    assert "WIP:" in output


def test_status_wip_counts_in_progress():
    lines = _capture_status(FIXTURE_REPO)
    output = "\n".join(lines)
    assert "WIP: 1" in output
