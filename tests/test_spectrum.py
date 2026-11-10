import numpy as np

from factory_control.supervisor.analyzer.vibration import amplitude_spectrum


def test_amplitude_spectrum_recovers_tone_amplitude():
    fs, n, f0, amp = 2560.0, 1024, 50.0, 0.7  # f0 lands exactly on bin 20
    t = np.arange(n) / fs
    freqs, a = amplitude_spectrum(amp * np.sin(2 * np.pi * f0 * t), fs)
    k = int(np.argmax(a))
    assert freqs[k] == f0
    assert abs(a[k] - amp) < 1e-2
