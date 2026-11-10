import numpy as np

from greeter.audio import float_to_pcm16, pcm16_to_float, resample, to_mono


def peak_hz(x, rate):
    spectrum = np.abs(np.fft.rfft(x))
    return np.fft.rfftfreq(len(x), 1 / rate)[np.argmax(spectrum)]


def test_resample_16k_to_24k_keeps_pitch_and_ratio():
    t = np.arange(16000) / 16000
    x = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    y = resample(x, 16000, 24000)
    assert abs(len(y) - 24000) <= 1
    assert abs(peak_hz(y, 24000) - 1000) <= 20


def test_resample_same_rate_is_identity():
    x = np.linspace(-1, 1, 100, dtype=np.float32)
    assert np.array_equal(resample(x, 16000, 16000), x)


def test_pcm16_round_trip():
    x = np.linspace(-1, 1, 1000, dtype=np.float32)
    assert np.max(np.abs(pcm16_to_float(float_to_pcm16(x)) - x)) <= 1 / 32767 + 1e-6


def test_out_of_range_is_clipped_not_wrapped():
    y = pcm16_to_float(float_to_pcm16(np.array([1.5, -1.5], np.float32)))
    assert y[0] > 0.99 and y[1] < -0.99


def test_to_mono_averages_channels():
    x = np.array([[0.2, 0.4], [-0.2, 0.0]], np.float32)
    assert np.allclose(to_mono(x), [0.3, -0.1])


def test_to_mono_passes_mono_through():
    x = np.array([0.1, 0.2], np.float32)
    assert np.array_equal(to_mono(x), x)
