'use strict';

// Metadata and receipts come from the local owner service. Audio is only played,
// sought and tempo-adjusted here; this interface does not perform DSP analysis.
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite = (n) => typeof n === 'number' && Number.isFinite(n);
const number = (n, digits = 1) => finite(n) ? n.toFixed(digits).replace(/\.0$/, '') : '—';
const time = (n) => finite(n) && n >= 0 ? `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2,'0')}` : '—';
const preciseTime = (n) => finite(n) ? `${time(Math.round(n*1000)/1000)}.${String(Math.round(n*1000)%1000).padStart(3,'0')}` : '—';
const state = {tracks: [], playlists: [], selected: null, playlist: null, capabilities: {}, csrf: null,
  loading: false, selectionVersion: 0, focus: 'a', noticeTimer: null, editBusy: false};
const decks = Object.fromEntries(['a','b'].map(id => [id,{audio:$(`audio-${id}`),track:null,loop:null,previewEnd:null}]));

function notify(message) {
  $('notice').textContent = message; $('notice').classList.add('visible');
  clearTimeout(state.noticeTimer); state.noticeTimer = setTimeout(() => $('notice').classList.remove('visible'), 5500);
}
function showError(error) {
  $('alert').textContent = error instanceof Error ? error.message : String(error);
  $('alert').hidden = false;
}
function clearError() { $('alert').hidden = true; $('alert').textContent = ''; }
async function api(path, options = {}) {
  const method = options.method || 'GET';
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined) headers.set('Content-Type','application/json');
  if (!['GET','HEAD'].includes(method)) {
    if (!state.csrf) throw new Error('This session cannot save changes. Reopen DJ Lab using its private launch link.');
    headers.set('X-CSRF-Token',state.csrf);
  }
  const response = await fetch(`/api${path}`,{...options,method,headers,credentials:'same-origin',cache:'no-store',
    body:options.body === undefined ? undefined : JSON.stringify(options.body)});
  const isJson = response.headers.get('content-type')?.includes('application/json');
  const result = isJson ? await response.json() : null;
  if (!response.ok) {
    const message = result?.error?.message || (typeof result?.error === 'string' ? result.error : null);
    throw new Error(message || (response.status === 401 || response.status === 403
      ? 'Session expired or access denied. Reopen the private DJ Lab launch link.' : `Request failed (${response.status}).`));
  }
  if (!isJson) throw new Error('The library returned an unexpected response.');
  return result;
}
const keyOf = t => typeof t?.key === 'string' ? t.key : (t?.key?.camelot || '');
function energyData(t) {
  const e=t.energy,bounds=e?.range,method=e?.method||e?.id;
  if(!e||!Array.isArray(bounds)||bounds.length!==2||!bounds.every(finite)||bounds[1]<=bounds[0]||typeof method!=='string'||!method||!finite(e.value)||e.value<bounds[0]||e.value>bounds[1])return null;
  return {value:e.value,low:bounds[0],high:bounds[1],method,normalized:(e.value-bounds[0])/(bounds[1]-bounds[0])};
}
const energyValue = t => energyData(t)?.normalized ?? null;
const keyGap = t => t.analysis_version===2 ? t.analysis?.key_confidence?.separation : t.analysis?.key_separation;
const reviewed = t => t.reviewed === true;
const uncertain = t => finite(keyGap(t)) && keyGap(t) < 0.08 && !reviewed(t);
const trackById = id => state.tracks.find(t => t.id === id);
const playlistById = id => state.playlists.find(p => p.id === id);
const feature = name => state.capabilities.features?.[name] ?? state.capabilities[name];
const available = name => { const f=feature(name); return f === true || f?.available === true || f?.supported === true; };
function sourceUrl(t) { try { const u=new URL(t.source?.url); return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null; } catch { return null; } }
function options(values, selected = '', first = null) {
  return (first !== null ? `<option value="">${esc(first)}</option>` : '') + values.map(v => {
    const value=typeof v === 'string' ? v : v.value; const label=typeof v === 'string' ? v : v.label;
    return `<option value="${esc(value)}"${value === selected ? ' selected' : ''}>${esc(label)}</option>`;
  }).join('');
}
function populateFilters() {
  const keys=Array.from({length:12},(_,i)=>[`${i+1}A`,`${i+1}B`]).flat();
  $('filter-key').innerHTML=options(keys,$('filter-key').value,'Every key');
  const sources=[...new Set(state.tracks.map(t=>t.source?.kind).filter(Boolean))].sort();
  $('filter-source').innerHTML=options(sources,$('filter-source').value,'All sources');
  $('filter-energy').disabled=!state.tracks.some(t=>finite(energyValue(t)));
  $('filter-energy').title=$('filter-energy').disabled ? 'No per-track energy measurements are available.' : 'Lower/middle/upper third of the declared method range; different methods are not interchangeable';
}
function capabilities() {
  const c=state.capabilities; const orion=c.orion || {}; const fresh=feature('fresh_analysis');
  const online=orion.available === true;
  $('orion-status').textContent=online ? 'Orion connected' : (orion.reason || fresh?.reason || 'Fresh analysis is unavailable in this session.');
  $('orion-status').classList.toggle('acid',online);
  const formats=feature('exports');
  if (Array.isArray(formats)) for (const opt of $('export-format').options) opt.disabled=!formats.includes(opt.value);
  const first=[...$('export-format').options].find(o=>!o.disabled);
  if (first && $('export-format').selectedOptions[0]?.disabled) $('export-format').value=first.value;
  $('export').disabled=!first; $('new-playlist').disabled=!available('manual_edits');
  $('open-plan').disabled=!available('plans');
}
async function refresh() {
  if (state.loading) return;
  state.loading=true; $('refresh').disabled=true; clearError();
  $('connection').textContent='Connecting'; $('connection').className='status-dot';
  try {
    const session=await api('/session'); state.csrf=session.csrf_token;
    const [library,collections,caps]=await Promise.all([api('/tracks'),api('/playlists'),api('/capabilities')]);
    if (!Array.isArray(library.tracks) || !Array.isArray(collections.playlists)) throw new Error('Library response has no track or playlist inventory.');
    state.tracks=library.tracks; state.playlists=collections.playlists; state.capabilities=caps;
    $('all-count').textContent=String(state.tracks.length); $('connection').textContent='Library connected'; $('connection').className='status-dot connected';
    populateFilters(); capabilities(); renderPlaylists(); renderTracks();
    if (state.selected) await selectTrack(state.selected.id);
  } catch (e) { $('connection').textContent='Unavailable'; $('connection').className='status-dot error'; showError(e);
    if (!state.tracks.length) { $('track-rows').innerHTML='<tr><td colspan="7" class="empty">The library could not be loaded.<br>Check the message above, then refresh.</td></tr>'; $('result-count').textContent='Library unavailable'; }
  } finally { state.loading=false; $('refresh').disabled=false; }
}
function playlistOrder() {
  const out=[]; const seen=new Set();
  function visit(parent, depth) {
    for (const p of state.playlists.filter(x=>(x.parent_id || null) === parent)) {
      if (seen.has(p.id)) continue; seen.add(p.id); out.push({...p,depth}); visit(p.id,depth+1);
    }
  }
  visit(null,0); for (const p of state.playlists) if (!seen.has(p.id)) out.push({...p,depth:0});
  return out;
}
function renderPlaylists() {
  $('all-tracks').classList.toggle('active',!state.playlist);
  const rows=playlistOrder();
  $('playlists').innerHTML=rows.length ? rows.map(p=>`<button class="nav-item depth-${Math.min(p.depth,4)}${state.playlist===p.id?' active':''}" data-playlist="${esc(p.id)}"><span>${p.depth?'↳':'▱'} &nbsp;${esc(p.name)}</span><span class="count">${(p.track_ids || []).length}</span></button>`).join('') : '<p class="small muted">Build a crate for your next set.</p>';
}
function visibleTracks() {
  const query=$('search').value.trim().toLocaleLowerCase(); const key=$('filter-key').value;
  const low=$('bpm-min').value === '' ? null : Number($('bpm-min').value); const high=$('bpm-max').value === '' ? null : Number($('bpm-max').value);
  const source=$('filter-source').value; const review=$('filter-review').value; const energy=$('filter-energy').value;
  const playlist=playlistById(state.playlist); const ids=playlist?.track_ids || [];
  let tracks=state.tracks.filter(t=>!playlist || ids.includes(t.id)).filter(t=>{
    if (query && ![t.title,t.artist,...(t.tags || [])].join(' ').toLocaleLowerCase().includes(query)) return false;
    if (key && keyOf(t)!==key) return false;
    if (low!==null && (!finite(t.bpm) || t.bpm<low)) return false;
    if (high!==null && (!finite(t.bpm) || t.bpm>high)) return false;
    if (source && t.source?.kind!==source) return false;
    if (review==='reviewed' && !reviewed(t) || review==='unreviewed' && reviewed(t) || review==='uncertain' && !uncertain(t)) return false;
    const e=energyValue(t);
    if (energy==='unknown' && e!==null || energy && energy!=='unknown' && e===null) return false;
    if (energy==='low' && e>=1/3 || energy==='mid' && (e<1/3 || e>=2/3) || energy==='high' && e<2/3) return false;
    return true;
  });
  const sort=$('sort').value;
  tracks.sort((a,b)=>{
    if (sort==='playlist' && playlist) return ids.indexOf(a.id)-ids.indexOf(b.id);
    if (sort==='bpm') return (a.bpm ?? Infinity)-(b.bpm ?? Infinity);
    if (sort==='duration') return (a.duration_seconds ?? Infinity)-(b.duration_seconds ?? Infinity);
    if (sort==='energy') return (energyData(a)?.method||'~').localeCompare(energyData(b)?.method||'~') || (energyValue(b) ?? -Infinity)-(energyValue(a) ?? -Infinity);
    if (sort==='key') return keyOf(a).localeCompare(keyOf(b),undefined,{numeric:true});
    return String(a[sort==='artist'?'artist':'title'] || '').localeCompare(String(b[sort==='artist'?'artist':'title'] || ''));
  });
  return tracks;
}
function renderTracks() {
  const playlist=playlistById(state.playlist); const tracks=visibleTracks();
  $('library-title').textContent=playlist?.name || 'All tracks';
  const dot=document.createElement('span'); dot.className='acid'; dot.textContent='.'; $('library-title').append(dot);
  $('library-subtitle').textContent=playlist ? 'Your saved order, with source analysis and manual edits kept separate.' : `${state.tracks.length} tracks · real source metadata · your corrections, your collection`;
  $('edit-playlist').hidden=!playlist;
  $('result-count').textContent=`${tracks.length} ${tracks.length===1?'track':'tracks'}${tracks.length!==state.tracks.length && !playlist ? ` of ${state.tracks.length}`:''}${playlist ? ` · ${time(tracks.reduce((sum,t)=>sum+(t.duration_seconds || 0),0))} total`:''}`;
  const n=[$('filter-key'),$('bpm-min'),$('bpm-max'),$('filter-energy'),$('filter-review'),$('filter-source')].filter(e=>e.value!=='').length;
  $('filter-count').textContent=n ? `(${n})` : '';
  if (!tracks.length) { $('track-rows').innerHTML='<tr><td colspan="7" class="empty">No tracks here yet.<br>Reset filters or add tracks to this playlist.</td></tr>'; return; }
  $('track-rows').innerHTML=tracks.map((t,i)=>{
    const e=energyValue(t); const playable=t.media?.available===true;
    return `<tr data-track="${esc(t.id)}" class="${state.selected?.id===t.id?'selected':''}"><td>${String(i+1).padStart(2,'0')}</td><td><button class="track-select" data-select="${esc(t.id)}"><span class="track-title">${esc(t.title || 'Untitled')}</span><span class="track-artist">${esc(t.artist || t.source?.kind || 'Unknown artist')}${reviewed(t)?' · reviewed':''}</span></button></td><td><span class="key-chip${keyOf(t)?'':' unknown'}">${esc(keyOf(t) || '—')}</span>${uncertain(t)?'<span class="estimate-dot" title="Close key alternatives; needs listening review">●</span>':''}</td><td class="bpm-value">${number(t.bpm)}${t.bpm_source==='manual'?'<span class="estimate-dot" title="Manual BPM">✎</span>': ''}</td><td class="duration-value">${time(t.duration_seconds)}</td><td class="energy-cell">${e===null?'<span class="energy-label">Not measured</span>':`<meter class="energy-meter" min="0" max="1" value="${Math.max(0,Math.min(1,e))}" aria-label="${esc(energyData(t).method)} energy estimate"></meter><span class="energy-label" title="${esc(energyData(t).method)} · range ${number(energyData(t).low)}–${number(energyData(t).high)}">${number(energyData(t).value)} / ${number(energyData(t).high)}</span>`}</td><td><div class="load-buttons"><button class="load-button" data-load="a" data-id="${esc(t.id)}" aria-label="Load ${esc(t.title)} into Deck A"${playable?'':' disabled'}>A</button><button class="load-button b" data-load="b" data-id="${esc(t.id)}" aria-label="Load ${esc(t.title)} into Deck B"${playable?'':' disabled'}>B</button></div></td></tr>`;
  }).join('');
}
function detailMarkup(t) {
  const a=t.analysis || {}; const url=sourceUrl(t); const alternatives=Array.isArray(a.key_alternatives) ? a.key_alternatives : [];
  const musical=t.musical_key || (t.key&&typeof t.key==='object'?t.key.name:'');
  const optionsHtml=options(Array.from({length:12},(_,i)=>[`${i+1}A`,`${i+1}B`]).flat(),keyOf(t),'Use analyzed key');
  const sourceProof={source:t.source,sha256:t.sha256,input_id:t.input_id,media:t.media,provenance:t.provenance,raw_metadata:t.raw_metadata,analysis:t.analysis,analysis_history:t.analysis_history};
  return `<div class="detail-header"><p class="eyebrow">TRACK INSPECTOR</p><span class="pill">${esc(t.source?.kind || 'LOCAL FILE')}</span><h2>${esc(t.title)}</h2><p class="small muted">${esc(t.artist || 'Artist not supplied')}</p><div class="load-buttons"><button class="load-button" data-load="a" data-id="${esc(t.id)}"${t.media?.available?'':' disabled'}>Load deck A</button><button class="load-button b" data-load="b" data-id="${esc(t.id)}"${t.media?.available?'':' disabled'}>Load deck B</button></div>${!t.media?.available?`<p class="small muted">${esc(t.media?.reason || 'Source audio is not available for playback.')}</p>`:''}</div>
    <div class="metric-grid"><div class="metric"><strong>${esc(keyOf(t) || '—')}</strong><small>${esc(musical || 'Key unavailable')} · ${t.key_source==='manual'?'manual':'estimate'}</small></div><div class="metric"><strong>${number(t.bpm)}</strong><small>BPM · ${esc(t.bpm_source || 'estimate')}</small></div><div class="metric"><strong>${time(t.duration_seconds)}</strong><small>Source duration</small></div></div>
    <section class="detail-section"><h3>What the analysis says</h3><p>${esc(a.confidence_note || 'Algorithmic estimates require listening review.')}</p>${finite(a.analysis_duration_seconds)?`<p>Analyzed ${time(a.analysis_duration_seconds)} of the source. Key separation ${number(a.key_separation,4)}; tempo periodicity ${number(a.tempo_periodicity,4)}. These are heuristic scores, not probabilities.</p>`:''}${alternatives.length?`<p>Key alternatives: ${alternatives.map(k=>`${esc(k.camelot || k.key || k.name || 'Unknown')} (${number(k.correlation ?? k.weighted_correlation_score,3)})`).join(' · ')}</p>`:''}${Array.isArray(a.bpm_alternatives)?`<p>Tempo alternatives: ${a.bpm_alternatives.filter(finite).map(b=>number(b)).join(' / ')} BPM.</p>`:''}${Array.isArray(a.tempo_alternatives)?`<p>Tempo alternatives: ${a.tempo_alternatives.filter(b=>finite(b?.bpm)).map(b=>`${number(b.bpm)} BPM (${esc(b.relationship||'alternative')})`).join(' · ')}. Half/double-time notation is not listening-verified.</p>`:''}${t.analysis_version===2?`<p>Measured coverage: ${time(t.coverage?.analyzed_seconds)} of ${time(t.duration_seconds)} · ${t.coverage?.full_track===true?'full source':'partial source'}. Weighted key separation ${number(keyGap(t),4)}; uncalibrated and not listening-verified.</p>`:''}<div id="waveform-area" class="no-wave detail-gap"><p>No measured per-track waveform available.</p></div><p class="detail-gap">${finite(a.rms_dbfs)?`Measured RMS: ${number(a.rms_dbfs,2)} dBFS. `:''}${energyValue(t)===null?'Perceptual energy has not been measured.':`Energy estimate: ${number(energyData(t).value)} on ${number(energyData(t).low)}–${number(energyData(t).high)} · ${esc(energyData(t).method)}. Not a calibrated perceptual rating.`}</p></section>
    <section class="detail-section"><h3>Check the key by ear</h3><p>A synthesized tone reference, not a piano recording or an automatic key verdict. Sound plays only when you press a note.</p><div class="tone-controls"><label class="field">Octave<select id="tone-octave"><option value="2">2 · low</option><option value="3">3</option><option value="4" selected>4 · middle</option><option value="5">5 · high</option></select></label><button id="play-key-chord" class="outline"${keyOf(t)?'':' disabled'}>Hear ${esc(keyOf(t) || 'key')} chord</button></div><div id="tone-keys" class="tone-keys" aria-label="Synthesized note references">${['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'].map((note,i)=>`<button class="tone-key${note.includes('♯')?' accidental':''}" data-tone="${i}" aria-label="Play synthesized ${note}">${note}</button>`).join('')}</div><p id="tone-status" class="small muted" role="status"></p></section>
    <section class="detail-section"><h3>Your corrections</h3><form id="edit-track"><div class="field-grid"><label class="field">Camelot key<select id="manual-key">${optionsHtml}</select></label><label class="field">BPM<input id="manual-bpm" type="number" min="20" max="300" step="any" value="${finite(t.bpm)?t.bpm:''}"></label><label class="field wide">Tags, separated by commas<input id="manual-tags" value="${esc((t.tags || []).join(', '))}" maxlength="500" placeholder="warm-up, heavy, late night"></label></div><label class="check-label"><input id="manual-reviewed" type="checkbox"${reviewed(t)?' checked':''}>I checked this track by listening</label><p>Manual key and tempo stay separate from the original analysis. Leave BPM empty or choose “Use analyzed key” to reset.</p><button class="accent full" type="submit"${available('manual_edits')?'':' disabled'}>Save corrections</button></form></section>
    <section class="detail-section"><div class="section-heading"><h3>Cue points</h3><button id="cue-current" class="quiet small">Use deck position</button></div><ul id="cue-list" class="row-list">${cueRows(t)}</ul>${suggestedCueMarkup(t)}<form id="add-cue" class="cue-form"><label class="field">Name<input name="name" maxlength="80" required placeholder="First drop"></label><label class="field">Seconds<input name="seconds" type="number" min="0" step="0.001" max="${t.duration_seconds || 0}" required value="0"></label><label class="field">Type<select name="kind"><option value="memory">Memory cue</option><option value="hotcue">Hot cue</option></select></label><label class="field">Hot slot<select name="slot"><option value="">None</option>${Array.from({length:8},(_,i)=>`<option value="${i}">${i+1}</option>`).join('')}</select></label><button class="outline wide" type="submit"${available('manual_edits')?'':' disabled'}>＋ Add cue</button></form></section>
    <section class="detail-section"><h3>Saved loops</h3><p>Browser-timed previews are not sample-accurate loops.</p><ul id="loop-list" class="row-list">${loopRows(t)}</ul><form id="add-loop" class="loop-form"><label class="field wide">Name<input name="name" maxlength="80" required placeholder="Eight-bar groove"></label><label class="field">Start, seconds<input name="start_seconds" type="number" min="0" step="0.001" required></label><label class="field">End, seconds<input name="end_seconds" type="number" min="0" step="0.001" required></label><button class="outline wide" type="submit"${available('manual_edits')?'':' disabled'}>＋ Save loop</button></form></section>
    <section class="detail-section"><h3>Add to a crate</h3><div class="field-grid"><select id="add-playlist-select" class="wide" aria-label="Choose a playlist">${options(playlistOrder().map(p=>({value:p.id,label:`${'↳ '.repeat(Math.min(p.depth,4))}${p.name}`})),'','Choose playlist')}</select><button id="add-to-playlist" class="outline wide"${state.playlists.length?'':' disabled'}>Add selected track</button></div></section>
    <section class="detail-section" aria-labelledby="research-heading"><h3 id="research-heading">Public recording research</h3><p>Look up this title and artist in MusicBrainz. No audio is sent. Candidates are unverified metadata leads; they do not establish key, tempo or licensing.</p><button id="research-lookup" class="outline full" disabled>Look up public metadata</button><p id="research-status" class="small muted detail-gap" role="status">Checking local cache…</p><div id="research-results"></div></section>
    <section class="detail-section"><h3>Source & provenance</h3>${url?`<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)} ↗</a>`:'<p>No original source URL recorded.</p>'}<p>Rights: ${esc(t.source?.rights_status || 'unknown')}. A downloaded file is not evidence of a license.</p><p>Key: ${esc(t.key_source || 'analysis')}. Playback verification: ${esc(t.media?.verification || 'unavailable')}.</p><details class="provenance"><summary>Inspect original metadata and evidence</summary><pre>${esc(JSON.stringify(sourceProof,null,2))}</pre></details></section>`;
}
function eligibleResearch(t) {
  try {const u=new URL(t.source?.url);return t.source?.kind==='soundcloud'&&u.protocol==='https:'&&u.hostname==='soundcloud.com'&&(!u.port||u.port==='443')&&!u.username&&!u.password&&!u.search&&!u.hash&&/^\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+\/?$/.test(u.pathname);}catch{return false;}
}
function researchLink(value) {
  try {const u=new URL(value);return u.protocol==='https:'&&['musicbrainz.org','soundcloud.com'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443')?u.href:null;}catch{return null;}
}
function bindResearch(t) {
  const button=$('research-lookup'),status=$('research-status'),results=$('research-results');
  if(!eligibleResearch(t)){status.textContent='External research is unavailable for private productions or sources without a public SoundCloud track URL. No metadata was sent.';return;}
  if(!available('research')){status.textContent='Metadata research is not available from this server.';return;}
  let serial=0,hasReceipt=false;
  async function request(explicit=false) {
    const own=++serial;button.disabled=true;status.textContent=explicit?'Looking up the public title and artist…':'Checking the local cache only…';
    try {
      const r=await api(`/research/${encodeURIComponent(t.id)}`,explicit?{method:'POST',body:hasReceipt?{refresh:true}:{}}:{});
      if(!button.isConnected||state.selected?.id!==t.id||serial!==own)return;
      const evidence=r.research;hasReceipt=Boolean(evidence);results.replaceChildren();
      if(!evidence){status.textContent='No fresh local result. Press the button to send this public title and artist to MusicBrainz.';return;}
      if(evidence.binding?.track_id!==t.id||evidence.binding?.source_sha256!==t.sha256||evidence.audio_uploaded!==false||evidence.verified_match!==false)throw new Error('Research evidence does not match this track.');
      const rows=Array.isArray(evidence.candidates)?evidence.candidates:[];
      status.textContent=evidence.status==='ok'?`${evidence.cached?'Cached':'Retrieved'} ${evidence.retrieved_at} · ${rows.length} unverified ${rows.length===1?'candidate':'candidates'}.`:`MusicBrainz: ${evidence.error?.message||evidence.status}. No fallback results were invented.`;
      results.innerHTML=rows.map(row=>{const url=researchLink(row.url);return `<article class="detail-gap"><h4>${esc(row.title)}</h4><p>${esc(row.artist||'Artist not returned')}${finite(row.duration_seconds)?` · ${time(row.duration_seconds)}`:''}</p><p class="small muted">${finite(row.duration_delta_seconds)?`Duration difference ${row.duration_delta_seconds>=0?'+':''}${number(row.duration_delta_seconds,3)} s · `:''}Unverified match</p>${url?`<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open recording metadata ↗</a>`:''}</article>`;}).join('')+
        (evidence.search_links||[]).map(link=>{const url=researchLink(link.url);return url?`<p class="detail-gap"><a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(link.label)} ↗</a><span class="small muted"> · constructed search link, not verified results</span></p>`:'';}).join('')+
        `<details class="provenance detail-gap"><summary>Query, source and response evidence</summary><pre>${esc(JSON.stringify(evidence,null,2))}</pre></details>`;
    }catch(error){if(button.isConnected&&serial===own)status.textContent=`Research unavailable: ${error.message}`;}
    finally {if(button.isConnected&&serial===own){button.disabled=false;button.textContent=hasReceipt?'Refresh MusicBrainz lookup':'Look up public metadata';}}
  }
  button.addEventListener('click',()=>request(true));request(false);
}
function cueRows(t) { return (t.cues || []).map((c,i)=>`<li><span class="row-label">${esc(c.name)}<br><span class="muted small">${preciseTime(c.seconds)} · ${esc(c.kind || 'memory')}${c.slot!==null && c.slot!==undefined?` ${c.slot+1}`:''}</span></span><button class="quiet" data-preview-cue="${i}"${t.media?.available?'':' disabled'}>Preview</button><button class="icon-button" data-delete-cue="${i}" aria-label="Delete cue ${esc(c.name)}">×</button></li>`).join('') || '<li class="muted">No saved cues.</li>'; }
function loopRows(t) { return (t.loops || []).map((l,i)=>`<li><span class="row-label">${esc(l.name)}<br><span class="muted small">${preciseTime(l.start_seconds)} → ${preciseTime(l.end_seconds)}</span></span><button class="quiet" data-preview-loop="${i}"${t.media?.available?'':' disabled'}>Preview</button><button class="icon-button" data-delete-loop="${i}" aria-label="Delete loop ${esc(l.name)}">×</button></li>`).join('') || '<li class="muted">No saved loops.</li>'; }
async function selectTrack(id) {
  const version=++state.selectionVersion; const known=trackById(id);
  if (known) {state.selected=known; renderTracks();}
  $('inspector').setAttribute('aria-busy','true');
  try {
    const result=await api(`/tracks/${encodeURIComponent(id)}`);
    if (version!==state.selectionVersion) return;
    const t=result.track; if (!t || t.id!==id) throw new Error('Track details do not match the selected track.');
    state.selected=t; replaceTrack(t); renderDetail(); renderTracks(); recommendations(id,version);
  } catch(e) { if (version===state.selectionVersion) showError(e); }
  finally { if (version===state.selectionVersion) $('inspector').removeAttribute('aria-busy'); }
}
function renderDetail() {
  const t=state.selected; if (!t) return;
  $('inspector').innerHTML=detailMarkup(t); bindDetail(t); bindResearch(t);
  drawMeasuredWaveform(t);

}
function suggestedCueMarkup(t) {
  const cues=t.cue_suggestions;
  if(t.analysis_version!==2||!Array.isArray(cues)||!cues.length)return '';
  return `<details class="provenance"><summary>${cues.length} inferred cue suggestions</summary><p>Unverified analysis markers, separate from your saved cues. Copy to the form, listen and edit before saving. Confidence is a heuristic, not a probability.</p><ul id="cue-suggestions" class="row-list">${cues.map((c,i)=>c.inferred===true&&finite(c.seconds)?`<li><span class="row-label">${esc(String(c.kind||'cue').replaceAll('_',' '))}<br><span class="muted small">${preciseTime(c.seconds)} · score ${number(c.confidence,3)}</span></span><button type="button" class="quiet" data-use-suggestion="${i}"${available('manual_edits')?'':' disabled'}>Use in form</button></li>`:'').join('')}</ul></details>`;
}
function measuredWaveformBins(t) {
  const w=t.waveform,coverage=t.coverage;
  if(t.analysis_version!==2||w?.measured!==true||!Array.isArray(w.frames)||!w.frames.length||w.frames.length>150000||!finite(t.duration_seconds)||t.duration_seconds<=0||!finite(coverage?.analyzed_seconds)||coverage.analyzed_seconds<=0||coverage.analyzed_seconds>t.duration_seconds+.05||JSON.stringify(w.channels)!==JSON.stringify(['time_seconds','minimum','maximum','rms'])||w.sample_rate!==11025||w.nominal_hz!==20||w.normalization!=='absolute_mono_downmix_float_pcm_full_scale_no_peak_normalization')return null;
  const bins=Array.from({length:600},()=>null);let previous=-1,clipped=false;
  for(const frame of w.frames){
    if(!Array.isArray(frame)||frame.length!==4||!frame.every(finite))return null;
    const [at,lo,hi,rms]=frame;
    if(at<=previous||at<0||at>coverage.analyzed_seconds||lo>hi||lo< -64||hi>64||rms<0||rms>Math.max(Math.abs(lo),Math.abs(hi))+.000002)return null;
    previous=at;clipped ||=lo< -1||hi>1;
    const x=Math.min(599,Math.floor(at/t.duration_seconds*600));const old=bins[x];bins[x]=old?{lo:Math.min(old.lo,lo),hi:Math.max(old.hi,hi)}:{lo,hi};
  }
  return {bins,clipped,frameCount:w.frames.length};
}
function drawMeasuredWaveform(t) {
  const measured=measuredWaveformBins(t);if(!measured)return;
  const canvas=document.createElement('canvas');canvas.className='actual-waveform';canvas.width=600;canvas.height=110;canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`Actual mono PCM min/max waveform; ${time(t.coverage.analyzed_seconds)} measured of ${time(t.duration_seconds)}. Unmeasured time is blank.`);
  const caption=document.createElement('p');caption.className='small muted';caption.textContent=`${measured.frameCount.toLocaleString()} measured frames · 20 Hz envelope from 11,025 Hz mono PCM. Timeline 0:00–${time(t.duration_seconds)}; measured 0:00–${time(t.coverage.analyzed_seconds)}. Absolute full-scale amplitude, no peak normalization.${measured.clipped?' Display clipped at ±1; original values remain in evidence.':''}`;
  $('waveform-area').replaceChildren(canvas,caption);$('waveform-area').className='';const ctx=canvas.getContext('2d');if(!ctx)return;
  ctx.fillStyle='#a6db71';measured.bins.forEach((bin,x)=>{if(!bin)return;const hi=Math.max(-1,Math.min(1,bin.hi)),lo=Math.max(-1,Math.min(1,bin.lo));ctx.fillRect(x,55-hi*50,1,Math.max(1,(hi-lo)*50));});
}
function replaceTrack(t) { const i=state.tracks.findIndex(x=>x.id===t.id); if(i>=0) state.tracks[i]=t; for(const id of ['a','b']) if(decks[id].track?.id===t.id){decks[id].track=t;updateDeckMetadata(id);} }
async function saveTrack(patch) {
  if (state.editBusy || !state.selected) return;
  if (!available('manual_edits')) return notify('Manual edits are unavailable in this session.');
  state.editBusy=true; const id=state.selected.id;
  $('inspector').setAttribute('aria-busy','true');
  try {
    const result=await api(`/tracks/${encodeURIComponent(id)}`,{method:'PATCH',body:patch});
    if (!result.track || result.track.id!==id) throw new Error('The saved track response was not valid. Refresh to check its state.');
    replaceTrack(result.track);
    if (state.selected?.id===id) {state.selected=result.track;renderDetail();recommendations(id,state.selectionVersion);}
    renderTracks();notify('Saved to your local library. Original analysis preserved.');
  } catch(e) {showError(e);} finally {state.editBusy=false;$('inspector').removeAttribute('aria-busy');}
}
function selectedDeck() {const preferred=decks[state.focus];if(preferred.track?.id===state.selected?.id)return state.focus;return ['a','b'].find(id=>decks[id].track?.id===state.selected?.id)||null;}
function bindDetail(t) {
  $('tone-keys').addEventListener('click',e=>{const b=e.target.closest('[data-tone]');if(b)referenceTone([Number(b.dataset.tone)],Number($('tone-octave').value));});
  $('play-key-chord').addEventListener('click',()=>{const c=KEY_REFERENCE[keyOf(t)];if(c)referenceTone([c[0],c[0]+(c[1]==='minor'?3:4),c[0]+7],Number($('tone-octave').value));});
  $('edit-track').addEventListener('submit',e=>{e.preventDefault();const value=$('manual-bpm').value,key=$('manual-key').value;const patch={tags:[...new Set($('manual-tags').value.split(',').map(x=>x.trim()).filter(Boolean))],reviewed:$('manual-reviewed').checked};if(key && key!==keyOf(t))patch.key=key;else if(!key && t.key_source==='manual')patch.key=null;if(value!=='' && Number(value)!==t.bpm)patch.bpm=Number(value);else if(value==='' && t.bpm_source==='manual')patch.bpm=null;saveTrack(patch);});
  $('cue-current').addEventListener('click',()=>{const id=selectedDeck();if(!id)return notify('Load this track into a deck first.');$('add-cue').elements.seconds.value=decks[id].audio.currentTime.toFixed(3);});
  $('cue-suggestions')?.addEventListener('click',e=>{const b=e.target.closest('[data-use-suggestion]');if(!b)return;const cue=t.cue_suggestions?.[Number(b.dataset.useSuggestion)];if(!cue||cue.inferred!==true||!finite(cue.seconds))return;const form=$('add-cue');form.elements.name.value=`Inferred ${String(cue.kind||'cue').replaceAll('_',' ')}`;form.elements.seconds.value=String(cue.seconds);form.elements.kind.value='memory';form.elements.slot.value='';form.elements.name.focus();notify('Suggestion copied into the editable cue form. Listen, adjust, then press Add cue to save.');});
  $('add-cue').addEventListener('submit',e=>{e.preventDefault();const f=new FormData(e.currentTarget);const cue={name:String(f.get('name')).trim(),seconds:Number(f.get('seconds')),kind:f.get('kind'),slot:f.get('slot')===''?null:Number(f.get('slot'))};if(!cue.name)return notify('Give this cue a name.');if(cue.kind==='memory')cue.slot=null;if(cue.kind==='hotcue'&&cue.slot===null)return notify('Choose a hot-cue slot from 1 to 8.');saveTrack({cues:[...(t.cues || []),cue]});});
  $('add-loop').addEventListener('submit',e=>{e.preventDefault();const f=new FormData(e.currentTarget);const loop={name:String(f.get('name')).trim(),start_seconds:Number(f.get('start_seconds')),end_seconds:Number(f.get('end_seconds'))};if(!loop.name)return notify('Give this loop a name.');if(loop.end_seconds<=loop.start_seconds || loop.end_seconds>t.duration_seconds)return notify('Loop end must follow its start and stay within the track.');saveTrack({loops:[...(t.loops || []),loop]});});
  $('cue-list').addEventListener('click',e=>{const del=e.target.closest('[data-delete-cue]');const preview=e.target.closest('[data-preview-cue]');if(del)saveTrack({cues:t.cues.filter((_,i)=>i!==Number(del.dataset.deleteCue))});if(preview)previewCue(t,t.cues[Number(preview.dataset.previewCue)]);});
  $('loop-list').addEventListener('click',e=>{const del=e.target.closest('[data-delete-loop]');const preview=e.target.closest('[data-preview-loop]');if(del)saveTrack({loops:t.loops.filter((_,i)=>i!==Number(del.dataset.deleteLoop))});if(preview)previewLoop(t,t.loops[Number(preview.dataset.previewLoop)]);});
  $('add-to-playlist').addEventListener('click',async()=>{const p=playlistById($('add-playlist-select').value);if(!p)return notify('Choose a playlist first.');try{await updatePlaylist(p.id,{track_ids:[...new Set([...(p.track_ids || []),t.id])]});notify(`Added to ${p.name}.`);}catch(e){showError(e);}});
}
async function recommendations(id,version) {
  $('recommend-context').textContent='Finding compatible tracks…';$('recommendations').replaceChildren();
  try {
    const data=await api(`/recommendations?track_id=${encodeURIComponent(id)}&limit=4`);
    if (version!==state.selectionVersion || state.selected?.id!==id) return;
    const rows=data.recommendations || [];
    $('recommend-context').textContent=rows.length ? `Next-track and mashup audition candidates for ${state.selected.title}. Preview the musical fit.` : 'No compatible candidates found for this track.';
    $('recommendations').innerHTML=rows.map(r=>{const t=r.track;if(!t)return '';return `<article class="recommendation-card"><div class="section-heading"><button data-select="${esc(t.id)}" class="track-select"><h3>${esc(t.title)}</h3></button><span class="match-score">${finite(r.score)?`Score ${number(r.score,2)}`:''}</span></div><p class="small muted">${esc(keyOf(t) || 'Unknown key')} · ${number(t.bpm)} BPM · ${esc(t.artist || '')}</p>${r.compatible===false?'<p class="small warning">Outside current mix limits · audition only</p>':''}${[.5,2].includes(r.tempo?.octave_factor)?`<p class="small muted">${r.tempo.octave_factor===.5?'Half':'Double'}-time notation assumed · not verified</p>`:''}<ul class="reasons">${(r.reasons || []).map(reason=>`<li>${esc(typeof reason==='string'?reason:reason.message || JSON.stringify(reason))}</li>`).join('')}</ul>${(r.warnings || []).length?`<details class="match-warnings"><summary>Match limitations</summary><ul class="reasons">${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></details>`:''}<div class="load-buttons"><button class="load-button" data-load="a" data-id="${esc(t.id)}"${t.media?.available?'':' disabled'}>Load A</button><button class="load-button b" data-load="b" data-id="${esc(t.id)}"${t.media?.available?'':' disabled'}>Load B</button><button class="load-button" data-compare="${esc(t.id)}"${t.media?.available && state.selected?.media?.available?'':' disabled'}>Compare A/B</button></div></article>`;}).join('');
  } catch(e) { if(version===state.selectionVersion)$('recommend-context').textContent=`Recommendations unavailable: ${e.message}`; }
}
function modal(title,markup) { $('modal-title').textContent=title;$('modal-content').innerHTML=markup;if(!$('modal').open)$('modal').showModal(); }
function modalError(e) {let p=$('modal-error');if(!p){p=document.createElement('p');p.id='modal-error';p.className='modal-error';p.setAttribute('role','alert');$('modal-content').append(p);}p.textContent=e.message || String(e);}
async function updatePlaylist(id,patch) {
  const result=await api(`/playlists/${encodeURIComponent(id)}`,{method:'PUT',body:patch});
  const p=result.playlist;if(!p)throw new Error('Playlist save returned no playlist. Refresh to check its state.');
  const i=state.playlists.findIndex(x=>x.id===p.id);if(i>=0)state.playlists[i]=p;else state.playlists.push(p);
  renderPlaylists();renderTracks();return p;
}
function createPlaylist() {
  modal('Start a new crate',`<p class="muted">Keep tracks in a playlist, or nest it under another collection.</p><form id="playlist-form"><div class="field-grid"><label class="field wide">Name<input id="playlist-name" maxlength="100" required placeholder="Late-night voltage"></label><label class="field wide">Parent collection<select id="playlist-parent">${options(playlistOrder().map(p=>({value:p.id,label:`${'↳ '.repeat(Math.min(p.depth,4))}${p.name}`})),state.playlist || '','Top level')}</select></label></div><div class="actions"><button class="accent" type="submit">Create playlist</button></div></form>`);
  $('playlist-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;try{const r=await api('/playlists',{method:'POST',body:{name:$('playlist-name').value.trim(),parent_id:$('playlist-parent').value || null}});if(!r.playlist)throw new Error('No playlist returned. Refresh before trying again.');state.playlists.push(r.playlist);state.playlist=r.playlist.id;renderPlaylists();renderTracks();if(state.selected)renderDetail();$('modal').close();notify('Playlist created. Add tracks from the inspector.');}catch(e){modalError(e);button.disabled=false;}});
}
function editPlaylist() {
  const p=playlistById(state.playlist);if(!p)return;let ids=[...(p.track_ids || [])];
  modal('Edit collection',`<form id="playlist-edit-form"><div class="field-grid"><label class="field wide">Name<input id="playlist-edit-name" maxlength="100" required value="${esc(p.name)}"></label><label class="field wide">Parent<select id="playlist-edit-parent">${options(playlistOrder().filter(x=>x.id!==p.id).map(x=>({value:x.id,label:x.name})),p.parent_id || '','Top level')}</select></label></div><p class="muted small">Reorder tracks here. Removing a track from this playlist leaves its source file and library entry intact.</p><div id="playlist-track-order"></div><div class="actions"><button class="accent" type="submit">Save collection</button></div></form>`);
  function renderOrder(){ $('playlist-track-order').innerHTML=ids.map((id,i)=>`<div class="playlist-track"><span>${i+1}. ${esc(trackById(id)?.title || id)}</span><button type="button" class="quiet" data-move="${i}" data-direction="-1" aria-label="Move track up"${i===0?' disabled':''}>↑</button><button type="button" class="quiet" data-move="${i}" data-direction="1" aria-label="Move track down"${i===ids.length-1?' disabled':''}>↓</button><button type="button" class="icon-button" data-remove="${i}" aria-label="Remove track from playlist">×</button></div>`).join('') || '<p class="muted small">No tracks in this playlist yet.</p>'; }
  renderOrder();$('playlist-track-order').addEventListener('click',e=>{const move=e.target.closest('[data-move]');const remove=e.target.closest('[data-remove]');if(move){const i=Number(move.dataset.move),j=i+Number(move.dataset.direction);if(j>=0&&j<ids.length)[ids[i],ids[j]]=[ids[j],ids[i]];}if(remove)ids.splice(Number(remove.dataset.remove),1);renderOrder();});
  $('playlist-edit-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button[type=submit]');button.disabled=true;try{await updatePlaylist(p.id,{name:$('playlist-edit-name').value.trim(),parent_id:$('playlist-edit-parent').value || null,track_ids:ids});$('modal').close();notify('Playlist order saved.');}catch(e){modalError(e);button.disabled=false;}});
}
function downloadBlob(blob,filename) {const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
async function exportLibrary() {
  $('export').disabled=true;try{const format=$('export-format').value;const query=state.playlist?`?playlist_id=${encodeURIComponent(state.playlist)}`:'';const response=await fetch(`/api/exports/${format}${query}`,{credentials:'same-origin',cache:'no-store'});if(!response.ok){const r=await response.json().catch(()=>null);throw new Error(r?.error?.message || `Export failed (${response.status}).`);}const blob=await response.blob();const extension=format==='rekordbox'?'xml':format;downloadBlob(blob,`sour-sides-${state.playlist?'playlist':'library'}.${extension}`);notify('Export downloaded. Source audio was not modified.');}catch(e){showError(e);}finally{capabilities();}
}
function openPlan() {
  const p=playlistById(state.playlist);const canExecute=feature('plans')?.execution===true;
  modal('Shape the next mix',`<p class="muted">${p?`Use the saved order in ${esc(p.name)}.`:'Start from your selected track and ask the library for compatible choices.'} A plan is metadata; it does not render or publish audio.</p><form id="plan-form"><div class="field-grid"><label class="field">Target length, minutes<input id="plan-duration" type="number" min="0.5" max="30" step="0.5" value="12" required></label><label class="field">Target BPM<input id="plan-bpm" type="number" min="60" max="190" step="any" value="${finite(state.selected?.bpm)?Math.max(60,Math.min(190,state.selected.bpm)):140}" required></label></div><p class="small muted">${canExecute?'Use the returned plan and its server-side execution requirements.':'Audio rendering is not available from this interface. The plan can be exported for review.'}</p><div class="actions"><button class="accent" type="submit">Build plan</button></div></form><div id="plan-output"></div>`);
  $('plan-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;const body={target_duration_seconds:Math.round(Number($('plan-duration').value)*60),target_bpm:Number($('plan-bpm').value)};if(p)body.track_ids=p.track_ids || [];else if(state.selected)body.seed_track_id=state.selected.id;else body.track_ids=visibleTracks().map(t=>t.id);try{const r=await api('/plans',{method:'POST',body});const plan=r.plan;if(!plan)throw new Error('No plan was returned.');$('plan-output').className='plan-output';$('plan-output').innerHTML=`<h3>${plan.target_duration_met===false?'Plan falls short of the target':'Preparation plan for review'}</h3><p class="small muted">${esc(plan.id || '')}</p><p>Estimated audio: <strong>${time(plan.estimated_duration_seconds)}</strong>${finite(plan.requested_duration_seconds)?` · requested <strong>${time(plan.requested_duration_seconds)}</strong>`:''}. ${plan.target_duration_met===false?'Add more suitable source material to fill this set.':'Timing remains a metadata estimate.'}</p>${(plan.warnings || []).length?`<ul class="reasons">${plan.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`:''}<ol class="plan-list">${(plan.tracks || []).map(row=>{const t=typeof row==='string'?trackById(row):(row.track || trackById(row.track_id || row.id) || row);return `<li>${esc(t?.title || row.track_id || row.id || row)}<small>${esc(keyOf(t) || '')} ${finite(t?.bpm)?`· ${number(t.bpm)} BPM`:''}</small></li>`;}).join('')}</ol><details class="provenance"><summary>Transitions and exact plan metadata</summary><pre>${esc(JSON.stringify(plan,null,2))}</pre></details><button id="download-plan" class="outline detail-gap">Download plan JSON</button>`;$('download-plan').addEventListener('click',()=>downloadBlob(new Blob([JSON.stringify(plan,null,2)+'\n'],{type:'application/json'}),'sour-sides-mix-plan.json'));}catch(e){modalError(e);}finally{button.disabled=false;}});
}

const KEY_REFERENCE={'1A':[8,'minor'],'2A':[3,'minor'],'3A':[10,'minor'],'4A':[5,'minor'],'5A':[0,'minor'],'6A':[7,'minor'],'7A':[2,'minor'],'8A':[9,'minor'],'9A':[4,'minor'],'10A':[11,'minor'],'11A':[6,'minor'],'12A':[1,'minor'],'1B':[11,'major'],'2B':[6,'major'],'3B':[1,'major'],'4B':[8,'major'],'5B':[3,'major'],'6B':[10,'major'],'7B':[5,'major'],'8B':[0,'major'],'9B':[7,'major'],'10B':[2,'major'],'11B':[9,'major'],'12B':[4,'major']};
let toneContext=null,toneVoices=[];
async function referenceTone(notes,octave) {
  try {
    const AudioContext=window.AudioContext || window.webkitAudioContext;
    if(!AudioContext)throw new Error('Synthesized reference tones are not supported in this browser.');
    if(!toneContext)toneContext=new AudioContext();
    await toneContext.resume();
    for(const voice of toneVoices){try{voice.stop();}catch{}}toneVoices=[];
    const now=toneContext.currentTime;
    for(const note of notes.slice(0,3)){
      const oscillator=toneContext.createOscillator(),gain=toneContext.createGain();
      oscillator.type='sine';oscillator.frequency.value=440*2**(((octave+1)*12+note-69)/12);
      gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(.045,now+.02);gain.gain.setValueAtTime(.045,now+.55);gain.gain.linearRampToValueAtTime(0,now+.85);
      oscillator.connect(gain);gain.connect(toneContext.destination);oscillator.start(now);oscillator.stop(now+.9);
      oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();toneVoices=toneVoices.filter(v=>v!==oscillator);};toneVoices.push(oscillator);
    }
    if($('tone-status'))$('tone-status').textContent='Playing a short synthesized reference. Compare by ear with the track.';
  }catch(e){showError(e);}
}

function focusDeck(id) {state.focus=id;for(const name of ['a','b']){$(`deck-${name}`).classList.toggle('active',id===name);document.querySelector(`.deck-focus[data-deck="${name}"]`).setAttribute('aria-pressed',String(id===name));}}
function updateDeckMetadata(id) {
  const d=decks[id],t=d.track;if(!t)return;
  $(`deck-${id}-title`).textContent=t.title;
  $(`deck-${id}-meta`).textContent=`${keyOf(t) || 'Unknown key'} · ${number(t.bpm)} BPM · ${t.artist || 'Local audio'}`;
  $(`cue-${id}`).innerHTML='<option value="">Cues</option>'+(t.cues || []).map((c,i)=>`<option value="${i}">${esc(c.name)} · ${time(c.seconds)}</option>`).join('');
  $(`cue-${id}`).disabled=!(t.cues || []).length;$(`loop-${id}`).disabled=!(t.loops || []).length;
}
async function loadDeck(id,track) {
  if (!track || track.media?.available!==true) {notify(track?.media?.reason || 'Source audio is unavailable.');return false;}
  const d=decks[id];d.audio.pause();d.track=track;d.loop=null;d.previewEnd=null;
  d.audio.src=`/api/media/${encodeURIComponent(track.id)}`;d.audio.playbackRate=1;d.audio.preservesPitch=true;if('webkitPreservesPitch' in d.audio)d.audio.webkitPreservesPitch=true;
  $(`rate-${id}`).value='1';$(`rate-${id}-value`).textContent='1.000×';$(`loop-${id}`).textContent='Loop off';$(`loop-${id}`).setAttribute('aria-pressed','false');
  for(const name of ['play','rate','reset-rate'])$(`${name}-${id}`).disabled=false;
  $(`seek-${id}`).disabled=true;$(`time-${id}`).textContent=`0:00 / ${time(track.duration_seconds)}`;
  updateDeckMetadata(id);updateVolumes();focusDeck(id);$('sync-tempo').disabled=!(decks.a.track&&decks.b.track);d.audio.load();
  return true;
}
function metadataReady(audio) {
  if(audio.readyState>=1)return Promise.resolve();
  return new Promise((resolve,reject)=>{const timer=setTimeout(()=>finish(new Error('Audio metadata did not load. Check the source mount.')),15000);function finish(error){clearTimeout(timer);audio.removeEventListener('loadedmetadata',ok);audio.removeEventListener('error',bad);error?reject(error):resolve();}const ok=()=>finish();const bad=()=>finish(new Error('This source could not be played.'));audio.addEventListener('loadedmetadata',ok,{once:true});audio.addEventListener('error',bad,{once:true});});
}
async function play(id) {const d=decks[id];if(!d.track)return;try{if(!d.audio.paused){d.audio.pause();return;}await d.audio.play();focusDeck(id);}catch(e){showError(new Error(`Deck ${id.toUpperCase()}: ${e.message}`));}}
function updateVolumes(){const x=(Number($('crossfader').value)+1)/2;const m=Number($('master').value)*Math.SQRT1_2;decks.a.audio.volume=Math.cos(x*Math.PI/2)*m;decks.b.audio.volume=Math.sin(x*Math.PI/2)*m;}
function tempoMatch(target,source) {
  if(!finite(target)||!finite(source)||target<=0||source<=0)return null;
  const choices=[1,.5,2].map(factor=>({factor,rate:target/(source*factor)}));
  choices.sort((a,b)=>Math.abs(a.rate-1)-Math.abs(b.rate-1));
  return {...choices[0],within:choices[0].rate>=.9&&choices[0].rate<=1.1};
}
function matchDeckTempo() {
  const a=decks.a,b=decks.b;
  const match=tempoMatch(a.track?.bpm*a.audio.playbackRate,b.track?.bpm);
  if(!match)return notify('Both tracks need a BPM value to match tempo.');
  if(!match.within)return notify('Outside the ±10% mix tempo limit, even allowing half/double notation. Audition independently; no rate was changed.');
  setRate('b',match.rate);
  const assumption=match.factor===1?'Original BPM notation':`${match.factor===.5?'Half':'Double'}-time notation assumed, not verified`;
  $(`deck-b-meta`).textContent+=` · ${assumption}`;
  $('rate-b-value').title=`${number(b.track.bpm*match.factor*match.rate,2)} BPM using ${assumption.toLowerCase()}`;
  notify(`Deck B set to ${match.rate.toFixed(3)}×. ${assumption}. Align beats and phrases by ear; matching does not start playback.`);
}
function setRate(id,value){const d=decks[id];if(!d.track||!finite(value)||value<.5||value>1.5)return;updateDeckMetadata(id);d.audio.playbackRate=value;$(`rate-${id}`).value=String(value);$(`rate-${id}-value`).textContent=`${value.toFixed(3)}×`;$(`rate-${id}-value`).title=finite(d.track.bpm)?`${number(d.track.bpm*value,2)} effective BPM`:'';}
async function previewCue(t,cue){const id=selectedDeck() || state.focus;try{if(decks[id].track?.id!==t.id && !await loadDeck(id,t))return;const d=decks[id];await metadataReady(d.audio);if(d.track?.id!==t.id)return;d.loop=null;d.previewEnd=Math.min(cue.seconds+8,t.duration_seconds);d.audio.currentTime=cue.seconds;$(`loop-${id}`).textContent='Loop off';$(`loop-${id}`).setAttribute('aria-pressed','false');await d.audio.play();notify(`Previewing ${cue.name} on deck ${id.toUpperCase()} for up to 8 seconds.`);}catch(e){showError(e);}}
async function previewLoop(t,loop,preferred=null){const id=preferred || selectedDeck() || state.focus;try{if(decks[id].track?.id!==t.id && !await loadDeck(id,t))return;const d=decks[id];await metadataReady(d.audio);if(d.track?.id!==t.id)return;d.loop=loop;d.previewEnd=null;d.audio.currentTime=loop.start_seconds;$(`loop-${id}`).textContent='Loop on';$(`loop-${id}`).setAttribute('aria-pressed','true');await d.audio.play();notify(`Looping ${loop.name} on deck ${id.toUpperCase()}. Turn Loop off to continue.`);}catch(e){showError(e);}}
function bindDeck(id) {
  const d=decks[id];$(`play-${id}`).addEventListener('click',()=>{d.previewEnd=null;play(id);});
  $(`rate-${id}`).addEventListener('input',e=>setRate(id,Number(e.target.value)));$(`reset-rate-${id}`).addEventListener('click',()=>setRate(id,1));
  $(`seek-${id}`).addEventListener('input',e=>{d.previewEnd=null;d.audio.currentTime=Number(e.target.value);});
  $(`cue-${id}`).addEventListener('change',async e=>{if(e.target.value==='')return;const cue=d.track?.cues[Number(e.target.value)];if(cue)try{await metadataReady(d.audio);d.previewEnd=null;d.audio.currentTime=cue.seconds;}catch(error){showError(error);}});
  $(`loop-${id}`).addEventListener('click',()=>{if(d.loop){d.loop=null;$(`loop-${id}`).textContent='Loop off';$(`loop-${id}`).setAttribute('aria-pressed','false');}else if(d.track?.loops?.length){const loop=d.track.loops[0];previewLoop(d.track,loop,id);}});
  d.audio.addEventListener('loadedmetadata',()=>{const duration=d.audio.duration;if(finite(duration)){$(`seek-${id}`).max=String(duration);$(`seek-${id}`).disabled=false;$(`time-${id}`).textContent=`${time(d.audio.currentTime)} / ${time(duration)}`;}});
  d.audio.addEventListener('timeupdate',()=>{if(d.loop&&d.audio.currentTime>=d.loop.end_seconds)d.audio.currentTime=d.loop.start_seconds;if(d.previewEnd!==null&&d.audio.currentTime>=d.previewEnd){d.audio.pause();d.previewEnd=null;}$(`seek-${id}`).value=String(d.audio.currentTime);$(`time-${id}`).textContent=`${time(d.audio.currentTime)} / ${time(d.audio.duration)}`;});
  d.audio.addEventListener('play',()=>{$(`play-${id}`).textContent='Ⅱ';$(`play-${id}`).setAttribute('aria-label',`Pause Deck ${id.toUpperCase()}`);});
  d.audio.addEventListener('pause',()=>{$(`play-${id}`).textContent='▶';$(`play-${id}`).setAttribute('aria-label',`Play Deck ${id.toUpperCase()}`);});
  d.audio.addEventListener('error',()=>{if(d.track)showError(new Error(`Deck ${id.toUpperCase()} could not load ${d.track.title}. The file may be unavailable or this browser may not support its format.`));});
}
function bind() {
  $('refresh').addEventListener('click',refresh);
  for(const id of ['search','bpm-min','bpm-max'])$(id).addEventListener('input',renderTracks);
  for(const id of ['filter-key','filter-energy','filter-review','filter-source','sort'])$(id).addEventListener('change',renderTracks);
  $('filters-toggle').addEventListener('click',()=>{$('filters').hidden=!$('filters').hidden;$('filters-toggle').setAttribute('aria-expanded',String(!$('filters').hidden));});
  $('clear-filters').addEventListener('click',()=>{for(const id of ['search','bpm-min','bpm-max','filter-key','filter-energy','filter-review','filter-source'])$(id).value='';renderTracks();});
  $('all-tracks').addEventListener('click',()=>{state.playlist=null;renderPlaylists();renderTracks();});
  $('playlists').addEventListener('click',e=>{const b=e.target.closest('[data-playlist]');if(b){state.playlist=b.dataset.playlist;$('sort').value='playlist';renderPlaylists();renderTracks();}});
  document.body.addEventListener('click',e=>{const load=e.target.closest('[data-load]');const select=e.target.closest('[data-select]');const compare=e.target.closest('[data-compare]');if(compare&&!compare.disabled&&state.selected){loadDeck('a',state.selected);loadDeck('b',trackById(compare.dataset.compare));matchDeckTempo();}else if(load&&!load.disabled)loadDeck(load.dataset.load,trackById(load.dataset.id));else if(select)selectTrack(select.dataset.select);});
  $('new-playlist').addEventListener('click',createPlaylist);$('edit-playlist').addEventListener('click',editPlaylist);$('export').addEventListener('click',exportLibrary);$('open-plan').addEventListener('click',openPlan);
  $('modal-close').addEventListener('click',()=>$('modal').close());
  $('keyboard-help').addEventListener('click',()=>modal('Keyboard shortcuts','<p class="muted small">Shortcuts are active outside form fields and dialogs.</p><div class="shortcut"><span>Search your library</span><kbd>/</kbd></div><div class="shortcut"><span>Load selected track into A / B</span><kbd>A / B</kbd></div><div class="shortcut"><span>Play or pause focused deck</span><kbd>Space</kbd></div><div class="shortcut"><span>Seek focused deck 5 seconds</span><kbd>← / →</kbd></div><div class="shortcut"><span>Close a dialog</span><kbd>Esc</kbd></div>'));
  for(const id of ['a','b'])bindDeck(id);focusDeck('a');updateVolumes();
  document.querySelectorAll('.deck-focus').forEach(b=>b.addEventListener('click',()=>focusDeck(b.dataset.deck)));
  $('crossfader').addEventListener('input',updateVolumes);$('master').addEventListener('input',updateVolumes);
  $('sync-tempo').addEventListener('click',matchDeckTempo);
  document.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey||$('modal').open||e.target.closest('input,select,textarea,[contenteditable=true]'))return;if(e.key==='/'){e.preventDefault();$('search').focus();}else if(['a','b'].includes(e.key.toLowerCase())&&state.selected){e.preventDefault();loadDeck(e.key.toLowerCase(),state.selected);}else if(e.code==='Space'&&!e.target.closest('button,a')){e.preventDefault();play(state.focus);}else if(['ArrowLeft','ArrowRight'].includes(e.key)&&decks[state.focus].track){e.preventDefault();const a=decks[state.focus].audio;a.currentTime=Math.max(0,Math.min(finite(a.duration)?a.duration:Infinity,a.currentTime+(e.key==='ArrowRight'?5:-5)));}});
}
bind();refresh();
