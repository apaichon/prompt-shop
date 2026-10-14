"""Count pending bytes at the actual ADK enqueue/dequeue boundary."""
import asyncio

from google.adk.live.live_request_queue import LiveRequest, LiveRequestQueue


class QueueOverflow(RuntimeError):
    pass


class _AccountingQueue(asyncio.Queue):
    def __init__(self):
        super().__init__(maxsize=64)
        self.pending_pcm = 0

    @staticmethod
    def size(item):
        return len(item.blob.data or b"") if item.blob else 0

    def put_nowait(self, item):
        size = self.size(item)
        if self.full() or self.pending_pcm + size > 32_000:
            raise QueueOverflow("input backlog exceeded")
        super().put_nowait(item)
        self.pending_pcm += size

    def get_nowait(self):
        item = super().get_nowait()
        self.pending_pcm -= self.size(item)
        return item


class BoundedLiveRequestQueue(LiveRequestQueue):
    def __init__(self):
        super().__init__()
        self._queue = _AccountingQueue()

    @property
    def pending_pcm(self):
        return self._queue.pending_pcm

    def close(self):
        if self.closed:
            return
        while not self._queue.empty():
            self._queue.get_nowait()
        super().close()

    def send(self, req: LiveRequest):
        if self.closed:
            raise RuntimeError("queue closed")
        super().send(req)

    def send_realtime(self, blob):
        self.send(LiveRequest(blob=blob))

    def send_content(self, content, partial=False):
        self.send(LiveRequest(content=content, partial=partial))
