"""v0.2.1: maximizing the compare window must not freeze it.

The debounce logic always runs. The window itself runs when a display exists
(Xvfb in this environment). GitHub CI has no display, so that part is skipped.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

from oculto_scan.gui_logic import RESIZE_DEBOUNCE_MS, ResizeCoalescer, run_scan_job
from tests.workbook_factory import build_workbook


class _Clock:
    def __init__(self) -> None:
        self.now = 0
        self._seq = 0
        self.queue: list[tuple[int, int, object]] = []

    def schedule(self, delay: int, callback):
        self._seq += 1
        token = self._seq
        self.queue.append((self.now + delay, token, callback))
        return token

    def cancel(self, token: int) -> None:
        self.queue = [item for item in self.queue if item[1] != token]

    def fire_due(self) -> None:
        due = [item for item in self.queue if item[0] <= self.now]
        self.queue = [item for item in self.queue if item[0] > self.now]
        for _when, _token, callback in due:
            callback()


def test_resize_burst_applies_once_and_stops_configure_feedback():
    clock = _Clock()
    applied: list[int] = []

    def apply(width: int) -> None:
        applied.append(width)
        coalescer.push(width + 1)

    coalescer = ResizeCoalescer(clock.schedule, clock.cancel, apply)
    assert coalescer.delay_ms == RESIZE_DEBOUNCE_MS == 100
    for width in range(400, 440):
        coalescer.push(width)
    assert len(clock.queue) == 1
    clock.now += RESIZE_DEBOUNCE_MS
    for _step in range(6):
        clock.fire_due()
        clock.now += RESIZE_DEBOUNCE_MS
    assert applied[0] == 439
    assert coalescer.fires <= 3
    assert clock.queue == []


def test_run_scan_job_compares_two_workbooks_off_the_ui(tmp_path):
    left = tmp_path / "enviada.xlsx"
    right = tmp_path / "recebida.xlsx"
    build_workbook(left, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "antes"}]}])
    build_workbook(right, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "depois"}]}])
    session = run_scan_job("diff", str(left), str(right))
    assert session.mode == "diff"
    assert session.diff is not None
    assert session.diff.changes
    missing = run_scan_job("scan", str(tmp_path / "nao.xlsx"), "")
    assert "não encontrado" in missing.error.casefold()


def test_compare_stays_responsive_when_the_window_is_maximized(tmp_path, monkeypatch):
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        pytest.skip("sem display")
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")
    probe.destroy()

    import oculto_scan.gui_logic as logic
    from oculto_scan.gui_window import App

    def cells(tag: str) -> list[dict]:
        rows = [{"ref": "A1", "value": "Item"}]
        rows.extend({"ref": f"B{row}", "value": f"{tag} {row}"} for row in range(2, 18))
        return rows

    left = tmp_path / "enviada.xlsx"
    right = tmp_path / "recebida.xlsx"
    build_workbook(left, [{"name": "Proposta", "cells": cells("antes")}])
    build_workbook(right, [{"name": "Proposta", "cells": cells("depois")}])

    started = threading.Event()
    holder: dict[str, int] = {}
    real = logic.compare_files

    def slow(original, received):
        holder["thread"] = threading.get_ident()
        started.set()
        time.sleep(0.35)
        return real(original, received)

    monkeypatch.setattr(logic, "compare_files", slow)
    root = tk.Tk()
    try:
        app = App(root)
        app._mode.set("diff")
        app._apply_mode()
        app._left.set(str(left))
        app._right.set(str(right))
        app._run()
        assert started.wait(2)
        began = time.perf_counter()
        for _pump in range(8):
            root.update()
        assert time.perf_counter() - began < 0.25
        assert app._busy is True
        assert "disabled" in app._go.state()
        assert "disabled" in app._save_btn.state()
        assert app._meter[1] == "Analisando..."
        assert app._status.get() == "Analisando..."
        assert holder["thread"] != threading.get_ident()

        deadline = time.perf_counter() + 3
        while app._busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert app._busy is False
        assert app.session.mode == "diff"
        assert app.session.diff is not None
        cards = tuple(id(child) for child in app._card_frame.winfo_children())
        assert cards
        fires = app._resize.fires
        root.geometry("1440x1080")
        try:
            root.state("zoomed")
        except tk.TclError:
            pass
        for step in range(30):
            root.event_generate("<Configure>", width=1100 + (step % 5), height=900)
            app._cards_canvas.event_generate("<Configure>", width=680 + (step % 9), height=520)
        storm = time.perf_counter()
        limit = storm + 1.5
        while time.perf_counter() < limit:
            root.update()
            time.sleep(0.01)
        assert time.perf_counter() - storm < 2
        assert fires < app._resize.fires <= fires + 6
        assert tuple(id(child) for child in app._card_frame.winfo_children()) == cards
        assert "disabled" not in app._go.state()
    finally:
        root.destroy()
