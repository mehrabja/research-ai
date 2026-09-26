from __future__ import annotations

import threading

from app.workers import stats as worker_stats


def test_register_is_idempotent() -> None:
    a = worker_stats.register("w1")
    b = worker_stats.register("w1")
    assert a is b


def test_snapshot_shape() -> None:
    s = worker_stats.register("w1")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 0
    assert snap["failed_jobs"] == 0
    assert snap["reclaimed_jobs"] == 0


def test_success_path() -> None:
    s = worker_stats.register("w1")
    s.job_started("job-a", "t")
    assert s.snapshot()["active_jobs"] == 1
    s.job_finished("job-a", "completed")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 1


def test_failure_path() -> None:
    s = worker_stats.register("w1")
    s.job_started("job-a", "t")
    s.job_finished("job-a", "failed")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["failed_jobs"] == 1


def test_double_finish_same_job_is_idempotent() -> None:
    s = worker_stats.register("w1")
    s.job_started("job-a", "t")
    s.job_finished("job-a", "completed")
    s.job_finished("job-a", "completed")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 1


def test_double_finish_does_not_corrupt_sibling_job() -> None:
    s = worker_stats.register("w-regression")
    s.job_started("A", "t")
    s.job_started("B", "t")
    assert s.snapshot()["active_jobs"] == 2

    s.job_finished("A", "completed")
    s.job_finished("A", "completed")

    assert s.snapshot()["active_jobs"] == 1

    s.job_finished("B", "completed")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 2
    assert snap["failed_jobs"] == 0


def test_finish_unknown_does_not_touch_counters() -> None:
    s = worker_stats.register("w-unknown")
    s.job_finished("never-seen", "completed")
    s.job_finished("never-seen", "failed")
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 0
    assert snap["failed_jobs"] == 0


def test_active_never_negative_under_churn() -> None:
    s = worker_stats.register("w1")
    for _ in range(5):
        s.job_finished("never-started", "completed")
    assert s.snapshot()["active_jobs"] == 0


def test_concurrent_mutation_consistency() -> None:
    s = worker_stats.register("w1")
    N = 100
    barrier = threading.Barrier(N)

    def work(i: int) -> None:
        barrier.wait()
        job_id = f"job-{i}"
        s.job_started(job_id, "t")
        s.job_finished(job_id, "completed")

    threads = [
        threading.Thread(target=work, args=(i,)) for i in range(N)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == N


def test_concurrent_mixed_operations() -> None:
    s = worker_stats.register("w1")
    barrier = threading.Barrier(30)

    def start_finish(seed: int) -> None:
        barrier.wait()
        for i in range(20):
            job_id = f"g{seed}-{i}"
            s.job_started(job_id, "t")
            s.job_finished(job_id, "completed")

    def reclaim() -> None:
        barrier.wait()
        for _ in range(10):
            s.jobs_reclaimed(1)

    def snap() -> None:
        barrier.wait()
        for _ in range(20):
            s.snapshot()

    threads = (
        [threading.Thread(target=start_finish, args=(g,))
         for g in range(10)]
        + [threading.Thread(target=reclaim) for _ in range(10)]
        + [threading.Thread(target=snap) for _ in range(10)]
    )
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = s.snapshot()
    assert snap["active_jobs"] == 0
    assert snap["completed_jobs"] == 200
    assert snap["reclaimed_jobs"] == 100
