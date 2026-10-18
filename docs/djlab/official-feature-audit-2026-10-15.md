# DJ Lab: official feature and interoperability audit

Observed 2026-10-15. This is an independent implementation comparison, not an
accuracy benchmark, affiliation, compatibility certification, or copy of Mixed
In Key's proprietary software. No purchase, paid provider, licensed download,
private API, model download, or music analysis was performed for this audit.

## Current public product

Mixed In Key's [features page](https://mixedinkey.com/features/) identifies the
11 family, Standard and Pro, and displays an October 8, 2026 update. Both editions
include key, BPM and energy analysis, automatic cue suggestions, tags and
playlists. Pro adds two-deck audition, suggested mashups/mix-outs, stems,
pitch changes, loops and filters. The page advertises up to eight cues.

The [public release notes](https://mixedinkey.com/release-notes/mixed-in-key-pro/)
contain Windows 11.1.0.846 and Mac 11.2.6.7421 entries dated September 2025, among
out-of-order older entries. These do **not** establish the newest downloadable
build on the audit date. “11” is the supported product-family observation.

The [Pro FAQ](https://mixedinkey.com/faq/mixed-in-key-pro/) lists macOS 12.7.6+
and Windows 10+, with separate stem requirements (Apple Silicon on Mac; 6 GB GPU
memory on Windows). Its platform-specific input format lists differ from the
broader features page. We do not infer universal format support.

## Functional comparison and implementation boundaries

| Capability | Official evidence | Existing owner evidence / DJ Lab approach | Limit |
|---|---|---|---|
| Key and tempo | [Features](https://mixedinkey.com/features/) | Import 91 source-hashed Orion results, 19 refined selections; add versioned segmented analysis | Pitch-profile correlation and tempo periodicity are heuristics, not calibrated probabilities or MIK-equivalent accuracy |
| Energy | [Energy scale](https://mixedinkey.com/harmonic-mixing-guide/sorting-playlists-by-energy-level/) | Implement and name an original loudness/pulse/brightness score with published formula | MIK uses 1–10; a similarly sized scale must not imply matching values or validation |
| Cues | [Cue export workflow](https://mixedinkey.com/workflows/export-cue-points-to-rekordbox/) | Up to eight audio-derived editable cue suggestions with provenance | No verified downbeat, phrase or musical-section claim; sparse/quiet files may produce fewer suggestions |
| Library and tags | [Tag workflow](https://mixedinkey.com/workflows/add-key-and-bpm-tags/) | Search real receipts; retain manual overrides separately; export sidecars first | Original media stays immutable by default; tag overwrite is distinct from playlist export |
| Suggested transitions | [Pro workflow](https://mixedinkey.com/workflows/what-is-mixed-in-key-11-pro/) | Explain key relationship, tempo ratio and energy change; retain source IDs and manual plan edits | Compatibility is a suggestion, not proof that phrasing, groove or vocals work together |
| Audition / transformations | [Pro workflow](https://mixedinkey.com/workflows/what-is-mixed-in-key-11-pro/) | Audition accessible media; future typed Orion pitch/tempo jobs after runtime verification | No browser-side heavy analysis, Mac FFmpeg, fabricated waveform, or silent local fallback |
| Stems | [Pro FAQ](https://mixedinkey.com/faq/mixed-in-key-pro/) | Inspect existing Orion tooling before proposing an isolated, model-pinned job | Not implemented or available merely because a package is installed |
| Recordable mix plan | [Pro workflow](https://mixedinkey.com/workflows/what-is-mixed-in-key-11-pro/) | Existing typed phrase/crossfade mix contract; export reproducible JSON plan | Existing mix renderer is not a general DAW; rights remain unverified |

## Interoperability contracts

**rekordbox XML.** The official
[XML format list](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf)
defines a `DJ_PLAYLISTS` document with `PRODUCT`, `COLLECTION`, `TRACK` and playlist
nodes. Track metadata includes `Location` as a file URI, `AverageBpm`, `Tonality`
and `Comments`. `TEMPO` carries time in seconds (`Inizio`), BPM, meter and beat
position. `POSITION_MARK` carries `Name`, `Type`, `Start`, optional `End`, and
`Num`; cue type is 0, loop type 4, and memory-cue number is -1. Export UTF-8 with
proper XML escaping and locale-independent numbers. Do not assert a complete
beatgrid from an opening window or uncertain phase. Test a generated file's
structural validity separately from import acceptance in an actual installed
rekordbox version.

Mixed In Key's [rekordbox workflow](https://mixedinkey.com/workflows/export-cue-points-to-rekordbox/)
requires rekordbox beatgrid/BPM analysis and collection XML interchange; tag
reload and cue import are separate operations. That workflow also documents a
WAV tagging/cue-export limitation, despite WAV analysis support. It does not
constitute a general public SDK for another application.

**Serato and Traktor.** The official
[Serato integration](https://mixedinkey.com/integration/serato-integration/?source=desktop)
and [Traktor workflow](https://mixedinkey.com/workflows/use-mixed-in-key-with-traktor/)
describe destination beatgrid preparation and explicit tag/cue export, including
existing-cue overwrite choices. We found no documented third-party write SDK in
these sources. DJ Lab must not advertise certified native cue export without
its own genuine format/import validation. Open playlists and metadata are a
separate, useful compatibility path.

**ID3.** The [ID3v2.4 frame specification](https://id3.org/id3v2.4.0-frames)
defines `TBPM` as an integer numeric string and `TKEY` as musical key notation.
Keep decimal BPM precision in the sidecar. Wheel labels are not standard `TKEY`
syntax; retain them in a separate user-defined/comment field if explicitly
selected. Suggested key and manually confirmed key must remain distinguishable.

**Open exports.** [XSPF](https://www.xspf.org/spec) provides ordered track lists
and URI locations with extension support. JSON/CSV preserve analysis coverage,
uncertainty, source hashes and edit provenance; M3U8 and XSPF preserve playback
order. These formats need no proprietary SDK. Do not put local absolute paths
or download URLs into a public artifact unless the user intends them to be
shared.

## Reuse facts observed in this workspace

The Sour Sides archive contains 66 downloaded SoundCloud tracks and 25 original
productions with analysis rows bound to input IDs and SHA-256. Nineteen selected
tracks have refined tempo receipts. The existing analysis reads at most the
opening 240 seconds, so its result cannot be presented as whole-track analysis.
Its confidence fields are diagnostic scores. PR5 (`45942c9636d6af2d5d97693eae47056b21d094c2`)
contains the original typed analyzer/mixer; it is not evidence of a currently
running analysis endpoint. The prior task lane's receipt says it stopped after
completion. The new analysis button remains unavailable until current
capability, resource admission, authenticated dispatch and real-job evidence
establish the v2 route.
