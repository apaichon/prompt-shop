"""One isolated native inference process. Pipe messages never contain credentials."""
import asyncio
from collections import deque
from dataclasses import dataclass
import logging
import multiprocessing
import os
import time
import sys
import resource
import uuid

from .model import EnglishModel
from .protocol import abstain, validate, valid_text


@dataclass
class Job:
    text: str | None
    future: asyncio.Future
    enqueued: float
    deadline: float
    started: bool = False
    timer: object = None


def worker_main(connection, model_root, factory):
    # Native/runtime warnings may include supplied content. No worker stdout/stderr.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    logging.disable(logging.CRITICAL)
    try:
        started = time.monotonic()
        model = factory(model_root)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        connection.send(("ready", {"startup_ms": (time.monotonic()-started)*1000, "peak_rss_bytes": peak,
                                   "runtime": getattr(model, "runtime", {"implementation": "synthetic_test_worker"})}))
        while True:
            call_id, text = connection.recv()
            try:
                result = validate(model.predict(text))
            except Exception:
                result = abstain("error")
            finally:
                text = None
            connection.send((call_id, result))
            result = None
    except (EOFError, BrokenPipeError, OSError):
        pass
    except Exception:
        try:
            connection.send(("failed", None))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class Engine:
    """Event-loop admission and a maximum four waiting jobs, no executor backlog."""
    def __init__(self, model_root, *, factory=EnglishModel, startup_timeout=120, restart_delay=.25):
        self.model_root, self.factory = str(model_root), factory
        self.startup_timeout, self.restart_delay = startup_timeout, restart_delay
        self.jobs, self.wake = deque(), asyncio.Event()
        self.task = self.process = self.pipe = self.active = None
        self.ready = self.closed = False
        self.startup_ms = None
        self.load_facts = None
        self.restarts = 0
        self.last_fault = None
        self.context = multiprocessing.get_context("spawn")

    async def start(self):
        if self.task is not None:
            raise ValueError("engine already started")
        self.task = asyncio.create_task(self._manage())

    def _purge(self):
        self.jobs = deque(job for job in self.jobs if not job.future.done())

    async def classify(self, text, *, deadline=None):
        valid_text(text)
        if self.closed or not self.ready:
            return abstain("error")
        self._purge()
        if len(self.jobs) >= 4:
            return abstain("busy")
        loop = asyncio.get_running_loop()
        now = loop.time()
        job = Job(text, loop.create_future(), now, min(deadline or now+1.2, now+1.2))
        def expired():
            if not job.started and not job.future.done():
                job.text = None
                job.future.set_result(abstain("busy"))
                self._purge()
        job.timer = loop.call_later(min(.2, max(0,job.deadline-now)), expired)
        self.jobs.append(job)
        self.wake.set()
        try:
            async with asyncio.timeout_at(job.deadline):
                return await asyncio.shield(job.future)
        except TimeoutError:
            if not job.future.done():
                job.future.cancel()
            self.wake.set()
            return abstain("timeout")
        except asyncio.CancelledError:
            job.future.cancel()
            self.wake.set()
            raise
        finally:
            job.text = None
            job.timer.cancel()
            self._purge()

    async def _receive(self, deadline, cancelled=None):
        loop = asyncio.get_running_loop()
        while loop.time() < deadline:
            if cancelled is not None and cancelled():
                raise asyncio.CancelledError
            if self.pipe.poll():
                return self.pipe.recv()
            if not self.process.is_alive():
                raise ValueError("worker exited")
            await asyncio.sleep(.002)
        raise TimeoutError

    async def _stop_process(self):
        self.ready = False
        process, self.process = self.process, None
        if process is not None:
            if process.is_alive(): process.terminate()
            await asyncio.to_thread(process.join, .2)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, .5)
            if process.is_alive():
                self.process = process  # Capacity stays occupied; no replacement is permitted.
                raise RuntimeError("worker could not be reaped")
            process.close()
        if self.pipe is not None:
            self.pipe.close()
            self.pipe = None

    def _fail_queue(self):
        for job in self.jobs:
            job.text = None
            job.timer.cancel()
            if not job.future.done(): job.future.set_result(abstain("error"))
        self.jobs.clear()

    async def _boot(self):
        self.pipe, child = self.context.Pipe()
        self.process = self.context.Process(target=worker_main, args=(child,self.model_root,self.factory), daemon=True)
        self.process.start()
        child.close()
        message, facts = await self._receive(asyncio.get_running_loop().time()+self.startup_timeout)
        if message != "ready":
            raise ValueError("worker load or warmup failed")
        self.startup_ms = facts["startup_ms"]
        self.load_facts = facts
        self.ready = True

    async def _manage(self):
        try:
            while not self.closed:
                if not self.ready:
                    try:
                        await self._boot()
                    except (ValueError, OSError, EOFError, TimeoutError):
                        self.last_fault = "load_error"
                        await self._stop_process()
                        self._fail_queue()
                        await asyncio.sleep(max(5,self.restart_delay))
                        continue
                self._purge()
                if not self.jobs:
                    self.wake.clear()
                    try:
                        await asyncio.wait_for(self.wake.wait(), .05)
                    except TimeoutError:
                        if not self.process.is_alive():
                            await self._stop_process()
                            self.last_fault = "worker_exit"
                            self.restarts += 1
                    continue
                job = self.jobs.popleft()
                if job.future.done(): continue
                self.active = job
                job.started = True
                job.timer.cancel()
                if asyncio.get_running_loop().time()-job.enqueued > .2:
                    job.future.set_result(abstain("busy"))
                    job.text = None
                    self.active = None
                    continue
                call_id = uuid.uuid4().hex
                try:
                    self.pipe.send((call_id,job.text))
                    job.text = None
                    response_id, result = await self._receive(job.deadline, job.future.cancelled)
                    if response_id != call_id:
                        raise ValueError("stale worker result")
                    validate(result)
                    if not job.future.done(): job.future.set_result(result)
                except (TimeoutError, asyncio.CancelledError, ValueError, EOFError, OSError):
                    if not job.future.done(): job.future.set_result(abstain("timeout"))
                    await self._stop_process()
                    self._fail_queue()
                    self.last_fault = "inference_timeout_or_cancel"
                    self.restarts += 1
                    await asyncio.sleep(self.restart_delay)
                finally:
                    job.text = None
                    self.active = None
        finally:
            self.ready = False
            self._fail_queue()
            if self.active is not None and not self.active.future.done(): self.active.future.set_result(abstain("error"))
            await self._stop_process()

    async def close(self):
        self.closed = True
        self.ready = False
        self.wake.set()
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
