import json
import os
import time
import pytest

from orc.locking import acquire, release, LockHeld


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tasks").mkdir()
    return tmp_path


def test_acquire_writes_lock_file(repo):
    lock = acquire(repo)
    lock_path = repo / "tasks" / ".orc.lock"
    assert lock_path.exists()
    data = json.loads(lock_path.read_text())
    assert data["pid"] == os.getpid()
    lock.release()


def test_release_removes_lock_file(repo):
    lock = acquire(repo)
    lock.release()
    assert not (repo / "tasks" / ".orc.lock").exists()


def test_release_fn_removes_lock(repo):
    lock = acquire(repo)
    release(lock)
    assert not (repo / "tasks" / ".orc.lock").exists()


def test_second_acquire_raises_lock_held(repo):
    lock = acquire(repo)
    try:
        with pytest.raises(LockHeld):
            acquire(repo)
    finally:
        lock.release()


def test_stale_lock_by_age_reclaimed(repo):
    lock_path = repo / "tasks" / ".orc.lock"
    lock_path.write_text(json.dumps({"pid": os.getpid(), "timestamp": time.time() - 99999}))

    lock = acquire(repo, stale_seconds=14400)
    data = json.loads(lock_path.read_text())
    assert data["pid"] == os.getpid()
    lock.release()


def test_stale_lock_dead_pid_reclaimed(repo):
    lock_path = repo / "tasks" / ".orc.lock"
    lock_path.write_text(json.dumps({"pid": 999999999, "timestamp": time.time()}))

    lock = acquire(repo, stale_seconds=14400)
    assert lock_path.exists()
    lock.release()


def test_corrupted_lock_reclaimed(repo):
    lock_path = repo / "tasks" / ".orc.lock"
    lock_path.write_text("not json at all")

    lock = acquire(repo)
    assert lock_path.exists()
    lock.release()


def test_tasks_dir_created_if_missing(tmp_path):
    lock = acquire(tmp_path)
    assert (tmp_path / "tasks" / ".orc.lock").exists()
    lock.release()
