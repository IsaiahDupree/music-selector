# DJ Lab owner-local backend

The Python standard-library backend imports 91 actual Sour Sides source identities
and saved Orion harmonic-analysis records. It does not start the legacy Next.js
application, access Supabase, decode audio, invoke FFmpeg, or call an AI provider.
There is no fresh-analysis or render route until a verified typed Orion adapter
has been connected. `GET /api/capabilities` reports that distinction explicitly.

## Run and access

```sh
python3 -m djlab import --studio-root /absolute/path/to/sour-sides-studio \
  --state-dir '/owner/private/path/DJLab'
python3 -m djlab status --studio-root /absolute/path/to/sour-sides-studio \
  --state-dir '/owner/private/path/DJLab'
python3 -m djlab serve --studio-root /absolute/path/to/sour-sides-studio \
  --state-dir '/owner/private/path/DJLab' --port 5572
```

`serve` binds only `127.0.0.1` and prints the origin and private `launch.html`
path, never a credential. Open that file and submit its one-use form within ten
minutes. The server returns an HttpOnly, SameSite=Strict session cookie. The
private `auth-key` also supports command-line clients via Bearer authentication.
The state directory is owner-only and must be outside Git. Token values and the
launch page must never be copied into source, reports or a release.

`python3 -m djlab launch --state-dir ... --port 5572` prepares a fresh launch page
for an already running server. It does not start a browser or server. Session
cookies expire after eight hours and are invalidated by server restart. Public
routes are the static interface and minimal `GET /api/health` only. Static UI
access provides no library or media access without authentication.

All requests require the exact `Host: 127.0.0.1:<port>`. No CORS headers are
provided. Browser API requests must have the same origin; cookie-authenticated
writes also require `X-CSRF-Token`, obtained from authenticated `GET /api/session`.
The private launch form alone permits `Origin: null`, because local files use
that origin. Its nonce is bound to the exact origin, expires, and is consumed
once. Bearer clients may omit Origin; an explicitly foreign Origin is rejected.
Request JSON is capped at 65,536 bytes; duplicate fields, non-finite numbers,
ambiguous content lengths, and chunked request bodies are rejected. Eight
concurrent HTTP handlers and 15-second socket timeouts bound the local server.

## Evidence and file safety

The source fixture contains 19 byte-for-byte real metadata files, plus a pinned
capture manifest identifying source Git commit and file SHA-256 values. Startup
rehashes only those metadata files. It joins each staging plan to its actual
verified staging receipt, analysis request and analysis result by input ID and
SHA. The 19 selected refined analyses supersede estimates for those tracks while
retaining both real analysis records. Missing or changed evidence fails closed.

Audio is **not freshly rehashed on the Mac**. Its SHA is historical Orion staging
evidence. Playback requires an existing regular source file with the recorded
size, no symlink ancestors, and unchanged device/inode/size/mtime since import.
The DTO labels this `historical_sha_and_current_size`; this is not a claim that
present media bytes have been freshly cryptographically verified. A missing or
changed file is unavailable. Media routes accept only known immutable track IDs,
never caller file paths, and support one RFC-style byte range. Reads stream in
256 KiB chunks. No source audio or tags are modified.

Manual key, BPM, cues, loops, tags and review flags append to an owner-private,
fsynced JSONL journal. Each event binds source SHA, sequence and previous event
hash; damaged/truncated history fails closed. A process lock serializes readers
and writes. This is local metadata, not a second remote database. Edits are
last-writer-wins; `revision` reports the journal sequence. Passing `null` for key
or BPM restores the measured estimate. Original analysis fields remain intact.

## API contract

Every error is `{ "error": { "code": "...", "message": "..." } }`.
Validation errors use 400, missing auth 401, Host/Origin/CSRF rejection 403,
missing routes 404, unavailable/changed media 409, excessive request body 413,
unsupported content type 415, invalid range 416, and unavailable local I/O 503.

| Method/path | Input | Result |
|---|---|---|
| GET `/api/tracks` | `query`, `key`, `bpm_min`, `bpm_max` | `{tracks,total}` |
| GET `/api/tracks/{id}` | known track ID | `{track}` |
| PATCH `/api/tracks/{id}` | subset of `key,bpm,tags,cues,loops,reviewed` | `{track}` |
| GET `/api/playlists` | none | `{playlists}` |
| POST `/api/playlists` | `name,parent_id?,track_ids?` | `{playlist}`, 201 |
| PUT `/api/playlists/{id}` | `name?,parent_id?,track_ids?` | `{playlist}` |
| GET `/api/recommendations` | `track_id`, `limit` 1–91 | `{recommendations}` |
| POST `/api/plans` | `track_ids?,seed_track_id?,target_duration_seconds?,target_bpm?,crossfade_beats?` | `{plan}` |
| GET `/api/exports/{format}` | `playlist_id?` | downloadable JSON/CSV/M3U8/XSPF/rekordbox XML |
| GET/HEAD `/api/media/{id}` | optional one `Range` header; no query | actual authenticated source bytes |
| GET `/api/session` | session cookie | `{csrf_token}` |
| GET `/api/capabilities` | auth | supported and unavailable capability fields |

Track DTO fields are `id,input_id,sha256,title,artist,duration_seconds,source,
bpm,key,musical_key,bpm_source,key_source,analysis,analysis_history,raw_metadata,
tags,cues,loops,reviewed,revision,waveform,energy,media,provenance`. `source` has
`kind,url,rights_status`; rights remain `unknown`. Keys are Camelot strings;
manual entry also accepts musical notation through the shared normalizer. Tempo
is a number; `analysis` retains alternatives, correlation/separation,
periodicity, measured RMS, sampled duration, and its uncertainty note. These
scores are not calibrated probabilities. `waveform` and `energy` are null for
this v1 catalog, rather than invented from filenames or synthetic graphics.

Cues: `{name,seconds,slot,kind}`; `kind` is `hotcue` with distinct slot 0–7, or
`memory` with slot null. Loops: `{name,start_seconds,end_seconds}`. All positions
must lie within measured duration, and loop end must follow start. Up to 64
memory/hot cues total and 32 loops are allowed. Playlists use
`{id,name,parent_id,track_ids,updated_at}` with distinct known tracks and no parent
cycles. A folder is represented by a playlist with children, not another store.

Recommendations and plans are explainable metadata proposals, never proof of a
successful mashup, verified downbeat alignment, stem separation or rendered mix.
Export commands require an explicit new output filename and create it with 0600:

```sh
python3 -m djlab export --format rekordbox --playlist-id <actual-id> \
  --studio-root /absolute/path/to/sour-sides-studio \
  --state-dir '/owner/private/path/DJLab' --output /owner/private/path/set.xml
```

## Verification

`python3 -m unittest djlab.tests.test_backend -v` uses the 91 real saved metadata
records and real ephemeral loopback HTTP servers. Positive audio-range tests
read 257 bytes from actual recovered original audio in `DJLAB_REAL_STUDIO_ROOT`
(default the owner's Sour Sides studio). No fake audio, provider response or
skipped positive replaces missing media. The test fails if those real source
files are unavailable. No durable daemon or browser is started by the tests.

## Explicit public-track research

`POST /api/research/<known-track-id>` accepts only `{}` or a boolean `refresh`.
It uses the same bearer or same-origin cookie/CSRF controls as manual edits and
calls the MusicBrainz adapter for public SoundCloud title/artist metadata only.
Private owner productions and caller-supplied paths, URLs or queries are rejected.
The response is `{research: result}`; provider errors remain truthful results,
not empty successful matches. No audio is uploaded, and candidates are unverified.
`GET /api/research/<id>` reads only a fresh source-bound cache (or returns null)
and never triggers a provider request. The exact real Preach/Leotrix response is
retained as bounded integration evidence; no further lookup is needed for tests.

See [ANALYSIS-IMPORT.md](ANALYSIS-IMPORT.md) for the owner-only actual Orion v2
import contract. It does not enable fresh analysis or mutate manual cue edits.
