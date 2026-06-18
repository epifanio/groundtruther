"""Frame-accurate video reader with interlaced-source support.

OpenCV's FFmpeg backend (with FFmpeg 7/8's stricter swscale) fails to convert
*interlaced* frames to BGR — it logs "Cannot convert interlaced to progressive
frames or vice versa" and returns black frames.  PyAV with a ``yadif``
deinterlace filter handles those sources correctly, so when PyAV is available we
use it; otherwise we fall back to OpenCV.

Both backends expose the same minimal interface the player needs:

    reader = open_video(path)         # -> a *Reader or None if it can't open
    reader.frame_count, reader.fps, reader.width, reader.height
    bgr = reader.read(index)          # BGR ndarray (H, W, 3) or None
    reader.release()

``read`` is frame-accurate: sequential reads are cheap, random seeks jump to the
nearest preceding keyframe and decode forward to the requested frame.
"""
from __future__ import annotations

import numpy as np

try:
    import cv2
    _CV2 = True
except ImportError:  # pragma: no cover - cv2 is a hard plugin dep in practice
    _CV2 = False

try:
    import av
    _AV = True
except ImportError:
    _AV = False


# --------------------------------------------------------------------------- #
# PyAV backend (handles interlaced sources via yadif)                          #
# --------------------------------------------------------------------------- #
class AvVideoReader:
    """PyAV-backed reader; deinterlaces flagged frames with ``yadif``."""

    # Decode forward (no re-seek) when the requested frame is within this many
    # frames ahead of the cursor — covers playback and short skips.
    _SEQ_WINDOW = 60

    def __init__(self, path: str):
        self._container = av.open(path)
        self._stream = self._container.streams.video[0]
        self._stream.thread_type = "AUTO"
        cc = self._stream.codec_context
        self.width = int(cc.width)
        self.height = int(cc.height)
        rate = self._stream.average_rate or self._stream.guessed_rate
        self.fps = float(rate) if rate else 25.0
        self._time_base = self._stream.time_base
        self._start = self._stream.start_time or 0
        self.frame_count = self._frame_count()
        self._graph = None
        self._decode = None
        self._cursor = -1          # index of the last frame yielded by `read`
        self._last = None          # cached last BGR frame
        self._reset_pipeline()

    # -- setup helpers -------------------------------------------------------
    def _frame_count(self) -> int:
        if self._stream.frames:
            return int(self._stream.frames)
        dur = self._stream.duration or (self._container.duration and
                                        self._container.duration / 1_000_000 / float(self._time_base))
        if dur:
            return int(round(float(dur) * float(self._time_base) * self.fps))
        return 0

    def _build_graph(self):
        graph = av.filter.Graph()
        src = graph.add_buffer(template=self._stream)
        # deint=1 -> only frames flagged interlaced are deinterlaced; progressive
        # frames pass through unchanged, so this is safe for any source.
        yadif = graph.add("yadif", "mode=0:deint=1")
        sink = graph.add("buffersink")
        src.link_to(yadif)
        yadif.link_to(sink)
        graph.configure()
        self._graph = graph

    def _reset_pipeline(self):
        """(Re)create the decode generator and filter graph from the current pos."""
        self._build_graph()
        self._decode = self._container.decode(self._stream)

    def _index_of(self, frame) -> int:
        # Use the frame's own presentation time (seconds): the filter graph's
        # buffersink may report a different time_base than the input stream, so
        # deriving the index from the stream time_base would be wrong.
        t = frame.time
        if t is None:
            return self._cursor + 1
        return int(round(t * self.fps))

    # -- public API ----------------------------------------------------------
    @property
    def is_opened(self) -> bool:
        return self._container is not None

    def read(self, index: int):
        if self._container is None:
            return None
        if self.frame_count:
            index = max(0, min(int(index), self.frame_count - 1))
        else:
            index = max(0, int(index))

        if index == self._cursor and self._last is not None:
            return self._last

        # Decide between forward decode and a seek (also re-seek if the decode
        # pipeline was drained by a previous end-of-stream read).
        if self._decode is None or not (self._cursor < index <= self._cursor + self._SEQ_WINDOW):
            self._seek(index)

        return self._advance_to(index)

    def _seek(self, index: int):
        target = self._start + int(round(index / self.fps / float(self._time_base)))
        try:
            self._container.seek(target, stream=self._stream, backward=True, any_frame=False)
        except av.AVError:
            self._container.seek(0, stream=self._stream, backward=True)
        self._reset_pipeline()
        self._cursor = -1

    def _advance_to(self, index: int):
        for frame in self._decode:
            self._graph.push(frame)
            hit = self._pull_until(index)
            if hit is not None:
                return hit
        # Decode exhausted: flush the filter graph (yadif holds one frame of
        # latency, so the final frame only emerges after an EOF push).
        try:
            self._graph.push(None)
        except Exception:
            pass
        hit = self._pull_until(index)
        if hit is not None:
            return hit
        self._decode = None  # pipeline drained; next read() will re-seek
        return self._last

    def _pull_until(self, index: int):
        while True:
            try:
                out = self._graph.pull()
            except (av.BlockingIOError, av.EOFError):
                return None
            self._cursor = self._index_of(out)
            self._last = out.to_ndarray(format="bgr24")
            if self._cursor >= index:
                return self._last

    def release(self):
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass
            self._container = None
        self._graph = None
        self._decode = None


# --------------------------------------------------------------------------- #
# OpenCV backend (fallback)                                                    #
# --------------------------------------------------------------------------- #
class CvVideoReader:
    """OpenCV-backed reader. Does not deinterlace (no swscale control)."""

    def __init__(self, path: str, backend=None):
        self._cap = cv2.VideoCapture(path, backend if backend is not None else cv2.CAP_ANY)
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 0 else 25.0
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._pos = -1

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self, index: int):
        if self._cap is None:
            return None
        if self.frame_count:
            index = max(0, min(int(index), self.frame_count - 1))
        if index != self._pos + 1:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ret, bgr = self._cap.read()
        if not ret:
            return None
        self._pos = index
        return bgr

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def open_video(path: str, prefer_av: bool = True):
    """Open *path* and return a reader, or ``None`` if it cannot be opened.

    Prefers the PyAV backend (handles interlaced sources); falls back to OpenCV.
    """
    if prefer_av and _AV:
        try:
            reader = AvVideoReader(path)
            if reader.is_opened and reader.frame_count >= 0:
                return reader
        except Exception:
            pass  # fall through to OpenCV
    if _CV2:
        reader = CvVideoReader(path)
        return reader if reader.is_opened else None
    return None
