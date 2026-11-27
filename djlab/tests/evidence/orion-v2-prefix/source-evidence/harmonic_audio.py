"""Bounded, content-addressed DJ analysis and phrase-crossfade jobs for Orion.

Estimates are diagnostic measurements, never verified musical keys/downbeats or
copyright clearance. Callers supply staged files, not commands or filter graphs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

PARAMETERS = ["manifest_input_id", "manifest_sha256", "output_name", "timeout_sec"]
EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def staged(root, value, extensions):
    root = Path(root).resolve()
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(value) or ":" in str(value):
        raise ValueError("input must be a relative staged path")
    p = root
    for part in relative.parts:
        p = p / part
        if p.is_symlink():
            raise ValueError("staged symlinks are forbidden")
    p = p.resolve()
    if not p.is_relative_to(root) or p.suffix.lower() not in extensions or not p.is_file():
        raise ValueError("missing or invalid staged input")
    return p


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return float(value)


def validate(params, input_root, job_type):
    if set(params) - set(PARAMETERS):
        raise ValueError("unknown audio parameters")
    source = staged(input_root, params.get("manifest_input_id", ""), {".json"})
    if source.stat().st_size > 128 * 1024 or sha(source) != params.get("manifest_sha256"):
        raise ValueError("audio manifest is oversized or hash mismatch")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    mixing = job_type == "audio.dj_mix"
    expected = "orion_dj_mix_v1" if mixing else "orion_harmonic_analysis_v1"
    if manifest.get("contract") != expected:
        raise ValueError("incorrect audio manifest contract")
    allowed = {"contract", "tracks", "target_bpm", "crossfade_beats"} if mixing else {"contract", "tracks", "analysis_seconds"}
    if set(manifest) - allowed:
        raise ValueError("unknown audio manifest fields")
    tracks = manifest.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 24:
        raise ValueError("audio jobs require 1–24 tracks")
    seconds = number(manifest.get("analysis_seconds", 180), "analysis_seconds", 20, 240) if not mixing else None
    target = number(manifest.get("target_bpm"), "target_bpm", 60, 190) if mixing else None
    beats = number(manifest.get("crossfade_beats", 16), "crossfade_beats", 4, 64) if mixing else None
    if mixing and (int(beats) != beats or int(beats) % 4):
        raise ValueError("crossfade_beats must contain whole four-beat bars")
    total = 0.0
    total_bytes = 0
    for track in tracks:
        allowed_track = {"input_id", "sha256", "label"} | ({"cue_seconds", "source_bpm", "beats", "gain_db"} if mixing else set())
        if not isinstance(track, dict) or set(track) - allowed_track:
            raise ValueError("unknown track fields")
        audio = staged(input_root, track.get("input_id", ""), EXTENSIONS)
        size = audio.stat().st_size
        total_bytes += size
        if not 1 <= size <= 512 * 1024 * 1024 or total_bytes > 4 * 1024**3 or sha(audio) != track.get("sha256"):
            raise ValueError("track is oversized or hash mismatch")
        if len(str(track.get("label", ""))) > 300:
            raise ValueError("track label exceeds 300 characters")
        if mixing:
            number(track.get("cue_seconds"), "cue_seconds", 0, 7200)
            bpm = number(track.get("source_bpm"), "source_bpm", 60, 190)
            count = number(track.get("beats"), "beats", 32, 2048)
            if int(count) != count or int(count) % 4 or count <= 2 * beats:
                raise ValueError("segments must contain whole bars and exceed two crossfades")
            number(track.get("gain_db", 0), "gain_db", -24, 6)
            if not 0.90 <= target / bpm <= 1.10:
                raise ValueError("pitch-preserving tempo change exceeds 10 percent")
            total += count * 60 / target
    if mixing:
        total -= (len(tracks) - 1) * beats * 60 / target
        if not 30 <= total <= 1800:
            raise ValueError("mix duration must be 30–1800 seconds")
    name = str(params.get("output_name", ""))
    extension = ".wav" if mixing else ".json"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", name) or not name.endswith(extension):
        raise ValueError("invalid audio output filename")
    timeout = params.get("timeout_sec", 1800)
    if type(timeout) is not int or not 30 <= timeout <= 3600:
        raise ValueError("audio timeout must be 30–3600 seconds")
    return {**params, "timeout_sec": timeout, "manifest": manifest, "expected_duration_seconds": total if mixing else None}, "cpu-heavy", 0


def command(job, job_dir, input_root, environment, ffmpeg):
    params = job["params"]
    checked, _, _ = validate({k: params[k] for k in PARAMETERS}, input_root, job["job_type"])
    if checked != params:
        raise RuntimeError("audio inputs changed after admission")
    if not ffmpeg:
        raise RuntimeError("FFmpeg unavailable")
    config = {"job_type": job["job_type"], "params": params, "input_root": str(input_root),
              "output_root": str(job_dir / "out"), "ffmpeg": ffmpeg}
    config_path = job_dir / "audio-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    environment.update(OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2", NUMBA_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2", VECLIB_MAXIMUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1")
    job["runtime"] = {"engine": "numpy-scipy-stft-autocorrelation-v1", "python": sys.executable,
                      "audio_worker_sha256": sha(__file__), "downloads_allowed": False,
                      "rights_verified": False, "tempo_and_key_are_estimates": True}
    return [sys.executable, str(Path(__file__).resolve()), "--config", str(config_path)], Path(__file__).parent, environment


def analyze_signal(y, sr):
    import numpy as np
    from scipy import signal
    if not np.all(np.isfinite(y)):
        raise ValueError("non-finite audio samples")
    if len(y) < sr * 5 or float(np.max(np.abs(y))) < 1e-6:
        raise ValueError("insufficient audible signal for analysis")
    n = 4096
    hop = 256
    freqs, times, stft = signal.stft(y, fs=sr, nperseg=n, noverlap=n-hop, boundary=None)
    magnitude = np.abs(stft)
    positive = np.maximum(np.diff(magnitude, axis=1), 0)
    onset = positive.sum(axis=0)
    onset = np.maximum(onset - np.median(onset), 0)
    onset_rate = sr / hop
    corr = signal.correlate(onset, onset, mode="full", method="fft")[len(onset)-1:]
    low = int(onset_rate * 60 / 190)
    high = min(len(corr)-1, int(onset_rate * 60 / 60))
    peaks, _ = signal.find_peaks(corr[low:high+1])
    lags = (peaks + low).tolist() or [low + int(np.argmax(corr[low:high+1]))]
    # Prefer dance-tempo interpretation but retain the half/double-time ambiguity.
    ranked = sorted(lags, key=lambda lag: corr[lag] * (1.0 if 110 <= onset_rate*60/lag <= 175 else .86), reverse=True)
    lag = ranked[0]
    frac = 0.0
    if 0 < lag < len(corr)-1:
        denominator = corr[lag-1] - 2*corr[lag] + corr[lag+1]
        if abs(denominator) > 1e-12:
            frac = .5*(corr[lag-1]-corr[lag+1])/denominator
    bpm = float(onset_rate * 60 / (lag + frac))
    autocorrelation_bpm = bpm
    # Sub-frame precision matters over many bars: refine the selected half/full
    # time interpretation against the spectral pulse of the whole onset curve.
    fft_size = 1 << int(math.ceil(math.log2(max(32, len(onset) * 8))))
    pulse = np.abs(np.fft.rfft(onset * np.hanning(len(onset)), n=fft_size))
    pulse_bpms = np.fft.rfftfreq(fft_size, d=1/onset_rate) * 60
    candidates = np.flatnonzero((pulse_bpms >= max(60,bpm*.94)) & (pulse_bpms <= min(190,bpm*1.06)))
    pulse_ratio = 0.0
    if len(candidates):
        strongest = int(candidates[int(np.argmax(pulse[candidates]))])
        pulse_ratio = float(pulse[strongest] / max(float(np.median(pulse[candidates])), 1e-12))
        if pulse_ratio >= 2:
            bpm = float(pulse_bpms[strongest])
    period = 60 / bpm
    # Offset aligns the detected onset comb; bar/phrase position remains inferred.
    offsets = np.linspace(0, period, 128, endpoint=False)
    scores = []
    onset_times = times[1:]
    for offset in offsets:
        grid = np.arange(offset, len(y)/sr, period)
        scores.append(float(np.interp(grid, onset_times, onset, left=0, right=0).sum()))
    offset = float(offsets[int(np.argmax(scores))])
    rms = float(np.sqrt(np.mean(y*y)))
    valid = (freqs >= 65) & (freqs <= 4000)
    midi = np.rint(69 + 12*np.log2(freqs[valid]/440)).astype(int)
    energy = np.mean(magnitude[valid], axis=1)
    chroma = np.bincount(midi % 12, weights=energy, minlength=12)
    chroma /= max(float(chroma.sum()), 1e-12)
    major = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
    minor = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    camelot_major = [8,3,10,5,12,7,2,9,4,11,6,1]
    camelot_minor = [5,12,7,2,9,4,11,6,1,8,3,10]
    keys = []
    for mode, profile, wheel in [("major",major,camelot_major),("minor",minor,camelot_minor)]:
        for root in range(12):
            score = float(np.corrcoef(chroma,np.roll(profile,root))[0,1]) if float(np.std(chroma)) > 1e-6 else None
            if score is not None and math.isfinite(score):
                keys.append({"key": names[root]+" "+mode,"camelot":str(wheel[root])+("B" if mode=="major" else "A"),"correlation":score})
    keys.sort(key=lambda item:item["correlation"],reverse=True)
    return {"bpm_estimate":round(bpm,3),"bpm_autocorrelation_estimate":round(autocorrelation_bpm,3),
            "pulse_peak_to_median":round(pulse_ratio,3),"tempo_refinement":"bounded_spectral_pulse_search_same_half_full_time_interpretation",
            "bpm_alternatives":[round(float(onset_rate*60/x),3) for x in ranked[:4]],
            "tempo_periodicity":round(float(corr[lag]/max(corr[0],1e-12)),4),
            "beat_offset_seconds":round(offset,5),"phrase_alignment":"inferred_32_beat_grid_not_verified_downbeats",
            "key_estimate":keys[0]["key"] if keys else None,"camelot_estimate":keys[0]["camelot"] if keys else None,
            "key_correlation":round(keys[0]["correlation"],4) if keys else None,
            "key_separation":round(keys[0]["correlation"]-keys[1]["correlation"],4) if len(keys)>1 else None,"key_alternatives":keys[:3],
            "rms_dbfs":round(20*math.log10(max(rms,1e-12)),3),"chroma":chroma.tolist(),
            "analysis_duration_seconds":len(y)/sr,"confidence_note":"Heuristic scores, not calibrated probabilities; percussion-heavy/atonal audio and half-time grids require listening."}


def probe(ffmpeg, path):
    ffprobe = str(Path(ffmpeg).with_name("ffprobe.exe" if os.name=="nt" else "ffprobe"))
    if not Path(ffprobe).exists():
        ffprobe = "ffprobe"
    p = subprocess.run([ffprobe,"-v","error","-show_entries","format=duration:stream=codec_type,sample_rate,channels","-of","json",str(path)],capture_output=True,text=True,check=True,timeout=30)
    return json.loads(p.stdout)


def reactive_envelope(y, sr, source_sha256, fps=60):
    """Measured continuous controls for a renderer; normalized by each band's P95."""
    import numpy as np
    from scipy import signal
    if len(y) < 1 or not np.all(np.isfinite(y)):
        raise ValueError("reactive envelope requires finite audio")
    starts = np.arange(0, len(y), sr / fps).astype(int)
    ends = np.r_[starts[1:], len(y)]
    rows = []
    scales = []
    bands = [None, (25, 150), (150, 2000), (2000, min(10000, sr * .45))]
    for limits in bands:
        band = y if limits is None else signal.sosfilt(signal.butter(4, limits, btype="bandpass", fs=sr, output="sos"), y)
        # Explicit destination protects the source from NumPy temporary reuse.
        power = np.empty_like(band)
        np.multiply(band, band, out=power)
        values = np.sqrt(np.add.reduceat(power, starts) / (ends - starts))
        scale = max(float(np.percentile(values, 95)), 1e-9)
        scales.append(scale)
        rows.append(np.minimum(values / scale, 1).round(5))
    return {"version": 1, "source_sha256": source_sha256, "duration_sec": len(y) / sr,
            "fps": fps, "channels": ["rms", "bass", "mid", "high"],
            "normalization": {"method": "per_band_95th_percentile_clipped", "scales_rms": scales},
            "band_hz": [None, [25, 150], [150, 2000], [2000, min(10000, sr * .45)]],
            "frames": np.stack(rows, axis=1).tolist()}


def canonical_audiomap(path, y, sr, source_hash):
    """Use the pinned music-to-video analyzer with our bounded decoded samples."""
    script = Path(__file__).parent / "vendor" / "analyze-beatgrid.py"
    expected = "acc14ffbbbcfb59fbe89a6886380d584df07a14205b1a299f424810bc85baed0"
    if sha(script) != expected or sr != 22050:
        raise RuntimeError("canonical beatgrid analyzer or sample rate changed")
    spec = importlib.util.spec_from_file_location("canonical_audio_beatgrid", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def bounded_decode(requested):
        if Path(requested) != path:
            raise ValueError("canonical analyzer requested an unexpected file")
        return y.copy(), sr, len(y)/sr
    module.load_audio = bounded_decode
    result = module.analyze(str(path), phrase_bars=4)
    result.update(source_sha256=source_hash, canonical_analyzer_sha256=expected,
                  bounded_decode_wrapper_sha256=sha(__file__),
                  beat_grid_note="Algorithmically inferred grid and downbeat phase, not manually verified.")
    return result


def execute(config):
    import numpy as np
    params = config["params"]
    root = Path(config["input_root"])
    out = Path(config["output_root"])
    manifest = params["manifest"]
    ffmpeg = config["ffmpeg"]
    # Recheck source and per-track hashes immediately before execution.
    verified, _, _ = validate({k:params[k] for k in PARAMETERS},root,config["job_type"])
    if verified != params:
        raise RuntimeError("audio input manifest changed")
    if config["job_type"] == "audio.harmonic_analyze":
        results=[]
        for track in manifest["tracks"]:
            path=staged(root,track["input_id"],EXTENSIONS)
            metadata=probe(ffmpeg,path)
            duration=float(metadata["format"]["duration"])
            args=[ffmpeg,"-nostdin","-v","error","-threads","2","-i",str(path),"-t",str(manifest.get("analysis_seconds",180)),"-vn","-ac","1","-ar","11025","-f","f32le","pipe:1"]
            audio=subprocess.run(args,capture_output=True,check=True,timeout=180).stdout
            y=np.frombuffer(audio,dtype="<f4")
            results.append({**track,"duration_seconds":duration,**analyze_signal(y,11025)})
            print(json.dumps({"analyzed":track.get("label",track["input_id"])}),flush=True)
        (out/params["output_name"]).write_text(json.dumps({"contract":"orion_harmonic_analysis_result_v1","tracks":results,"rights_verified":False},indent=2,allow_nan=False),encoding="utf-8")
        return
    target=manifest["target_bpm"]
    overlap=manifest.get("crossfade_beats",16)*60/target
    args=[ffmpeg,"-nostdin","-v","warning","-y","-threads","2","-filter_complex_threads","2"]
    filters=[];chapters=[];position=0.0
    for index,track in enumerate(manifest["tracks"]):
        path=staged(root,track["input_id"],EXTENSIONS)
        duration=float(probe(ffmpeg,path)["format"]["duration"])
        rate=target/track["source_bpm"]
        source_length=track["beats"]*60/track["source_bpm"]
        if track["cue_seconds"]+source_length>duration+.02:
            raise ValueError("mix segment exceeds actual source duration")
        args += ["-ss",str(track["cue_seconds"]),"-t",str(source_length),"-i",str(path)]
        length=track["beats"]*60/target
        filters.append(f"[{index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atempo={rate:.9f},atrim=duration={length:.9f},asetpts=PTS-STARTPTS,volume={track.get('gain_db',0):.3f}dB[a{index}]")
        chapters.append({"label":track.get("label",track["input_id"]),"mix_start_seconds":position,"source_start_seconds":track["cue_seconds"],"duration_seconds":length,"tempo_ratio":rate})
        position += length-(overlap if index<len(manifest["tracks"])-1 else 0)
    previous="a0"
    for index in range(1,len(manifest["tracks"])):
        filters.append(f"[{previous}][a{index}]acrossfade=d={overlap:.9f}:c1=qsin:c2=qsin[m{index}]")
        previous=f"m{index}"
    filters.append(f"[{previous}]afade=t=in:d=0.04,afade=t=out:st={position-2:.6f}:d=2,alimiter=limit=0.891251:level=false:latency=true[out]")
    args += ["-filter_complex",";".join(filters),"-map","[out]","-ar","48000","-c:a","pcm_s24le",str(out/params["output_name"])]
    subprocess.run(args,check=True,timeout=params["timeout_sec"]-10)
    result=probe(ffmpeg,out/params["output_name"])
    actual=float(result["format"]["duration"])
    if abs(actual-position)>.10:
        raise RuntimeError(f"mix duration mismatch: {actual} vs {position}")
    # Full decode validates the delivered WAV; EBU R128/true peak remain raw QC evidence.
    qc=subprocess.run([ffmpeg,"-nostdin","-v","info","-threads","2","-i",str(out/params["output_name"]),"-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,check=True,timeout=180)
    (out/"audio-qc.txt").write_text(qc.stderr,encoding="utf-8")
    decoded = subprocess.run([ffmpeg,"-nostdin","-v","error","-threads","2","-i",str(out/params["output_name"]),"-vn","-ac","1","-ar","22050","-f","f32le","pipe:1"],capture_output=True,check=True,timeout=180).stdout
    envelope = reactive_envelope(np.frombuffer(decoded,dtype="<f4"),22050,sha(out/params["output_name"]))
    (out/"audio-envelope-60fps.json").write_text(json.dumps(envelope,separators=(",",":"),allow_nan=False),encoding="utf-8")
    audiomap = canonical_audiomap(out/params["output_name"],np.frombuffer(decoded,dtype="<f4"),22050,sha(out/params["output_name"]))
    (out/"audiomap.json").write_text(json.dumps(audiomap,indent=2,allow_nan=False),encoding="utf-8")
    (out/"mix-receipt.json").write_text(json.dumps({"contract":"orion_dj_mix_result_v1","duration_seconds":actual,"expected_duration_seconds":position,"target_bpm":target,"crossfade_beats":manifest.get("crossfade_beats",16),"chapters":chapters,"full_decode_passed":True,"source_manifest_sha256":params["manifest_sha256"],"output_sha256":sha(out/params["output_name"]),"rights_verified":False},indent=2),encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",required=True)
    execute(json.loads(Path(parser.parse_args().config).read_text(encoding="utf-8")))
