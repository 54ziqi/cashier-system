"""所有写操作串行化"""
from __future__ import annotations
import concurrent.futures
import queue
import threading
from typing import Callable, TypeVar

T = TypeVar("T")

_q: "queue.Queue[tuple[Callable, concurrent.futures.Future]]" = queue.Queue()
_lock = threading.Lock()
_started = False


def _worker():
    while True:
        fn, fut = _q.get()
        try:
            with _lock:
                result = fn()
            if not fut.cancelled():
                fut.set_result(result)
        except Exception as e:
            if not fut.cancelled():
                fut.set_exception(e)


def start_writer():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_worker, daemon=True, name="db-writer").start()


def submit_write(fn: Callable[[], T]) -> concurrent.futures.Future:
    fut: concurrent.futures.Future = concurrent.futures.Future()
    _q.put((fn, fut))
    return fut
