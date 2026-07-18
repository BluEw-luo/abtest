#!/usr/bin/env python3
"""
abtest.py  —  Audio AB Blind Comparison Tool

Load two songs (flac / mp3 / wav / ogg), randomly assign them as A and B
(blind), and let you switch between them instantly with the spacebar.

Controls during playback:
    P         Play / Pause
    Space     Switch between A and B (instant)
    R         Restart from beginning
    Q         Quit

At the end the app reveals which original file mapped to A and which to B.
"""

from __future__ import annotations

import math
import os
import random
import select
import signal
import sys
import termios
import threading
import time
import tty
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly

# ──────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────

def _resample_to(data: np.ndarray, src_sr: int, dst_sr: int, axis: int = 0) -> np.ndarray:
    """Polyphase resample *data* from *src_sr* to *dst_sr*."""
    if src_sr == dst_sr:
        return data
    # reduce fraction for numerical stability
    g = math.gcd(src_sr, dst_sr)
    up = dst_sr // g
    down = src_sr // g
    return resample_poly(data, up=up, down=down, axis=axis)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


def _fmt_time(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def _fmt_pct(p: float) -> str:
    return f"{p * 100:5.1f}%"


# ──────────────────────────────────────────────────────────────────────
# core
# ──────────────────────────────────────────────────────────────────────

class ABTest:
    """Blind A/B audio comparator.

    The entire UI lives on the terminal via ANSI escapes.  Three threads
    cooperate:

    * **audio callback** (sounddevice realtime thread) — reads samples
      from the active buffer at the current play-head position.
    * **display** (daemon thread) — redraws the terminal every 100 ms.
    * **main thread** — waits for raw key-strokes.
    """

    BAR_WIDTH = 44

    def __init__(self, path1: str, path2: str) -> None:
        self._path1 = Path(path1).resolve()
        self._path2 = Path(path2).resolve()

        # ── load & inspect ──────────────────────────────────────────
        sys.stdout.write(f" Loading  {self._path1.name} ... ")
        sys.stdout.flush()
        d1, sr1 = sf.read(str(self._path1), always_2d=True, dtype="float32")
        info1 = sf.info(str(self._path1))
        sys.stdout.write(f"{info1.samplerate} Hz  {info1.format}\n")

        sys.stdout.write(f" Loading  {self._path2.name} ... ")
        sys.stdout.flush()
        d2, sr2 = sf.read(str(self._path2), always_2d=True, dtype="float32")
        info2 = sf.info(str(self._path2))
        sys.stdout.write(f"{info2.samplerate} Hz  {info2.format}\n")

        sys.stdout.write("\n Preparing … ")
        sys.stdout.flush()

        # ── to stereo ───────────────────────────────────────────────
        if d1.shape[1] == 1:
            d1 = np.broadcast_to(d1, (d1.shape[0], 2)).copy()
        if d2.shape[1] == 1:
            d2 = np.broadcast_to(d2, (d2.shape[0], 2)).copy()

        # ── common sample rate (highest of the two) ─────────────────
        self._target_sr = max(sr1, sr2)

        if sr1 < self._target_sr:
            d1 = _resample_to(d1, sr1, self._target_sr)
        if sr2 < self._target_sr:
            d2 = _resample_to(d2, sr2, self._target_sr)

        # ── same length ─────────────────────────────────────────────
        max_n = max(d1.shape[0], d2.shape[0])
        for lst, d in [(1, d1), (2, d2)]:
            if d.shape[0] < max_n:
                pad = np.zeros((max_n - d.shape[0], 2), dtype="float32")
                if lst == 1:
                    d1 = np.concatenate([d1, pad])
                else:
                    d2 = np.concatenate([d2, pad])

        self._total_samples = max_n
        self._duration = max_n / self._target_sr

        # ── volume normalisation (RMS match) ────────────────────────
        rms1 = _rms(d1)
        rms2 = _rms(d2)
        if rms1 > 1e-8 and rms2 > 1e-8:
            ratio = rms1 / rms2
            d2 = d2 * ratio  # normalise d2 to d1's level

        # ── blind assignment ────────────────────────────────────────
        if random.random() < 0.5:
            self._a_data, self._b_data = d1, d2
            self._a_original, self._b_original = 1, 2
        else:
            self._a_data, self._b_data = d2, d1
            self._a_original, self._b_original = 2, 1

        self._orig_sample_rates = (info1.samplerate, info2.samplerate)

        # ── playback state (protected by _lock) ─────────────────────
        self._lock = threading.Lock()
        self._active: str = "A"        # "A" | "B"
        self._playing: bool = False
        self._cursor: int = 0           # sample index
        self._finished: bool = False    # True once cursor reaches end
        self._switch_flash: float = 0   # timestamp of last switch (for UI)

        # sounddevice stream (started in run())
        self._stream: Optional[sd.OutputStream] = None

        # term settings saved for restore
        self._old_term: Optional[list] = None

        sys.stdout.write("done.\n\n")
        sys.stdout.flush()
        time.sleep(0.8)

    # ── audio callback ───────────────────────────────────────────────

    def _audio_cb(self, outdata: np.ndarray, frames: int,
                  _time_info, _status) -> None:
        """Called by sounddevice from its own thread."""
        if _status:
            # benign underruns during fast switching are normal – ignore
            pass

        with self._lock:
            playing = self._playing
            if not playing or self._cursor >= self._total_samples:
                outdata.fill(0)
                if not playing and self._cursor >= self._total_samples:
                    pass  # already finished
                return

            data = self._a_data if self._active == "A" else self._b_data
            start = self._cursor
            end = min(start + frames, self._total_samples)
            n = end - start

            outdata[:n] = data[start:end]
            if n < frames:
                outdata[n:] = 0
                self._playing = False
                self._finished = True
            self._cursor = end

    # ── UI ───────────────────────────────────────────────────────────

    def _draw(self) -> None:
        with self._lock:
            active = self._active
            playing = self._playing
            cursor = self._cursor
            finished = self._finished
            flash = self._switch_flash

        elapsed = cursor / self._target_sr
        frac = cursor / self._total_samples if self._total_samples > 0 else 0
        bar_n = min(int(frac * self.BAR_WIDTH), self.BAR_WIDTH)
        bar = "\u2588" * bar_n + "\u2591" * (self.BAR_WIDTH - bar_n)

        # status icon
        if finished:
            icon = "\u23F9  FINISHED"
        elif playing:
            icon = "\u25B6  PLAYING"
        else:
            icon = "\u23F8  PAUSED"

        # switch flash indicator
        flash_str = ""
        if flash and (time.monotonic() - flash) < 0.6:
            flash_str = "  \u2194  SWITCH!"

        out = [
            "\033[H\033[J",                              # clear screen
            "\033[?25l",                                 # hide cursor
            "",
            "  \033[1m\u266B  AB BLIND AUDIO TEST\033[0m",
            "  " + "\u2500" * 56,
            "",
            f"  {icon}  \t[ \033[7m {active} \033[0m ]{flash_str}",
            "",
            f"  {_fmt_time(elapsed)}  /  {_fmt_time(self._duration)}",
            f"  \033[38;5;245m[{bar}]\033[0m  {_fmt_pct(frac)}",
            "",
            "  " + "\u2500" * 56,
            "  \033[38;5;245m"
            "  P  Play/Pause    Space  Switch A\u2194B    "
            "R  Restart    Q  Quit\033[0m",
            "  " + "\u2500" * 56,
            "",
        ]
        sys.stdout.write("\n".join(out))
        sys.stdout.flush()

    # ── control methods (thread-safe) ────────────────────────────────

    def _toggle_play(self) -> None:
        with self._lock:
            if self._finished:
                # restart
                self._cursor = 0
                self._finished = False
                self._playing = True
            elif self._playing:
                self._playing = False
            else:
                self._playing = True

    def _switch(self) -> None:
        with self._lock:
            self._active = "B" if self._active == "A" else "A"
            self._switch_flash = time.monotonic()

    def _restart(self) -> None:
        with self._lock:
            self._cursor = 0
            self._finished = False
            self._playing = True

    # ── main loop ────────────────────────────────────────────────────

    def run(self) -> None:
        if not sys.stdin.isatty():
            print("error: abtest.py requires a real TTY (run interactively, not via pipe/background)")
            sys.exit(1)
        # ── start audio stream ──────────────────────────────────────
        self._stream = sd.OutputStream(
            samplerate=self._target_sr,
            channels=2,
            callback=self._audio_cb,
            blocksize=256,
            latency="low",
        )
        self._stream.start()

        # ── display refresh thread ──────────────────────────────────
        display_t = threading.Thread(target=self._display_loop, daemon=True)
        display_t.start()

        # ── keyboard loop (main thread, raw tty) ────────────────────
        fd = sys.stdin.fileno()
        self._old_term = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if r:
                    ch = sys.stdin.read(1)
                    if ch in ("q", "Q"):
                        break
                    elif ch in ("p", "P"):
                        self._toggle_play()
                    elif ch == " ":
                        self._switch()
                    elif ch in ("r", "R"):
                        self._restart()
        finally:
            # restore terminal
            if self._old_term is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, self._old_term)
            # show cursor again
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            self._cleanup()

    def _display_loop(self) -> None:
        """Redraw every 100 ms until the stream is gone."""
        while self._stream is not None and self._stream.active:
            self._draw()
            time.sleep(0.1)
        self._draw()  # one last frame

    def _cleanup(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        # small delay so the display thread can exit
        time.sleep(0.15)
        self._show_results()

    def _show_results(self) -> None:
        sys.stdout.write("\033[?25h")   # ensure cursor visible
        sys.stdout.write("\033[H\033[J")
        f1, f2 = self._path1.name, self._path2.name
        sr1, sr2 = self._orig_sample_rates

        lines = [
            "",
            "  \033[1m\u2728  BLIND TEST RESULTS\033[0m",
            "  " + "\u2500" * 56,
            "",
            f"  \033[1mA\033[0m  \u2192  {f1 if self._a_original == 1 else f2}"
            f"  ({sr1 if self._a_original == 1 else sr2} Hz)",
            f"  \033[1mB\033[0m  \u2192  {f1 if self._b_original == 1 else f2}"
            f"  ({sr1 if self._b_original == 1 else sr2} Hz)",
            "",
            "  " + "\u2500" * 56,
            "  Original files:",
            f"    1. {f1}  ({sr1} Hz)",
            f"    2. {f2}  ({sr2} Hz)",
            "",
            "  \033[38;5;245mPress Q to exit.\033[0m",
            "",
        ]
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

        # Wait for Q in normal cooked mode
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    ch = sys.stdin.read(1)
                    if ch in ("q", "Q"):
                        break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            sys.stdout.write("\033[?25h\n")
            sys.stdout.flush()


# ──────────────────────────────────────────────────────────────────────
# entry
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        print("Usage:  python abtest.py <audio_file1> <audio_file2>")
        print("        Supported: .flac .mp3 .wav .ogg")
        sys.exit(1)

    for f in sys.argv[1:3]:
        if not os.path.isfile(f):
            print(f"File not found: {f}")
            sys.exit(1)

    # ignore SIGINT during raw tty mode (we handle Q ourselves)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    ab = ABTest(sys.argv[1], sys.argv[2])
    ab.run()


if __name__ == "__main__":
    main()
