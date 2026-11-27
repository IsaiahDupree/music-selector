"""Versioned bounded audio measurements; no verified musical or rights claims."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workers import harmonic_audio as legacy
from workers.audio_process_guard import protect_process_tree

PARAMETERS = ["manifest_input_id", "manifest_sha256", "output_name", "timeout_sec"]
CONTRACT = "orion_harmonic_analysis_v2"
RESULT_CONTRACT = "orion_harmonic_analysis_result_v2"
SAMPLE_RATE = 11025
WINDOW_SECONDS = 30
WAVEFORM_HZ = 20
THREAD_ENV = {key: "2" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}
ENERGY_METHOD = {
    "id": "djlab_energy_v1", "range": [0, 100],
    "formula": "100*(0.50*clip((rms_dbfs+45)/40,0,1)+0.30*clip(onsets_per_second/6,0,1)+0.20*clip(spectral_centroid_hz/4000,0,1))",
    "aggregation": "duration-weighted mean of measured windows",
    "meaning": "Independent signal activity heuristic; not perceived-energy calibration or Mixed In Key equivalence.",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("audio v2 absolute deadline exceeded")
    return value


def sha(path, deadline=None):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            if deadline is not None:
                remaining(deadline)
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def unlinked(path):
    path = Path(path).absolute()
    for ancestor in [path, *path.parents]:
        if ancestor.exists() or ancestor.is_symlink():
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("linked/reparse paths are forbidden")
    return path


def staged(root, value, extensions):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ValueError("invalid staged input ID")
    root = unlinked(root).resolve()
    if "\\" in value or ":" in value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError("input must be a relative staged path")
    path = unlinked(root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in extensions:
        raise ValueError("invalid or missing staged input")
    return path


def write_json(path, value):
    path = Path(path)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    temp = path.with_name(path.name + ".partial")
    with temp.open("x", encoding="utf-8") as f:
        f.write(data)
    os.replace(temp, path)


def runtime_binding(ffmpeg, deadline=None):
    if not ffmpeg:
        raise ValueError("registered FFmpeg unavailable")
    exe = unlinked(ffmpeg).resolve()
    probe = exe.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    paths = {"python": Path(sys.executable), "ffmpeg": exe, "ffprobe": probe,
             "runner": Path(__file__), "legacy_analyzer": Path(legacy.__file__),
             "process_guard": ROOT / "workers/audio_process_guard.py"}
    files = {}
    for name, path in paths.items():
        path = unlinked(path).resolve()
        if not path.is_file():
            raise ValueError(f"runtime file unavailable: {name}")
        files[name] = {"path": str(path), "sha256": sha(path, deadline), "bytes": path.stat().st_size}
    packages, inventories = {}, {}
    for name in ("numpy", "scipy"):
        dist = importlib.metadata.distribution(name)
        rows, total = [], 0
        for item in sorted(dist.files or [], key=str):
            # Bytecode is interpreter-generated, not an executable source pin.
            if str(item).endswith(".pyc"):
                continue
            path = unlinked(dist.locate_file(item)).resolve()
            if not path.is_file():
                raise ValueError(f"installed package member missing: {name}")
            total += path.stat().st_size
            if total > 512 * 1024**2 or len(rows) >= 10000:
                raise ValueError("installed package exceeds audit bound")
            rows.append({"name": str(item).replace("\\", "/"), "sha256": sha(path, deadline), "bytes": path.stat().st_size})
        if not rows:
            raise ValueError("installed dependency has no file inventory")
        packages[name] = {"version": dist.version, "root": str(Path(dist.locate_file("")).resolve()),
                          "file_count": len(rows), "bytes": total, "tree_sha256": digest(rows)}
        inventories[name] = rows
    return {"engine": "djlab_segmented_stft_v2", "files": files, "packages": packages,
            "threads": 2, "platform": sys.platform, "python_version": sys.version,
            "external_dll_closure_pinned": False, "downloads_allowed": False}, inventories


def validate(params, input_root, ffmpeg, deadline=None):
    if not isinstance(params, dict) or set(params) != set(PARAMETERS):
        raise ValueError("audio v2 requires exactly its four documented parameters")
    source = staged(input_root, params["manifest_input_id"], {".json"})
    if source.stat().st_size > 128 * 1024 or sha(source, deadline) != params["manifest_sha256"]:
        raise ValueError("manifest oversized or hash mismatch")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {"contract", "tracks", "coverage_mode", "max_seconds"} or manifest["contract"] != CONTRACT:
        raise ValueError("invalid v2 manifest contract or fields")
    mode = manifest["coverage_mode"]
    if mode not in {"prefix", "full"}:
        raise ValueError("coverage_mode must be prefix or full")
    limit = legacy.number(manifest["max_seconds"], "max_seconds", 20, 240 if mode == "prefix" else 7200)
    tracks = manifest["tracks"]
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 8 or len(tracks) * limit > 7200:
        raise ValueError("v2 accepts 1–8 tracks with at most 7200 requested analysis seconds")
    total, ids = 0, set()
    for track in tracks:
        if not isinstance(track, dict) or set(track) - {"input_id", "sha256", "label"} or not {"input_id", "sha256"} <= set(track):
            raise ValueError("invalid track fields")
        audio = staged(input_root, track["input_id"], legacy.EXTENSIONS | {".aif", ".aiff"})
        total += audio.stat().st_size
        if not 1 <= audio.stat().st_size <= 512 * 1024**2 or total > 2 * 1024**3 or sha(audio, deadline) != track["sha256"]:
            raise ValueError("track oversized or hash mismatch")
        if track["input_id"] in ids or not isinstance(track.get("label", ""), str) or len(track.get("label", "")) > 300:
            raise ValueError("duplicate input or invalid track label")
        ids.add(track["input_id"])
    name = params["output_name"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,90}\.json", name) or name in {"analysis-progress.json", "runtime-files.json", "execution-result.json", "commands.json"} or re.fullmatch(r"track-[0-9]+-(?:result|progress)\.json", name):
        raise ValueError("invalid or reserved output name")
    if type(params["timeout_sec"]) is not int or not 120 <= params["timeout_sec"] <= 3600:
        raise ValueError("timeout_sec must be an integer in 120..3600")
    runtime, _ = runtime_binding(ffmpeg, deadline)
    return {**params, "manifest": manifest, "runtime": runtime}, "cpu-heavy", 0


def command(job, job_dir, input_root, environment, ffmpeg):
    params = job["params"]
    checked, _, _ = validate({key: params[key] for key in PARAMETERS}, input_root, ffmpeg)
    if checked != params:
        raise RuntimeError("audio v2 source/runtime changed after admission")
    config = {"job_id": job["job_id"], "job_type": job["job_type"], "params": params,
              "input_root": str(input_root), "output_root": str(job_dir / "out")}
    config_path = job_dir / "audio-v2-config.json"
    with config_path.open("x", encoding="utf-8") as f:
        json.dump(config, f, indent=2, allow_nan=False)
    environment.update(THREAD_ENV, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    job["runtime"] = params["runtime"]
    return [sys.executable, str(Path(__file__).resolve()), "--config", str(config_path)], ROOT, environment


def window_features(y, sr):
    """One actual decoded window; all musical interpretations remain inferred."""
    import numpy as np
    from scipy import signal
    if len(y) == 0 or not np.all(np.isfinite(y)):
        raise ValueError("empty or non-finite audio samples")
    duration = len(y) / sr
    rms = float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))
    rms_db = 20 * math.log10(max(rms, 1e-12))
    spectrum = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    centroid = float(np.sum(np.fft.rfftfreq(len(y), 1 / sr) * spectrum) / max(float(spectrum.sum()), 1e-12))
    _, times, z = signal.stft(y, fs=sr, nperseg=min(1024, len(y)), noverlap=min(768, max(0, len(y)-1)), boundary=None)
    magnitude = np.abs(z)
    flux = np.maximum(np.diff(magnitude, axis=1), 0).sum(axis=0) / np.maximum(magnitude[:, 1:].sum(axis=0), 1e-9)
    threshold = float(np.median(flux) + 1.5 * np.median(np.abs(flux - np.median(flux)))) if len(flux) else 0
    peaks, properties = signal.find_peaks(flux, height=max(threshold, .02), distance=max(1, round(sr / 256 * .10)))
    onset_times = times[1:][peaks]
    density = len(peaks) / duration
    activity = 100 * (.5 * np.clip((rms_db + 45) / 40, 0, 1) + .3 * np.clip(density / 6, 0, 1) + .2 * np.clip(centroid / 4000, 0, 1))
    diagnostics = None
    if duration >= 5 and float(np.max(np.abs(y))) >= 1e-6:
        diagnostics = legacy.analyze_signal(y, sr)
    uncertainty = ["not_listening_verified", "scores_are_not_probabilities", "downbeat_phase_unverified"]
    if diagnostics is None:
        uncertainty.append("insufficient_audible_signal")
    elif diagnostics["key_correlation"] is None or diagnostics["key_correlation"] < .45 or diagnostics["key_separation"] < .08:
        uncertainty.append("ambiguous_tonal_key")
    periodicity = max(0.0, min(1.0, diagnostics["tempo_periodicity"])) if diagnostics and len(peaks) >= 4 else 0
    if periodicity < .25:
        uncertainty.append("weak_periodic_pulse")
    return {"duration_seconds": duration, "rms_dbfs": round(rms_db, 4), "spectral_centroid_hz": round(centroid, 3),
            "onsets_per_second": round(density, 5), "onset_times_seconds": [round(float(x), 5) for x in onset_times],
            "energy_score": round(float(activity), 3), "analysis": diagnostics,
            "onset_confidence": {"method": "relative_positive_spectral_flux_median_mad_floor_0.02_v1", "threshold": max(threshold, .02),
                                 "median_peak_to_threshold": float(np.median(properties["peak_heights"]) / max(threshold, .02)) if len(peaks) else 0,
                                 "calibrated_probability": False},
            "beat_confidence": {"score": periodicity, "method": "normalized_onset_autocorrelation", "calibrated_probability": False},
            "uncertainty": uncertainty}


def waveform(y, sr, start):
    import numpy as np
    rows = []
    # Rational interval boundaries avoid cumulative 11025/20 sample rounding drift.
    for i in range(math.ceil(len(y) * WAVEFORM_HZ / sr)):
        a, b = round(i * sr / WAVEFORM_HZ), min(len(y), round((i + 1) * sr / WAVEFORM_HZ))
        part = y[a:b]
        if not len(part):
            continue
        rows.append([round(start + a / sr, 6), round(float(np.min(part)), 6), round(float(np.max(part)), 6),
                     round(float(np.sqrt(np.mean(np.square(part, dtype=np.float64)))), 6)])
    return rows


def summarize(windows, duration, covered):
    """Aggregate measured windows, never extend a prefix result to the full track."""
    usable = [w for w in windows if w["analysis"] is not None]
    votes, tempo_rows = {}, []
    for w in usable:
        d = w["analysis"]
        for key in d["key_alternatives"]:
            votes[key["key"]] = votes.get(key["key"], 0) + max(0, key["correlation"]) * w["duration_seconds"]
        if w["beat_confidence"]["score"] >= .25:
            tempo_rows.append((d["bpm_estimate"], w["duration_seconds"] * w["beat_confidence"]["score"]))
    best = sorted(votes, key=votes.get, reverse=True)
    selected_bpm = None
    if tempo_rows:
        ranked = sorted(tempo_rows)
        half = sum(row[1] for row in ranked) / 2
        cumulative = 0
        for bpm, weight in ranked:
            cumulative += weight
            if cumulative >= half:
                selected_bpm = bpm
                break
    alternatives = []
    if selected_bpm is not None:
        for multiplier in (.5, 1, 2):
            candidate = selected_bpm * multiplier
            if 30 <= candidate <= 380:
                alternatives.append({"bpm": round(candidate, 3), "relationship": {0.5: "half_time", 1: "selected_interpretation", 2: "double_time"}[multiplier], "calibrated_probability": False})
    cue_candidates = []
    rhythmic = [w for w in usable if w["beat_confidence"]["score"] >= .25]
    if rhythmic:
        first = rhythmic[0]
        cue_candidates.append((1000, first["start_seconds"] + first["analysis"]["beat_offset_seconds"], "first_inferred_beat", first["beat_confidence"]["score"]))
    for previous, current in zip(windows, windows[1:]):
        novelty = abs(current["energy_score"] - previous["energy_score"])
        key_changed = bool(previous["analysis"] and current["analysis"] and previous["analysis"]["key_estimate"] != current["analysis"]["key_estimate"])
        if novelty >= 2 or key_changed:
            cue_candidates.append((novelty + (10 if key_changed else 0), current["start_seconds"], "measured_window_change", min(1, novelty / 50)))
    for w in windows:
        for onset in w["onset_times_seconds"]:
            cue_candidates.append((w["energy_score"] / 10, w["start_seconds"] + onset, "detected_onset", w["beat_confidence"]["score"]))
    cues = []
    for salience, seconds, kind, confidence in sorted(cue_candidates, reverse=True):
        if 0 <= seconds < covered and all(abs(seconds - c["seconds"]) >= 8 for c in cues):
            cues.append({"seconds": round(seconds, 5), "kind": kind, "confidence": round(confidence, 4),
                         "confidence_is_probability": False, "inferred": True, "editable": True, "listening_verified": False})
        if len(cues) == 8:
            break
    cues.sort(key=lambda c: c["seconds"])
    for i, cue in enumerate(cues, 1):
        cue["id"] = f"suggestion-{i}"
    return {"key_estimate": best[0] if best else None, "key_alternatives": [{"key": k, "weighted_correlation_score": round(votes[k] / max(covered, 1e-12), 5)} for k in best[:5]],
            "bpm_estimate": selected_bpm, "tempo_alternatives": alternatives,
            "local_tempo_evidence": [{"bpm": bpm, "weighted_periodicity": round(weight / max(covered, 1e-12), 5)} for bpm, weight in sorted(tempo_rows, key=lambda r: r[1], reverse=True)[:8]],
            "key_confidence": {"method": "duration_weighted_positive_top3_profile_correlations", "calibrated_probability": False,
                               "separation": round((votes[best[0]] - votes[best[1]]) / max(covered, 1e-12), 5) if len(best) > 1 else None},
            "energy": {**ENERGY_METHOD, "score": round(sum(w["energy_score"] * w["duration_seconds"] for w in windows) / max(covered, 1e-12), 3)},
            "cue_suggestions": cues, "manual_review_required": True,
            "coverage": {"intervals_seconds": [[0, round(covered, 6)]], "analyzed_seconds": round(covered, 6),
                         "source_duration_seconds": duration, "container_duration_tolerance_seconds": .05, "full_track": abs(duration - covered) <= .05,
                         "method": "contiguous_bounded_decoding_30_second_windows"}}


class Runner:
    def __init__(self, output, deadline):
        self.output, self.deadline, self.commands = output, deadline, []

    def run(self, name, argv, max_bytes=4 * 1024**2):
        stdout, stderr = self.output / (name + ".stdout"), self.output / (name + ".stderr.txt")
        start = now()
        with stdout.open("xb") as out, stderr.open("xb") as err:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                code = process.wait(timeout=min(180, remaining(self.deadline)))
            except BaseException:
                process.kill(); process.wait(timeout=10)
                raise
        row = {"name": name, "argv": argv, "pid": process.pid, "started_at": start, "completed_at": now(), "exit_code": code,
               "stdout": stdout.name, "stdout_sha256": sha(stdout, self.deadline), "stdout_bytes": stdout.stat().st_size, "stdout_retention": "digest_only_ephemeral_decoded_pcm" if "-window-" in name else "retained",
               "stderr": stderr.name, "stderr_sha256": sha(stderr, self.deadline)}
        self.commands.append(row)
        write_json(self.output / "commands.json", self.commands)
        if code != 0 or stdout.stat().st_size > max_bytes or stderr.stat().st_size > 4 * 1024**2:
            raise RuntimeError(f"{name} failed or exceeded output bounds")
        return stdout


def execute(config_path):
    started = time.monotonic()
    config_path = unlinked(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    params = config["params"]
    deadline = started + params["timeout_sec"] - 30
    output = unlinked(config["output_root"])
    if output.name != "out" or output.parent.name != config["job_id"] or not re.fullmatch(r"wrk_[0-9a-f]{32}", config["job_id"]):
        raise ValueError("output must be this job's owned out directory")
    if config_path.parent != output.parent or not config_path.is_file():
        raise ValueError("configuration must be a regular file in the owned job directory")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("refusing to overwrite retained output")
    if config.get("job_type") != "audio.harmonic_analyze_v2":
        raise ValueError("wrong worker job type")
    result = {"contract": RESULT_CONTRACT, "job_id": config["job_id"], "passed": False, "tracks": [],
              "runtime": params["runtime"], "rights_verified": False, "listening_verified": False,
              "manifest_sha256": params["manifest_sha256"], "started_at": now()}
    runner = Runner(output, deadline)
    try:
        guard = protect_process_tree()  # Handle stays live until wrapper exit, including abrupt controller cancellation.
        ffmpeg = params["runtime"]["files"]["ffmpeg"]["path"]
        ffprobe = params["runtime"]["files"]["ffprobe"]["path"]
        checked, _, _ = validate({key: params[key] for key in PARAMETERS}, config["input_root"], ffmpeg, deadline)
        if checked != params:
            raise ValueError("source/runtime changed before execution")
        current, inventory = runtime_binding(ffmpeg, deadline)
        write_json(output / "runtime-files.json", inventory)
        runner.run("ffmpeg-version", [ffmpeg, "-version"])
        runner.run("ffprobe-version", [ffprobe, "-version"])
        import numpy as np
        for index, track in enumerate(params["manifest"]["tracks"]):
            remaining(deadline)
            path = staged(config["input_root"], track["input_id"], legacy.EXTENSIONS | {".aif", ".aiff"})
            prefix = f"track-{index+1:02d}"
            probe_path = runner.run(prefix + "-probe", [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
            duration = float(probe.get("format", {}).get("duration", 0))
            if len(audio_streams) != 1 or not math.isfinite(duration) or not 5 <= duration <= 7200:
                raise ValueError("source requires one audio stream and duration 5..7200 seconds")
            manifest = params["manifest"]
            if manifest["coverage_mode"] == "full" and duration > manifest["max_seconds"] + .001:
                raise ValueError("full analysis refuses to truncate a source above its duration limit")
            target = min(duration, manifest["max_seconds"])
            windows, peaks = [], []
            for window_index in range(math.ceil(target / WINDOW_SECONDS)):
                start = window_index * WINDOW_SECONDS
                length = min(WINDOW_SECONDS, target - start)
                pcm = runner.run(f"{prefix}-window-{window_index+1:03d}", [ffmpeg, "-nostdin", "-v", "error", "-threads", "2", "-ss", f"{start:.9f}", "-i", str(path),
                    "-t", f"{length:.9f}", "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
                    max_bytes=math.ceil(length * SAMPLE_RATE) * 4 + 4096)
                raw = pcm.read_bytes()
                y = np.frombuffer(raw, dtype="<f4")
                tolerance = .05 if start + length >= target - 1e-6 else 1 / SAMPLE_RATE
                if abs(len(y) / SAMPLE_RATE - length) > tolerance:
                    raise ValueError("decoded window duration differs from requested coverage")
                features = window_features(y, SAMPLE_RATE)
                windows.append({"start_seconds": start, "end_seconds": start + len(y) / SAMPLE_RATE,
                                "section_kind": "analysis_window_not_named_musical_section", **features})
                peaks.extend(waveform(y, SAMPLE_RATE, start))
                # Persist completed measured windows; partial records never advertise full-track success.
                write_json(output / (prefix + "-progress.json"), {"input_id": track["input_id"], "source_sha256": track["sha256"], "complete": False,
                           "completed_windows": windows, "decoded_pcm_sha256": [r["stdout_sha256"] for r in runner.commands if r["name"].startswith(prefix + "-window-")]})
                # PCM bytes are ephemeral; retain exact argv, byte count and SHA, not duplicated source media.
                pcm.unlink()
                print(json.dumps({"event": "window_complete", "track": index+1, "start_seconds": start, "end_seconds": windows[-1]["end_seconds"]}), flush=True)
            covered = windows[-1]["end_seconds"]
            if sha(path, deadline) != track["sha256"]:
                raise ValueError("source changed during analysis")
            row = {**track, "duration_seconds": duration, **summarize(windows, duration, covered),
                   "sections": windows, "waveform": {"channels": ["time_seconds", "minimum", "maximum", "rms"], "sample_rate": SAMPLE_RATE,
                   "nominal_hz": WAVEFORM_HZ, "normalization": "absolute_mono_downmix_float_pcm_full_scale_no_peak_normalization",
                   "frames": peaks}, "decoded_audio": {"sample_rate": SAMPLE_RATE, "channels": 1, "format": "f32le", "no_source_mutation": True}}
            write_json(output / (prefix + "-result.json"), row)
            result["tracks"].append(row)
            write_json(output / "analysis-progress.json", {"contract": RESULT_CONTRACT, "complete": False, "completed_track_count": len(result["tracks"]),
                       "requested_track_count": len(manifest["tracks"]), "track_result_files": [f"track-{i+1:02d}-result.json" for i in range(len(result["tracks"]))]})
        after, _ = runtime_binding(ffmpeg, deadline)
        final, _, _ = validate({key: params[key] for key in PARAMETERS}, config["input_root"], ffmpeg, deadline)
        if after != current or final != params:
            raise ValueError("source/runtime changed during job")
        result.update(passed=True, source_hashes_verified_after=True, runtime_verified_after=True)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result.update(completed_at=now(), elapsed_seconds=round(time.monotonic()-started, 3), commands_sha256=sha(output / "commands.json") if (output / "commands.json").exists() else None)
    write_json(output / params["output_name"], result)
    write_json(output / "execution-result.json", {k: v for k, v in result.items() if k != "tracks"})
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    raise SystemExit(execute(parser.parse_args().config))
