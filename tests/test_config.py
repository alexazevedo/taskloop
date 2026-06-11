import pytest
from pathlib import Path

from orc.config import load, BadConfig

EXAMPLE_TOML = Path(__file__).parent.parent / "orchestrator.toml.example"


def test_load_example_config():
    config = load(EXAMPLE_TOML)
    assert config.wip_cap == 5
    assert config.max_parallel == 3
    assert config.default_branch == "main"
    assert "LOCAL-S" in config.timeouts
    assert config.timeouts["LOCAL-S"] == 1200
    assert "API-MID" in config.harness
    assert "{context}" in config.harness["API-MID"].command
    assert config.github.enabled is True


def test_reject_missing_timeouts(tmp_path):
    cfg = tmp_path / "orchestrator.toml"
    cfg.write_text(
        'repo = "."\n'
        "wip_cap = 5\n"
        "night_wallclock_minutes = 360\n"
        "max_parallel = 3\n"
        'default_branch = "main"\n'
        'memory_file = "CLAUDE.md"\n'
    )
    with pytest.raises(BadConfig, match="timeouts"):
        load(cfg)


def test_reject_missing_required_field(tmp_path):
    cfg = tmp_path / "orchestrator.toml"
    cfg.write_text(
        'repo = "."\n'
        "night_wallclock_minutes = 360\n"
        "max_parallel = 3\n"
        'default_branch = "main"\n'
        'memory_file = "CLAUDE.md"\n'
        "[timeouts]\n"
        "API-MID = 1800\n"
    )
    with pytest.raises(BadConfig, match="wip_cap"):
        load(cfg)


def test_missing_file(tmp_path):
    with pytest.raises(BadConfig, match="not found"):
        load(tmp_path / "nonexistent.toml")
