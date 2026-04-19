"""Generate synthetic audio tap fixtures for FR-3 integration tests.

Physics model: x(t) = Σ_k  A_k · exp(-t/τ_k) · sin(2π f_k t + φ_k)

Validated parameters from ASM Handbook / Rosen et al. 2014:
  solid_karat  : f0~3200 Hz, τ~300 ms, harmonics at 2x/3x with decay
  hollow       : f0~1100 Hz, τ~ 80 ms, muffled (fewer harmonics)
  plated       : f0~3800 Hz, τ~130 ms, brighter centroid (brass substrate)
  quiet        : amplitude below -50 dB RMS threshold
  clipping     : amplitude above -3 dB (saturated)

Run: python tests/fixtures/make_audio.py
Output: tests/fixtures/tap_solid.wav etc.
"""
from __future__ import annotations

import struct
import wave
from pathlib import Path
import numpy as np

OUT = Path(__file__).parent
SR = 16_000


def _synth_tap(
    f0: float,
    tau_ms: float,
    harmonics: int = 4,
    duration_s: float = 0.5,
    amplitude: float = 0.55,
    noise_level: float = 0.01,
) -> np.ndarray:
    """Synthesise exponentially decaying multi-harmonic tap sound."""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    x = np.zeros_like(t)
    tau = tau_ms / 1000.0
    for k in range(1, harmonics + 1):
        # Higher harmonics decay faster (Q decreases with mode order)
        tau_k = tau / (k ** 0.7)
        A_k = amplitude / k
        phi = np.random.uniform(0, 2 * np.pi)
        x += A_k * np.exp(-t / tau_k) * np.sin(2 * np.pi * f0 * k * t + phi)
    x += np.random.normal(0, noise_level, len(t))
    return x


def _write_wav(path: Path, x: np.ndarray) -> None:
    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    rms_db = 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-9)
    print(f"  {path.name}: rms={rms_db:.1f} dB  len={len(x)/SR:.2f}s")


rng = np.random.default_rng(42)

print("Generating audio fixtures …")

# solid_karat: 22K gold ring tap — high f0, long ring (Rosen 2014)
np.random.seed(1)
x = _synth_tap(f0=3200, tau_ms=310, harmonics=5, amplitude=0.55)
_write_wav(OUT / "tap_solid.wav", x)

# hollow: hollow gold bangle — low f0, short decay
np.random.seed(2)
x = _synth_tap(f0=1100, tau_ms=78, harmonics=3, amplitude=0.50)
_write_wav(OUT / "tap_hollow.wav", x)

# plated: brass-core ring — brighter, intermediate decay
np.random.seed(3)
x = _synth_tap(f0=3800, tau_ms=130, harmonics=6, amplitude=0.52)
_write_wav(OUT / "tap_plated.wav", x)

# too quiet: well below -50 dB floor
np.random.seed(4)
x = np.random.normal(0, 1e-4, SR * 1)   # RMS ~ -80 dB
_write_wav(OUT / "tap_quiet.wav", x)

# clipping: saturated signal — above -3 dB
np.random.seed(5)
x = np.ones(SR) * 0.97 + np.random.normal(0, 0.01, SR)
_write_wav(OUT / "tap_clipping.wav", x)

print("done")
