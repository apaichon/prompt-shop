import asyncio
import time
import psutil
import pytest
from intent_service.worker import Engine
from fakes import TinyModel,BadLoad


async def ready(engine,timeout=3):
    end=time.monotonic()+timeout
    while not engine.ready and time.monotonic()<end: await asyncio.sleep(.01)
    assert engine.ready


@pytest.mark.asyncio
async def test_one_active_four_queued_expiry_and_nonblocking_audio():
    engine=Engine("synthetic-only",factory=TinyModel)
    await engine.start();await ready(engine)
    first=asyncio.create_task(engine.classify("stall"))
    while engine.active is None: await asyncio.sleep(.002)
    worker_pid=engine.process.pid
    start=time.monotonic();pending=[asyncio.create_task(engine.classify("queued")) for _ in range(4)]
    await asyncio.sleep(.01)
    assert len(engine.jobs)==4
    assert (await engine.classify("overflow"))["reason"]=="busy"
    ticks=[]
    async def heartbeat():
        while not first.done():
            ticks.append(time.monotonic());await asyncio.sleep(.005)
    heartbeat_task=asyncio.create_task(heartbeat())
    queued=await asyncio.gather(*pending)
    assert all(x["reason"]=="busy" for x in queued)
    assert time.monotonic()-start < .3
    assert engine.active is not None and engine.process.pid==worker_pid
    result=await first;assert result["reason"]=="timeout"
    assert time.monotonic()-start < 1.35
    await heartbeat_task
    assert len(ticks)>50 and max(b-a for a,b in zip(ticks,ticks[1:]))<.1
    while engine.ready: await asyncio.sleep(.002)
    assert not engine.ready
    await ready(engine)
    assert engine.process.pid!=worker_pid and not psutil.pid_exists(worker_pid)
    assert (await engine.classify("fresh"))["intent"]=="find_item"
    await engine.close();assert engine.process is None and not engine.jobs and engine.active is None


@pytest.mark.asyncio
async def test_queued_cancellation_does_not_release_running_capacity():
    engine=Engine("synthetic-only",factory=TinyModel);await engine.start();await ready(engine)
    active=asyncio.create_task(engine.classify("stall"))
    while engine.active is None: await asyncio.sleep(.002)
    old_pid=engine.process.pid
    queued=asyncio.create_task(engine.classify("queued"));await asyncio.sleep(.02);queued.cancel()
    with pytest.raises(asyncio.CancelledError): await queued
    assert not engine.jobs and engine.process.pid==old_pid and engine.active is not None
    active.cancel()
    with pytest.raises(asyncio.CancelledError): await active
    await asyncio.sleep(.03);assert not engine.ready
    await ready(engine)
    assert not psutil.pid_exists(old_pid)
    assert (await engine.classify("new-turn"))["intent"]=="find_item"
    await engine.close()


@pytest.mark.asyncio
async def test_crash_and_malformed_result_are_safe_and_cleanup():
    engine=Engine("synthetic-only",factory=TinyModel);await engine.start();await ready(engine)
    assert (await engine.classify("malformed"))["reason"]=="error"
    assert (await engine.classify("crash"))["abstained"]
    await ready(engine)
    assert (await engine.classify("fresh"))["intent"]=="find_item"
    await engine.close()


@pytest.mark.asyncio
async def test_load_failure_is_never_ready_and_shutdown_bounded():
    engine=Engine("synthetic-only",factory=BadLoad,startup_timeout=1)
    await engine.start();await asyncio.sleep(.3)
    assert not engine.ready and (await engine.classify("sample"))["reason"]=="error"
    start=time.monotonic();await engine.close();assert time.monotonic()-start<1
