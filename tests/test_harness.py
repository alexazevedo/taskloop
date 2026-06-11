import sys
import pytest
from pathlib import Path

from orc.harness import assemble_context, dispatch, TIMEOUT
from orc.ticket import parse
from orc.config import Config, HarnessConfig, GitHubConfig

FAKE_HARNESS = Path(__file__).parent / "fakes" / "fake_harness.py"
PYTHON = sys.executable


def _config(mode: str = "pass", timeout: int = 5) -> Config:
    return Config(
        repo=".",
        wip_cap=5,
        night_wallclock_minutes=360,
        max_parallel=3,
        default_branch="main",
        memory_file="CLAUDE.md",
        timeouts={"TEST": timeout},
        harness={"TEST": HarnessConfig(
            command=f"FAKE_MODE={mode} {PYTHON} {FAKE_HARNESS} {{context}} {{workdir}}"
        )},
        github=GitHubConfig(),
    )


@pytest.fixture
def ticket(tmp_path):
    p = tmp_path / "T-001.md"
    p.write_text(
        "---\nid: T-001\ntitle: Test\nstatus: ready\ndepends_on: []\n---\n\nTicket body here.\n"
    )
    return parse(p)


def test_dispatch_pass(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path)
    code, output = dispatch("TEST", ctx, tmp_path, _config("pass"))
    assert code == 0
    ctx.unlink(missing_ok=True)


def test_dispatch_fail(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path)
    code, output = dispatch("TEST", ctx, tmp_path, _config("fail"))
    assert code != 0 and code != TIMEOUT
    ctx.unlink(missing_ok=True)


def test_dispatch_timeout(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path)
    code, output = dispatch("TEST", ctx, tmp_path, _config("hang", timeout=1))
    assert code == TIMEOUT
    ctx.unlink(missing_ok=True)


def test_dispatch_substitutes_placeholders(tmp_path):
    ctx = tmp_path / "ctx.md"
    ctx.write_text("context")
    config = Config(
        repo=".",
        wip_cap=5,
        night_wallclock_minutes=360,
        max_parallel=3,
        default_branch="main",
        memory_file="CLAUDE.md",
        timeouts={"TEST": 10},
        harness={"TEST": HarnessConfig(command="echo {context} {workdir}")},
        github=GitHubConfig(),
    )
    code, output = dispatch("TEST", ctx, tmp_path, config)
    assert code == 0
    assert str(ctx) in output
    assert str(tmp_path) in output


def test_assemble_context_includes_body(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path)
    assert "Ticket body here." in ctx.read_text()
    ctx.unlink()


def test_assemble_context_includes_memory(tmp_path, ticket):
    (tmp_path / "CLAUDE.md").write_text("# Memory content")
    ctx = assemble_context(ticket, tmp_path)
    assert "# Memory content" in ctx.read_text()
    ctx.unlink()


def test_assemble_context_includes_prior_errors(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path, prior_errors="Error: test failed")
    assert "Error: test failed" in ctx.read_text()
    ctx.unlink()


def test_assemble_context_missing_memory_ok(tmp_path, ticket):
    ctx = assemble_context(ticket, tmp_path)
    content = ctx.read_text()
    assert "Ticket body here." in content
    ctx.unlink()
