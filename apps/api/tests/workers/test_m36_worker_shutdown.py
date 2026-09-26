from __future__ import annotations

import threading

from app.workers.runner import Worker


def test_event_wakes_polling_immediately(monkeypatch) -> None:
    w = Worker(worker_id="test-wake")
    reached_wait = threading.Event()

    monkeypatch.setattr(w, "_claim_once", lambda: False)
    monkeypatch.setattr(w, "_maybe_recover", lambda: None)
    w.install_signal_handlers = lambda: None  # type: ignore[assignment]

    class _S:
        job_poll_interval_seconds = 30.0
    w._settings = _S()  # type: ignore[assignment]

    original_wait = w._stopping.wait

    def wrapped_wait(timeout: float | None = None) -> bool:
        reached_wait.set()
        return original_wait(timeout)

    monkeypatch.setattr(w._stopping, "wait", wrapped_wait)

    t = threading.Thread(target=w.run_forever, daemon=True)
    t.start()
    assert reached_wait.wait(timeout=5.0), (
        "worker never reached polling wait"
    )
    w._stopping.set()
    t.join(timeout=5.0)
    assert not t.is_alive()


def test_no_claim_after_stop(monkeypatch) -> None:
    w = Worker(worker_id="test-stop")
    w._stopping.set()
    called = {"n": 0}

    def fake_claim() -> bool:
        called["n"] += 1
        return True

    monkeypatch.setattr(w, "_claim_once", fake_claim)
    monkeypatch.setattr(w, "_maybe_recover", lambda: None)
    w.install_signal_handlers = lambda: None  # type: ignore[assignment]

    class _S:
        job_poll_interval_seconds = 0.01
    w._settings = _S()  # type: ignore[assignment]

    w.run_forever()
    assert called["n"] == 0


def test_claim_once_returns_false_when_stopping() -> None:
    w = Worker(worker_id="test-claim-stop")
    w._stopping.set()
    assert w._claim_once() is False
