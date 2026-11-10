"""PCM conversion helpers between the Reachy SDK (float32) and OpenAI realtime (PCM16 @ 24 kHz)."""
from __future__ import annotations

import numpy as np


def to_mono(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x.mean(axis=1).astype(np.float32) if x.ndim == 2 else x


def resample(x: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    if src_hz == dst_hz or len(x) == 0:
        return x
    n_out = int(round(len(x) * dst_hz / src_hz))
    src_t = np.arange(len(x)) / src_hz
    dst_t = np.arange(n_out) / dst_hz
    return np.interp(dst_t, src_t, x).astype(np.float32)


def float_to_pcm16(x: np.ndarray) -> bytes:
    return (np.clip(x, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def pcm16_to_float(b: bytes) -> np.ndarray:
    return (np.frombuffer(b, dtype="<i2").astype(np.float32) / 32767).astype(np.float32)
