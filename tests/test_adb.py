import struct

import numpy as np

from farmbot.adb import Device, parse_raw_screencap


def test_parse_raw_screencap_with_and_without_colorspace():
    rgba = np.arange(3 * 2 * 4, dtype=np.uint8).reshape(2, 3, 4)
    for header in (struct.pack("<III", 3, 2, 1), struct.pack("<IIII", 3, 2, 1, 1)):
        img = parse_raw_screencap(header + rgba.tobytes())
        assert img.shape == (2, 3, 3)
        assert np.array_equal(img, rgba[:, :, :3])


def test_parse_raw_screencap_rejects_unknown_format():
    assert parse_raw_screencap(struct.pack("<III", 1, 1, 5) + bytes(4)) is None
    assert parse_raw_screencap(b"\\x89PNG") is None


def test_tap_streams_runs_streams_in_parallel_in_one_call(monkeypatch):
    calls = []
    dev = Device("x")
    monkeypatch.setattr(dev, "_run", lambda *args, **kw: calls.append(args))
    dev.tap_streams([[(1, 2), (1, 2)], [(3, 4)], []])
    assert calls == [("shell", "(input tap 1 2;input tap 1 2) & (input tap 3 4) & wait")]


def test_hold_is_a_swipe_that_does_not_move(monkeypatch):
    calls = []
    dev = Device("x")
    monkeypatch.setattr(dev, "_run", lambda *args, **kw: calls.append(args))
    dev.hold(100, 200, 750)
    assert calls == [("shell", "input", "swipe", "100", "200", "100", "200", "750")]
