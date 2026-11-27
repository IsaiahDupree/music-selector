# Orion audio capability audit

Read-only observation at 2026-10-15T04:12:07Z. Package metadata was read without
importing Torch, loading a model, downloading weights or executing audio work.
The existing 8788 controller listened; the previous isolated audio port 8791
had no listener. This is not a successful v2 job or current admission receipt.

| Installed metadata | Observed value | Meaning |
|---|---|---|
| Python | 3.11 on Orion Windows | Existing runtime; no new interpreter installed |
| NumPy / SciPy | 1.26.2 / 1.15.1 | Required by the existing and proposed analyzers |
| librosa / SoundFile | 0.10.2.post1 / 0.13.0 | Existing optional analysis tooling |
| Demucs | 4.0.1 | Installed metadata only, not verified inference |
| Torch / Torchaudio | 2.4.0+cu118 / 2.6.0 | Versions differ; do not advertise a ready stem backend |
| Spleeter / audio-separator / ONNX Runtime | Not found in this Python distribution metadata | Other environments were not exhaustively searched |
| FFmpeg | 7.1 essentials build | Existing direct binary; fresh hashes are required at job admission |
| FFmpeg filters | rubberband, atempo, loudnorm, ebur128, astats, aresample, asetrate | Actual `-filters` output confirms this binary includes them; no audio transform was run |

The [Torchaudio installation documentation](https://docs.pytorch.org/audio/stable/installation.html)
lists Torchaudio 2.6 with PyTorch 2.6 and explains that pre-2.11 releases link
to a single PyTorch version. The installed 2.6/2.4 pairing does not match that
matrix; metadata alone cannot establish successful execution. A separate, pinned environment
would be preferable to changing shared dependencies if stem work is pursued.

[Demucs' primary repository](https://github.com/facebookresearch/demucs) is
archived and points to a maintainer fork. Its documented separation outputs are
vocals, drums, bass and other accompaniment. Its two-stem option still performs
the underlying full separation. Default model selection can download weights,
and overlap, segment size and parallel jobs affect memory/time. Any future
worker must pin an already-approved model and dependency environment, block
implicit downloads, serialize GPU work, bound duration and preserve actual
source/output receipts. Installed Demucs is not an implemented DJ Lab feature.

A smaller proposed next extension is a fixed typed FFmpeg transform: content-
hashed staged input, semitone and tempo numeric bounds, fixed rubberband profile,
new WAV output, actual pre/post measurement and runtime/source hashes. A distinct
normalization job would require measured two-pass loudness with explicit target
and true-peak bounds. These are proposals only; there is no transform button
claim or live contract yet. Neither needs a proprietary Mixed In Key SDK.

The first implementation is instead the independent versioned analysis worker:
source-bound waveform, local pitch/tempo diagnostics, documented energy and
editable inferred cues. Heavy execution remains on authenticated Orion typed
jobs. The Mac edits, orchestrates and validates metadata only.
