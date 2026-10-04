"""Thin wrapper around the `adb` command line tool."""

from __future__ import annotations

import logging
import struct
import subprocess

import numpy as np

from farmbot import imaging

log = logging.getLogger(__name__)


class AdbError(RuntimeError):
    pass


RGBA_8888 = 1


def parse_raw_screencap(data: bytes) -> np.ndarray | None:
    """Decode `screencap` raw output (header + RGBA pixels); None if the format is unknown."""
    if len(data) < 12:
        return None
    w, h, fmt = struct.unpack_from("<III", data)
    header = len(data) - w * h * 4
    if fmt != RGBA_8888 or header not in (12, 16):  # 16 bytes when a color space is included
        return None
    pixels = np.frombuffer(data, np.uint8, offset=header).reshape(h, w, 4)
    return np.ascontiguousarray(pixels[:, :, :3])


class Device:
    def __init__(self, serial: str | None = None, adb_path: str = "adb"):
        self.serial = serial
        self.adb_path = adb_path
        self._size: tuple[int, int] | None = None

    def _cmd(self, *args: str) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    def _run(self, *args: str, timeout: float = 20) -> bytes:
        cmd = self._cmd(*args)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except FileNotFoundError as e:
            raise AdbError(f"adb nicht gefunden ({self.adb_path}). Ist es installiert und im PATH?") from e
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"Zeitüberschreitung bei: {' '.join(cmd)}") from e
        if result.returncode != 0:
            raise AdbError(f"{' '.join(cmd)} fehlgeschlagen: {result.stderr.decode(errors='replace').strip()}")
        return result.stdout

    def list_devices(self) -> list[str]:
        out = Device(adb_path=self.adb_path)._run("devices").decode()
        return [
            line.split()[0]
            for line in out.splitlines()[1:]
            if line.strip() and line.split()[-1] == "device"
        ]

    def ensure_connected(self) -> None:
        devices = self.list_devices()
        if not devices:
            raise AdbError("Kein Gerät gefunden. USB-Debugging aktiviert und Verbindung erlaubt?")
        if self.serial is None and len(devices) > 1:
            raise AdbError(f"Mehrere Geräte gefunden ({', '.join(devices)}). Bitte device.serial setzen.")
        if self.serial is not None and self.serial not in devices:
            raise AdbError(f"Gerät {self.serial} nicht verbunden. Gefunden: {', '.join(devices)}")

    def screenshot(self) -> np.ndarray:
        """Return the current screen as an RGB image."""
        # Raw pixels are much faster than PNG: no compression on the phone, no decoding here.
        img = parse_raw_screencap(self._run("exec-out", "screencap"))
        if img is None:
            data = self._run("exec-out", "screencap", "-p")
            try:
                img = imaging.decode(data)
            except OSError as e:
                raise AdbError("Screenshot konnte nicht dekodiert werden.") from e
        self._size = (img.shape[1], img.shape[0])
        return img

    @property
    def size(self) -> tuple[int, int]:
        """Screen size (width, height) in screenshot pixels."""
        if self._size is None:
            self.screenshot()
        assert self._size is not None
        return self._size

    def tap(self, x: int, y: int) -> None:
        log.debug("tap %d,%d", x, y)
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def tap_streams(self, streams: list[list[tuple[int, int]]]) -> None:
        """Run several tap sequences at the same time, all in a single adb call."""
        streams = [s for s in streams if s]
        if not streams:
            return
        jobs = ["(" + ";".join(f"input tap {int(x)} {int(y)}" for x, y in s) + ")" for s in streams]
        script = " & ".join(jobs) + " & wait" if len(jobs) > 1 else jobs[0]
        self._run("shell", script, timeout=30 + 0.5 * max(len(s) for s in streams))

    def hold(self, x: int, y: int, ms: int) -> None:
        """Press and hold at one spot (a swipe that doesn't move)."""
        self._run("shell", "input", "swipe", *(str(int(v)) for v in (x, y, x, y, ms)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run("shell", "input", "swipe", *(str(int(v)) for v in (x1, y1, x2, y2, duration_ms)))

    def start_app(self, package: str) -> None:
        self._run("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")

    def restart_app(self, package: str) -> None:
        self._run("shell", "am", "force-stop", package)
        self.start_app(package)
