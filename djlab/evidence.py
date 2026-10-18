"""Import a pinned, real Sour Sides catalog without decoding or bulk hashing audio."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import unicodedata

CAPTURE = Path(__file__).parent / "tests/evidence"
MANIFEST_SHA = "a3c77c95a6e7a2196eed3dfd12b182fb6b2f69cf927b1f20d22a38a7d901c141"
SHA = re.compile(r"[a-f0-9]{64}")


class Invalid(ValueError):
    pass


def require(test, message):
    if not test:
        raise Invalid(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "Duplicate JSON field")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "Non-finite JSON value"))


def regular(path):
    """Reject symlink ancestors and anything except an ordinary file."""
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "Symlink paths are not admitted")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode), "Not a regular file")
    return info


def clean(value):
    return " ".join("".join(c for c in str(value or "") if unicodedata.category(c) not in {"Cc", "Cf"}).split())


def finite(value, low, high, label):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"{label} must be a finite number from {low} to {high}")
    return float(value)


def import_catalog(studio_root):
    root = Path(studio_root).expanduser().absolute()
    manifest_raw = (CAPTURE / "evidence-manifest.json").read_bytes()
    require(digest(manifest_raw) == MANIFEST_SHA, "Captured evidence manifest changed")
    manifest = parse(manifest_raw)
    data, pins = {}, {}
    for entry in manifest["files"]:
        path = root / entry["path"]
        require(regular(path).st_size == entry["bytes"], f"Evidence missing/size changed: {entry['path']}")
        raw = path.read_bytes()
        require(digest(raw) == entry["sha256"], f"Evidence hash changed: {entry['path']}")
        data[entry["path"]] = parse(raw)
        pins[entry["path"]] = entry["sha256"]
    plans, staged = {}, {}
    for group in ("originals", "soundcloud"):
        plan_name = f"reports/orion-{group}-stage-plan.json"
        receipt_name = f"reports/orion-{group}-staging-receipt.json"
        require(data[receipt_name]["status"] == "verified", "Staging receipt is not verified")
        for row in data[receipt_name]["inputs"]:
            require(row["input_id"] not in staged, "Duplicate staged input")
            staged[row["input_id"]] = row
        for row in data[plan_name]["tracks"]:
            input_id = row["input_id"]
            require(input_id not in plans and SHA.fullmatch(row["sha256"]), "Invalid source identity")
            require(staged[input_id]["sha256"] == row["sha256"] and
                    staged[input_id]["bytes"] == row["source_bytes"], "Stage plan/receipt mismatch")
            plans[input_id] = (row, group, plan_name, receipt_name)
    analysis, history = {}, {}
    result_names = sorted(k for k in data if k.startswith("mixes/analysis-results/") and "refined" not in k)
    result_names.append("mixes/analysis-results/analysis-selected-refined.json")
    for result_name in result_names:
        result = data[result_name]
        require(result["contract"] == "orion_harmonic_analysis_result_v1", "Unsupported analysis contract")
        request_name = ("mixes/analysis-selected.json" if "refined" in result_name
                        else result_name.replace("analysis-results/", ""))
        requests = {r["input_id"]: r for r in data[request_name]["tracks"]}
        require(set(requests) == {r["input_id"] for r in result["tracks"]}, "Analysis request/result set differs")
        for row in result["tracks"]:
            source = plans[row["input_id"]][0]
            require(row["sha256"] == source["sha256"] == requests[row["input_id"]]["sha256"],
                    "Analysis input SHA mismatch")
            finite(row["duration_seconds"], .001, 86400, "Duration")
            finite(row["bpm_estimate"], 1, 1000, "Tempo")
            history.setdefault(row["input_id"], []).append({"path": result_name, "sha256": pins[result_name], "record": row})
            analysis[row["input_id"]] = row
    require(len(plans) == len(analysis) == 91, "Expected the 91 real analyzed source tracks")
    tags_by_path = {r["path"]: r for r in data["reports/soundcloud-library-inventory.json"]["tracks"]}
    tracks, media = {}, {}
    for input_id, (source, group, plan_name, receipt_name) in plans.items():
        row = analysis[input_id]
        path = (Path(source["source_path"]) if group == "soundcloud" else root / source["source_relative"])
        raw_tags = tags_by_path.get(str(path), {}).get("tags", {})
        title = clean(raw_tags.get("TIT2", source["label"]).rstrip(" |"))
        artist = clean(raw_tags.get("TPE1", "Sour Sides" if group == "originals" else "").rstrip(" |"))
        urls = re.findall(r"https://soundcloud\.com/[^\s|]+", str(raw_tags.get("TXXX", "")))
        ident = "trk_" + source["sha256"][:24]
        require(ident not in tracks, "Duplicate/colliding track identity")
        tracks[ident] = {
            "id": ident, "input_id": input_id, "sha256": source["sha256"], "title": title,
            "artist": artist, "duration_seconds": row["duration_seconds"],
            "source": {"kind": "soundcloud" if group == "soundcloud" else "owner-production",
                       "url": urls[0] if urls else None, "rights_status": "unknown"},
            "bpm": row["bpm_estimate"], "key": row["camelot_estimate"], "musical_key": row["key_estimate"],
            "bpm_source": "analysis", "key_source": "analysis", "analysis": row,
            "analysis_history": history[input_id], "raw_metadata": raw_tags,
            "tags": [], "cues": [], "loops": [], "reviewed": False, "revision": 0,
            "waveform": None, "energy": None,
            "provenance": {"stage_plan": {"path": plan_name, "sha256": pins[plan_name]},
                           "staging_receipt": {"path": receipt_name, "sha256": pins[receipt_name]},
                           "source_commit": manifest["source_commit"], "audio_rehashed_on_mac": False},
        }
        media[ident] = {"path": str(path), "bytes": source["source_bytes"]}
    return {"contract": "djlab_catalog_v1", "source_root": str(root), "capture_manifest_sha256": MANIFEST_SHA,
            "evidence": pins, "tracks": tracks, "media": media}
