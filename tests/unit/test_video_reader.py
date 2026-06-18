"""Frame-accuracy tests for gt.video_reader.

Synthesises tiny H.264 clips (progressive and interlaced) whose marker
rectangle x-position encodes the frame index, then checks that
``reader.read(i)`` returns frame ``i``. Skipped when PyAV / OpenCV / libx264
are unavailable (they are runtime deps, not unit-test deps).
"""
import numpy as np
import pytest

av = pytest.importorskip("av")
cv2 = pytest.importorskip("cv2")

from groundtruther.gt.video_reader import open_video, AvVideoReader


def _make_clip(path, interlaced, n=40, w=320, h=240):
    container = av.open(str(path), mode="w")
    stream = container.add_stream("libx264", rate=25)
    stream.width, stream.height, stream.pix_fmt = w, h, "yuv420p"
    if interlaced:
        stream.codec_context.flags |= (
            av.codec.context.Flags.interlaced_dct
            | av.codec.context.Flags.interlaced_me)
    for i in range(n):
        frame = np.zeros((h, w, 3), np.uint8)
        x = 20 + i * 4
        cv2.rectangle(frame, (x, 40), (x + 30, 200), (0, 160, 255), -1)
        for pkt in stream.encode(av.VideoFrame.from_ndarray(frame, format="bgr24")):
            container.mux(pkt)
    for pkt in stream.encode():
        container.mux(pkt)
    container.close()


def _marker_index(bgr):
    mask = (bgr[:, :, 0] < 80) & (bgr[:, :, 1] > 100) & (bgr[:, :, 2] > 180)
    cols = np.where(mask.any(axis=0))[0]
    return None if not len(cols) else round((cols.min() - 20) / 4)


@pytest.fixture
def clips(tmp_path):
    try:
        prog = tmp_path / "prog.mp4"
        ilace = tmp_path / "ilace.mp4"
        _make_clip(prog, interlaced=False)
        _make_clip(ilace, interlaced=True)
    except av.AVError as exc:  # libx264 missing
        pytest.skip(f"cannot encode test clip: {exc}")
    return {"progressive": prog, "interlaced": ilace}


@pytest.mark.parametrize("kind", ["progressive", "interlaced"])
def test_frame_accurate_read(clips, kind):
    reader = open_video(str(clips[kind]))
    assert reader is not None and reader.is_opened
    assert isinstance(reader, AvVideoReader)   # PyAV is installed
    assert reader.frame_count == 40
    # sequential, random, repeat, backward, last frame
    for idx in [0, 5, 10, 3, 20, 21, 22, 9, 39, 39, 0, 38]:
        bgr = reader.read(idx)
        assert bgr is not None and bgr.ndim == 3 and bgr.shape[2] == 3
        assert _marker_index(bgr) == idx, f"read({idx}) returned wrong frame"
        assert bgr.mean() > 2, f"read({idx}) is black (deinterlace failed)"
    reader.release()


def test_open_missing_file_returns_reader_or_none(tmp_path):
    # A nonexistent path should not raise; returns None or an unopened reader.
    reader = open_video(str(tmp_path / "nope.mp4"))
    assert reader is None or not reader.is_opened
