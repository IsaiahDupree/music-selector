# Public recording research

`djlab.research` searches MusicBrainz recording metadata after an explicit user action. It sends the selected public SoundCloud track’s actual title and artist only. It never sends audio, local file paths, source hashes, private owner-production metadata or SoundCloud access tokens to the provider. The source hash and public URL stay in the local audit binding. A metadata candidate is never treated as audio identification, a verified match, or evidence of key, tempo, ownership or licensing.

The current MusicBrainz [search contract](https://musicbrainz.org/doc/MusicBrainz_API/Search) supports Lucene recording and artist fields, JSON and bounded result counts. The client escapes Lucene phrases separately from URL encoding and requests at most five records. The [rate policy](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting) calls for a meaningful application/contact User-Agent and at most one request per second. This client serializes requests in the library’s private state and waits at least a second after completion before another request. Other applications on the same network remain outside this client’s coordination.

## API and storage

- `research_track(track, state_dir, refresh=False)` returns a fresh cache or performs one bounded request. Explicit refresh bypasses the cache; it does not retry a failed request.
- `cached_research(track, state_dir)` reads a valid cache less than 24 hours old or returns `None`. It never requests the network or creates files.
- The server exposes authenticated `GET /api/research/{track_id}` as `{research: result|null}` and authenticated, same-origin CSRF-protected `POST` as `{research: result}`. POST accepts only `{}` or `{refresh: boolean}`.
- Caches live under the owner-only state directory outside Git, use atomic mode-0600 writes, and bind the exact source SHA, track ID, title, artist, duration, public source URL and encoded query. Raw provider bytes, retrieval time, HTTP status and SHA are retained. Parsing reconstructs candidates from these bytes.

Only HTTPS `soundcloud.com/<artist>/<track>` sources without credentials, query or fragment are eligible. The sole provider endpoint is `https://musicbrainz.org/ws/2/recording`; HTTPS certificate/SNI verification remains enabled. DNS results must be public addresses, and the connection uses the validated numeric address without a second lookup. Proxy environment variables are not consumed, redirects are not followed and there is no retry. One supervised lightweight child bounds DNS plus the HTTP exchange to ten seconds; it performs no DSP or media work. Response bytes are bounded to 256 KiB; a truncated response is recorded as an error, never parsed as successful candidates.

The result includes `status`, request URL, source/query binding, HTTP status, retrieval/expiry/cache age, raw response SHA/size, up to five candidates with returned recording ID/title/artist and duration difference, `audio_uploaded:false` and `verified_match:false`. HTTP and connection errors retain their actual status without a fabricated fallback. Constructed MusicBrainz/SoundCloud search links are labeled `verified_results:false`; they are not searched until a person follows them.

## Real validation, 2026-10-15

One authorized lookup of the actual imported public track **Preach — Leotrix** returned HTTP 200 and one candidate. The complete response was 1,709 bytes, SHA `38d86e6c7040cf0fc66f02911b82db6f134e233c432e1e4a1d6efc1e0491ba2e`. Its byte-exact public evidence capture is `djlab/tests/evidence/musicbrainz-preach-20261015.json`. No audio was uploaded and the candidate remains unverified. A subsequent call reused the unchanged private cache without making another request.

`python3 -m unittest djlab.tests.test_research -v` replays only this genuine response and the pinned real catalog. It checks exact provider/source bindings, owner-only storage, stale cache behavior, changed evidence rejection, private/non-public source rejection, real-title Lucene escaping and in-flight exclusion. It makes no external requests, uses no mocks and never substitutes invented provider results. The original successful lookup ran before the additional completion-based rate timestamp was added; source validation records that distinction. No live timeout, throttling, redirect or oversized-body response was forced against MusicBrainz.
