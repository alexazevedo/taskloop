from pathlib import Path

from orc.ticket import Ticket
from orc.eligibility import eligible, detect_cycles, group_waves


def make_ticket(
    id: str,
    status: str = "ready",
    depends_on: list[str] | None = None,
    parallel_safe: bool | None = None,
    night_batch: bool | None = None,
    body: str = "",
) -> Ticket:
    return Ticket(
        id=id,
        title=f"Ticket {id}",
        status=status,
        path=Path(f"/fake/{id}.md"),
        body=body,
        depends_on=depends_on or [],
        parallel_safe=parallel_safe,
        night_batch=night_batch,
    )


class TestEligible:
    def test_basic_eligible(self):
        tickets = [
            make_ticket("T-001", status="done"),
            make_ticket("T-002", depends_on=["T-001"]),
        ]
        assert [t.id for t in eligible(tickets, night=False, wip_cap=5)] == ["T-002"]

    def test_unmet_dependency_excluded(self):
        tickets = [
            make_ticket("T-001"),
            make_ticket("T-002", depends_on=["T-001"]),
        ]
        result = eligible(tickets, night=False, wip_cap=5)
        assert [t.id for t in result] == ["T-001"]

    def test_wip_cap_returns_empty(self):
        tickets = [
            make_ticket("T-001", status="in_progress"),
            make_ticket("T-002", status="in_progress"),
            make_ticket("T-003"),
        ]
        assert eligible(tickets, night=False, wip_cap=2) == []

    def test_wip_cap_not_hit(self):
        tickets = [
            make_ticket("T-001", status="in_progress"),
            make_ticket("T-002"),
        ]
        result = eligible(tickets, night=False, wip_cap=2)
        assert [t.id for t in result] == ["T-002"]

    def test_escalated_counts_toward_wip(self):
        tickets = [
            make_ticket("T-001", status="escalated"),
            make_ticket("T-002", status="escalated"),
            make_ticket("T-003"),
        ]
        assert eligible(tickets, night=False, wip_cap=2) == []

    def test_night_filter_excludes_non_night(self):
        tickets = [
            make_ticket("T-001", night_batch=True),
            make_ticket("T-002", night_batch=False),
            make_ticket("T-003"),
        ]
        result = eligible(tickets, night=True, wip_cap=5)
        assert [t.id for t in result] == ["T-001"]

    def test_day_run_ignores_night_batch(self):
        tickets = [
            make_ticket("T-001", night_batch=True),
            make_ticket("T-002", night_batch=False),
        ]
        result = eligible(tickets, night=False, wip_cap=5)
        assert len(result) == 2

    def test_sorted_by_id(self):
        tickets = [
            make_ticket("T-003"),
            make_ticket("T-001"),
            make_ticket("T-002"),
        ]
        result = eligible(tickets, night=False, wip_cap=5)
        assert [t.id for t in result] == ["T-001", "T-002", "T-003"]

    def test_only_ready_tickets_eligible(self):
        tickets = [
            make_ticket("T-001", status="blocked"),
            make_ticket("T-002", status="done"),
            make_ticket("T-003", status="in_progress"),
            make_ticket("T-004"),
        ]
        result = eligible(tickets, night=False, wip_cap=5)
        assert [t.id for t in result] == ["T-004"]


class TestDetectCycles:
    def test_no_cycles(self):
        tickets = [
            make_ticket("T-001"),
            make_ticket("T-002", depends_on=["T-001"]),
        ]
        assert detect_cycles(tickets) == set()

    def test_simple_cycle(self):
        tickets = [
            make_ticket("T-001", depends_on=["T-002"]),
            make_ticket("T-002", depends_on=["T-001"]),
        ]
        assert detect_cycles(tickets) == {"T-001", "T-002"}

    def test_self_cycle(self):
        tickets = [make_ticket("T-001", depends_on=["T-001"])]
        assert "T-001" in detect_cycles(tickets)

    def test_missing_dependency(self):
        tickets = [make_ticket("T-002", depends_on=["T-999"])]
        assert "T-002" in detect_cycles(tickets)

    def test_cycle_does_not_infect_clean_tickets(self):
        tickets = [
            make_ticket("T-001"),
            make_ticket("T-002", depends_on=["T-003"]),
            make_ticket("T-003", depends_on=["T-002"]),
        ]
        result = detect_cycles(tickets)
        assert "T-001" not in result
        assert {"T-002", "T-003"} <= result

    def test_empty_tickets(self):
        assert detect_cycles([]) == set()


class TestGroupWaves:
    def test_non_parallel_safe_each_own_wave(self):
        tickets = [
            make_ticket("T-001", parallel_safe=False),
            make_ticket("T-002", parallel_safe=False),
        ]
        waves = group_waves(tickets)
        assert len(waves) == 2
        assert all(w.mode == "sequential" for w in waves)
        assert [w.tickets[0].id for w in waves] == ["T-001", "T-002"]

    def test_none_parallel_safe_is_sequential(self):
        tickets = [make_ticket("T-001", parallel_safe=None)]
        waves = group_waves(tickets)
        assert waves[0].mode == "sequential"

    def test_parallel_safe_packed_together(self):
        tickets = [
            make_ticket("T-001", parallel_safe=True, body="- CREATE: foo.py"),
            make_ticket("T-002", parallel_safe=True, body="- CREATE: bar.py"),
        ]
        waves = group_waves(tickets)
        assert len(waves) == 1
        assert waves[0].mode == "parallel"
        assert len(waves[0].tickets) == 2

    def test_file_overlap_splits_wave(self):
        tickets = [
            make_ticket("T-001", parallel_safe=True, body="- CREATE: shared.py"),
            make_ticket("T-002", parallel_safe=True, body="- CREATE: shared.py"),
        ]
        waves = group_waves(tickets)
        assert len(waves) == 2

    def test_no_file_overlap_stays_in_one_wave(self):
        tickets = [
            make_ticket("T-001", parallel_safe=True, body="- CREATE: a.py, b.py"),
            make_ticket("T-002", parallel_safe=True, body="- CREATE: c.py"),
        ]
        waves = group_waves(tickets)
        assert len(waves) == 1

    def test_ordering_stable_by_id(self):
        tickets = [
            make_ticket("T-003", parallel_safe=False),
            make_ticket("T-001", parallel_safe=False),
            make_ticket("T-002", parallel_safe=False),
        ]
        waves = group_waves(tickets)
        assert [w.tickets[0].id for w in waves] == ["T-001", "T-002", "T-003"]

    def test_wave_indices_sequential(self):
        tickets = [
            make_ticket("T-001", parallel_safe=False),
            make_ticket("T-002", parallel_safe=False),
        ]
        waves = group_waves(tickets)
        assert [w.index for w in waves] == [0, 1]

    def test_empty_eligible(self):
        assert group_waves([]) == []

    def test_modify_lines_parsed(self):
        tickets = [
            make_ticket("T-001", parallel_safe=True, body="- MODIFY: src/foo.py"),
            make_ticket("T-002", parallel_safe=True, body="- MODIFY: src/foo.py"),
        ]
        waves = group_waves(tickets)
        assert len(waves) == 2
