import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KNOWN_KEYS = {
    "id", "title", "status", "complexity", "criticality", "tier",
    "retry_budget", "escalate_to", "depends_on", "parallel_safe",
    "night_batch", "review", "github_issue", "branch", "verify",
}


class MalformedTicket(Exception):
    pass


@dataclass
class Ticket:
    id: str
    title: str
    status: str
    path: Path
    body: str
    complexity: str | None = None
    criticality: str | None = None
    tier: int | None = None
    retry_budget: int | None = None
    escalate_to: str | None = None
    depends_on: list[str] = field(default_factory=list)
    parallel_safe: bool | None = None
    night_batch: bool | None = None
    review: bool | None = None
    github_issue: int | None = None
    branch: str | None = None
    verify: list[str] = field(default_factory=list)


def _parse_value(raw: str) -> Any:
    stripped = raw.strip()
    if stripped == "null" or stripped == "~":
        return None
    if stripped == "true":
        return True
    if stripped == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped[1:-1]
    return stripped


def _parse_inline_list(raw: str) -> list[str]:
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    if not inner.strip():
        return []
    items = [item.strip().strip('"').strip("'") for item in inner.split(",")]
    return [i for i in items if i]


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise MalformedTicket("File does not start with '---'")
    first_newline = text.index("\n")
    rest = text[first_newline + 1:]
    closing_pos = rest.find("\n---")
    if closing_pos == -1:
        raise MalformedTicket("No closing '---' fence found")
    fm_text = rest[:closing_pos]
    body_start = closing_pos + len("\n---")
    body = rest[body_start:]
    if body.startswith("\n"):
        body = body[1:]
    return fm_text, body


def _parse_frontmatter(fm_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = fm_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, value_raw = line.partition(":")
        key = key.strip()
        value_raw = value_raw.strip()

        if key not in KNOWN_KEYS:
            logger.warning("Unknown front-matter key %r — ignored", key)
            i += 1
            continue

        if value_raw == "" or value_raw is None:
            block_items: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].startswith("\t")):
                item = lines[i].strip()
                if item.startswith("- "):
                    item = item[2:].strip().strip('"').strip("'")
                block_items.append(item)
                i += 1
            result[key] = block_items
            continue

        if value_raw.startswith("["):
            result[key] = _parse_inline_list(value_raw)
        else:
            result[key] = _parse_value(value_raw)
        i += 1

    return result


def parse(path: Path) -> Ticket:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise MalformedTicket(f"{path}: empty file")

    try:
        fm_text, body = _split_frontmatter(text)
    except (ValueError, MalformedTicket) as exc:
        raise MalformedTicket(f"{path}: {exc}") from exc

    try:
        data = _parse_frontmatter(fm_text)
    except Exception as exc:
        raise MalformedTicket(f"{path}: failed to parse front-matter: {exc}") from exc

    if "id" not in data:
        raise MalformedTicket(f"{path}: missing required field 'id'")
    if "title" not in data:
        raise MalformedTicket(f"{path}: missing required field 'title'")
    if "status" not in data:
        raise MalformedTicket(f"{path}: missing required field 'status'")

    return Ticket(
        id=str(data["id"]),
        title=str(data["title"]),
        status=str(data["status"]),
        path=path,
        body=body,
        complexity=data.get("complexity"),
        criticality=data.get("criticality"),
        tier=data.get("tier"),
        retry_budget=data.get("retry_budget"),
        escalate_to=data.get("escalate_to"),
        depends_on=data.get("depends_on") or [],
        parallel_safe=data.get("parallel_safe"),
        night_batch=data.get("night_batch"),
        review=data.get("review"),
        github_issue=data.get("github_issue"),
        branch=data.get("branch"),
        verify=data.get("verify") or [],
    )


def _emit_value(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if any(c in s for c in ('"', "'", ":", "#", "[", "]", "{", "}")):
        return f'"{s}"'
    return s


def _emit_list(items: list[str]) -> str:
    if not items:
        return "[]"
    lines = [""]
    for item in items:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def _build_frontmatter(ticket: Ticket) -> str:
    parts: list[str] = ["---"]

    def add(key: str, v: Any) -> None:
        if isinstance(v, list):
            parts.append(f"{key}:{_emit_list(v)}")
        else:
            parts.append(f"{key}: {_emit_value(v)}")

    add("id", ticket.id)
    add("title", ticket.title)
    add("status", ticket.status)
    if ticket.complexity is not None:
        add("complexity", ticket.complexity)
    if ticket.criticality is not None:
        add("criticality", ticket.criticality)
    if ticket.tier is not None:
        add("tier", ticket.tier)
    if ticket.retry_budget is not None:
        add("retry_budget", ticket.retry_budget)
    add("escalate_to", ticket.escalate_to)
    add("depends_on", ticket.depends_on)
    if ticket.parallel_safe is not None:
        add("parallel_safe", ticket.parallel_safe)
    if ticket.night_batch is not None:
        add("night_batch", ticket.night_batch)
    if ticket.review is not None:
        add("review", ticket.review)
    if ticket.github_issue is not None:
        add("github_issue", ticket.github_issue)
    if ticket.branch is not None:
        add("branch", ticket.branch)
    add("verify", ticket.verify)
    parts.append("---")
    return "\n".join(parts)


def write_frontmatter(ticket: Ticket) -> None:
    fm = _build_frontmatter(ticket)
    new_content = fm + "\n" + ticket.body
    dir_ = ticket.path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp_path, ticket.path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
