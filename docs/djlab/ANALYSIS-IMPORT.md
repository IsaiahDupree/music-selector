# Importing actual Orion audio analysis

DJLab has an owner-only offline importer for `audio.harmonic_analyze_v2`. It does
not submit jobs, start audio tools, analyze audio on the Mac, or accept an HTTP
file path/JSON upload. Fresh analysis remains unavailable in the browser until a
real typed RPC adapter is connected and verified separately.

The owner reviews the actual collected job evidence and supplies its exact
collection receipt SHA256 plus the three reviewed runner, legacy analyzer and
process guard source hashes. A receipt hashing itself does not establish trust.
The importer requires a successful actual Orion job and matching authenticated
status/artifact readbacks, exact admitted configuration and input manifest,
complete output inventory, runtime/dependency inventories, captured source bytes,
and fixed probe/decode command logs with actual PIDs. Retained stdout/stderr are
rehashes of real files. Decoded PCM is intentionally ephemeral: only its actual
byte count and SHA remain, and the importer never claims it retained those bytes.

```sh
python3 -m djlab import-analysis \
  --studio-root /Users/isaiahdupree/Documents/Software/sour-sides-studio \
  --state-dir "$HOME/Library/Application Support/SourSidesDJLab" \
  --evidence-dir /absolute/path/to/actual-collected-job \
  --collection-receipt-sha256 "$REVIEWED_COLLECTION_SHA" \
  --runner-sha256 "$REVIEWED_RUNNER_SHA" \
  --legacy-sha256 "$REVIEWED_LEGACY_ANALYZER_SHA" \
  --guard-sha256 "$REVIEWED_PROCESS_GUARD_SHA"
```

These variables stand for the reviewed actual hashes; there are no default or
example success hashes. No analysis is imported when any required file, join or
hash is absent. An existing job ID is idempotent only for the same reviewed
receipt and source pins. Private bundles are copied exclusively under
`analysis-imports/<actual-job-id>` in the owner-only state directory, replayed
there, then recorded in the hash-chained append-only journal. A failed copy is
retained for inspection without an admitting journal entry.

The exact collection layout is:

- `collection-receipt.json`: `job_id` and `files` rows with relative POSIX `path`,
  exact `bytes` and `sha256` for every other saved file.
- `job.json`, `status-api.json`, `artifacts-api.json`: actual raw durable job and
  successful API envelopes; no credentials.
- `audio-v2-config.json`, `input-manifest.json`: exact executed configuration and
  admitted input bytes.
- `out/*`: every actual job artifact, including its `manifest.json`, root analysis,
  execution receipt, package inventory, command log, per-track result/progress,
  and retained probe/version stdout and all command stderr.
- `source-evidence/harmonic_audio_v2.py`, `harmonic_audio.py`,
  `audio_process_guard.py`: exact runtime source bytes matching reviewed pins.

Only a known catalog input ID and exact source SHA can receive new analysis.
Original v1 records remain in `analysis_history`; subsequent actual prefix/full
v2 jobs append their own histories. The latest imported result supplies estimates,
with absent key or BPM remaining unknown. Manual key/BPM overrides, user cues,
loops and tags apply afterward and are preserved. Resetting an override uses the
latest imported analysis. Inferred `cue_suggestions` never become user cues.

`energy` is `{value, range:[0,100], method:'djlab_energy_v1', verified:false}`.
It is a documented signal-activity heuristic, not a calibrated perceptual energy
rating or a Mixed In Key equivalent. `waveform` keeps the real measured
`[time_seconds, minimum, maximum, rms]` frames in absolute mono PCM full-scale
units; it is not peak normalized. Coverage identifies the actual measured
interval and whether the full source was covered. Thirty-second sections are
analysis windows, not verified musical phrases or named song sections. Key,
beat/downbeat, cues and tempo remain estimates requiring manual review.

The track list summarizes frame/section counts and marks detail availability.
Authenticated `GET /api/tracks/<id>` returns the actual arrays. Capability flags
show only imported measured data; they do not imply fresh job submission.

Implementation is source-ready. A positive v2 import has not yet been verified;
the first real Orion prefix/full pair is required before claiming integration.
