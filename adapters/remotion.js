/**
 * music-selector — Remotion adapter
 *
 * Usage in a Remotion composition:
 *
 *   const { selectMusic, selectMusicSync } = require('./adapters/remotion');
 *
 *   // Async (non-blocking — use in calculateMetadata or data-fetch):
 *   const track = await selectMusic({ mood: 'energetic', duration: 30, platform: 'tiktok' });
 *   // track.local_path, track.title, track.score, track.duration_sec
 *
 *   // Sync (blocks — only use in non-render contexts like CLI scripts):
 *   const track = selectMusicSync({ mood: 'energetic' });
 *
 *   // Use with staticFile():
 *   import { staticFile } from 'remotion';
 *   const src = staticFile(getStaticPath(track, 'public'));
 *
 * Environment:
 *   MUSIC_INDEX_PATH — override path to library.json (default: ../library.json)
 *   MUSIC_TRACKS_ROOT — root directory where local_path is resolved from
 *                       (default: directory containing library.json)
 */

'use strict';

const { execFile, execFileSync } = require('child_process');
const path = require('path');

const SUGGEST_PY = path.resolve(__dirname, '..', 'suggest.py');
const DEFAULT_LIB = path.resolve(__dirname, '..', 'library.json');

/**
 * Resolve the absolute path to a track's audio file.
 * local_path in library.json is relative to the library's directory.
 */
function resolveTrackPath(localPath) {
  if (!localPath) return null;
  const root = process.env.MUSIC_TRACKS_ROOT ||
    path.dirname(process.env.MUSIC_INDEX_PATH || DEFAULT_LIB);
  if (path.isAbsolute(localPath)) return localPath;
  return path.resolve(root, localPath);
}

/**
 * Build CLI args array from options object.
 */
function buildArgs(opts = {}) {
  const args = ['--json'];
  if (opts.mood)           args.push('--mood',         opts.mood);
  if (opts.energy != null) args.push('--energy',       String(opts.energy));
  if (opts.duration)       args.push('--duration',     String(opts.duration));
  if (opts.platform)       args.push('--platform',     opts.platform);
  if (opts.contentType)    args.push('--content-type', opts.contentType);
  if (opts.pacing)         args.push('--pacing',       opts.pacing);
  if (opts.transcript)     args.push('--transcript',   opts.transcript);
  if (opts.top != null)    args.push('--top',          String(opts.top || 1));
  if (opts.trending)       args.push('--trending');
  return args;
}

function _addResolvedPath(track) {
  return { ...track, resolved_path: resolveTrackPath(track.local_path) };
}

function _libPath() {
  return process.env.MUSIC_INDEX_PATH || DEFAULT_LIB;
}

/**
 * Async — select a music track without blocking the event loop.
 * Use this in calculateMetadata(), data-fetch callbacks, or any async context.
 *
 * @param {object} opts
 * @param {string}  [opts.mood]        energetic | calm | inspiring | dramatic | uplifting | happy | focused
 * @param {number}  [opts.energy]      0.0–1.0
 * @param {number}  [opts.duration]    video duration in seconds
 * @param {string}  [opts.platform]    instagram | tiktok | youtube | linkedin | twitter
 * @param {string}  [opts.contentType] viral_short | reels | tutorial | product_demo | dev_vlog | ...
 * @param {string}  [opts.pacing]      slow | medium | fast | very_fast
 * @param {string}  [opts.transcript]  raw transcript text
 * @param {boolean} [opts.trending]    only trending tracks
 * @returns {Promise<object|null>}
 */
function selectMusic(opts = {}) {
  return new Promise((resolve, reject) => {
    const args = buildArgs({ top: 1, ...opts });
    execFile('python3', [SUGGEST_PY, ...args], { env: process.env, encoding: 'utf8', timeout: 30000 },
      (err, stdout, stderr) => {
        if (err) {
          return reject(new Error(
            `music-selector: suggest.py failed (library: ${_libPath()}) — ${stderr || err.message}`
          ));
        }
        try {
          const results = JSON.parse(stdout);
          resolve(results.length ? _addResolvedPath(results[0]) : null);
        } catch (parseErr) {
          reject(new Error(`music-selector: failed to parse JSON output — ${parseErr.message}`));
        }
      }
    );
  });
}

/**
 * Synchronously select a music track. Blocks the event loop.
 * Only use in CLI scripts or non-render contexts (not inside Remotion compositions).
 *
 * @param {object} opts  — same options as selectMusic()
 * @returns {object|null}
 */
function selectMusicSync(opts = {}) {
  const args = buildArgs({ top: 1, ...opts });
  try {
    const raw = execFileSync('python3', [SUGGEST_PY, ...args], { env: process.env, encoding: 'utf8' });
    const results = JSON.parse(raw);
    return results.length ? _addResolvedPath(results[0]) : null;
  } catch (err) {
    throw new Error(
      `music-selector: suggest.py failed (library: ${_libPath()}) — ${err.message}`
    );
  }
}

/**
 * Async — select N tracks sorted by score desc.
 * @param {object} opts
 * @param {number} [n=5]
 * @returns {Promise<object[]>}
 */
function selectMusicTopN(opts = {}, n = 5) {
  return new Promise((resolve, reject) => {
    const args = buildArgs({ ...opts, top: n });
    execFile('python3', [SUGGEST_PY, ...args], { env: process.env, encoding: 'utf8', timeout: 30000 },
      (err, stdout, stderr) => {
        if (err) {
          return reject(new Error(
            `music-selector: suggest.py failed (library: ${_libPath()}) — ${stderr || err.message}`
          ));
        }
        try {
          const results = JSON.parse(stdout);
          resolve(results.map(_addResolvedPath));
        } catch (parseErr) {
          reject(new Error(`music-selector: failed to parse JSON output — ${parseErr.message}`));
        }
      }
    );
  });
}

/**
 * Returns a staticFile()-compatible relative path for a track.
 * Only works when tracks are inside the Remotion public/ directory.
 *
 * Example:
 *   getStaticPath(track, 'public')  →  'music/my-track.mp3'
 *   staticFile('music/my-track.mp3')
 *
 * @param {object} track     — track object with .resolved_path
 * @param {string} publicDir — path to the Remotion public/ dir (default 'public')
 * @returns {string}
 */
function getStaticPath(track, publicDir = 'public') {
  const abs = track && track.resolved_path;
  if (!abs) return track && track.local_path || '';
  const pubAbs = path.resolve(publicDir);
  // Use path.relative() — immune to off-by-one separator issues
  if (abs.startsWith(pubAbs + path.sep) || abs === pubAbs) {
    return path.relative(pubAbs, abs).replace(/\\/g, '/');
  }
  return track.local_path;
}

module.exports = { selectMusic, selectMusicSync, selectMusicTopN, getStaticPath, resolveTrackPath };
