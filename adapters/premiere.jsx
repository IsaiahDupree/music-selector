/**
 * music-selector — Adobe Premiere Pro ExtendScript adapter
 * =========================================================
 * Runs the music selector and imports the top match into the active sequence.
 *
 * Installation:
 *   1. Open Premiere Pro → File → Scripts → Run Script...
 *   2. Select this file
 *
 *   OR automate via: File → Scripts → Browse...
 *   OR place in: /Applications/Adobe Premiere Pro/Scripts/
 *
 * Configuration:
 *   Edit MUSIC_SELECTOR_DIR and PYTHON3 below to match your system.
 *
 * What it does:
 *   1. Shows a dialog to choose mood / platform / duration
 *   2. Runs suggest.py via shell command (python3)
 *   3. Parses JSON output to get the best track
 *   4. Imports the audio file into the current project
 *   5. Places it on Audio track 2 of the active sequence at time 0
 */

// ─── Configuration ────────────────────────────────────────────────────────────
var MUSIC_SELECTOR_DIR = "/path/to/music-selector";   // EDIT THIS
var PYTHON3 = "/usr/bin/python3";                      // `which python3` to find yours
var DEFAULT_VOLUME_DB = -12;                           // dB reduction for background music

// ─── Helper: run a shell command and return stdout ────────────────────────────
function shellRun(cmd) {
    var result = system.callSystem(cmd);
    return result;
}

// ─── Helper: simple JSON parser for the subset we need ───────────────────────
// ExtendScript has no JSON.parse — we eval() the known-safe CLI output.
function parseJSON(str) {
    try {
        return eval("(" + str + ")");
    } catch (e) {
        return null;
    }
}

// ─── Dialog: pick mood + platform + duration ─────────────────────────────────
function showDialog() {
    var dlg = new Window("dialog", "Music Selector");
    dlg.orientation = "column";
    dlg.alignChildren = "fill";

    var moodGroup = dlg.add("group");
    moodGroup.add("statictext", undefined, "Mood:");
    var moodDrop = moodGroup.add("dropdownlist", undefined,
        ["energetic", "calm", "inspiring", "dramatic", "uplifting", "happy", "focused"]);
    moodDrop.selection = 0;

    var platformGroup = dlg.add("group");
    platformGroup.add("statictext", undefined, "Platform:");
    var platformDrop = platformGroup.add("dropdownlist", undefined,
        ["(any)", "instagram", "tiktok", "youtube", "linkedin", "twitter"]);
    platformDrop.selection = 0;

    var durGroup = dlg.add("group");
    durGroup.add("statictext", undefined, "Duration (sec):");
    var durInput = durGroup.add("edittext", undefined, "30");
    durInput.characters = 6;

    var btnGroup = dlg.add("group");
    btnGroup.add("button", undefined, "Select Music", { name: "ok" });
    btnGroup.add("button", undefined, "Cancel", { name: "cancel" });

    if (dlg.show() !== 1) return null;

    return {
        mood: moodDrop.selection.text,
        platform: platformDrop.selection.text === "(any)" ? null : platformDrop.selection.text,
        duration: parseFloat(durInput.text) || null,
    };
}

// ─── Main ─────────────────────────────────────────────────────────────────────
function main() {
    var opts = showDialog();
    if (!opts) return;

    // Build CLI command
    var args = [
        PYTHON3,
        '"' + MUSIC_SELECTOR_DIR + '/suggest.py"',
        "--json",
        "--top", "1",
        "--mood", opts.mood,
    ];
    if (opts.platform) { args.push("--platform"); args.push(opts.platform); }
    if (opts.duration)  { args.push("--duration"); args.push(String(opts.duration)); }

    var cmd = args.join(" ");
    var raw = shellRun(cmd);

    if (!raw || raw.indexOf("[") === -1) {
        alert("music-selector: No output from suggest.py.\n\nCommand tried:\n" + cmd);
        return;
    }

    // Extract JSON array from output
    var jsonStart = raw.indexOf("[");
    var jsonEnd   = raw.lastIndexOf("]") + 1;
    var jsonStr   = raw.substring(jsonStart, jsonEnd);
    var tracks    = parseJSON(jsonStr);

    if (!tracks || !tracks.length) {
        alert("music-selector: No tracks matched. Try a different mood or remove filters.");
        return;
    }

    var track = tracks[0];
    var resolvedPath = track.local_path;

    // Resolve relative paths against the music-selector directory
    if (resolvedPath.charAt(0) !== "/") {
        resolvedPath = MUSIC_SELECTOR_DIR + "/" + resolvedPath;
    }

    // Import audio file into project
    var proj = app.project;
    var importedItems = proj.importFiles(
        [resolvedPath],
        true,   // suppress UI
        proj.rootItem,
        false   // import as numbered stills
    );

    if (!importedItems) {
        alert("Failed to import: " + resolvedPath +
              "\n\nMake sure the file exists in the tracks/ directory.");
        return;
    }

    // Find the imported clip in project
    var audioItem = null;
    for (var i = 0; i < proj.rootItem.children.numItems; i++) {
        var item = proj.rootItem.children[i];
        if (item.name === File(resolvedPath).name) {
            audioItem = item;
            break;
        }
    }

    if (!audioItem) {
        alert("Track imported to project bin. Drag it to Audio 2 in your sequence.\nTrack: " + track.title);
        return;
    }

    // Place on Audio track 2 of active sequence at time 0
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("Track imported. No active sequence — open a sequence and drag the clip from the bin.\nTrack: " + track.title);
        return;
    }

    var audioTrack = seq.audioTracks[1]; // index 1 = Audio 2
    if (!audioTrack) {
        alert("Sequence has only one audio track. Track imported to bin — drag manually.\nTrack: " + track.title);
        return;
    }

    var startTime = seq.getPlayerPosition();
    audioTrack.insertClip(audioItem, startTime.seconds);

    alert(
        "Music placed on Audio 2!\n\n" +
        track.title + " — " + track.artist + "\n" +
        "Score: " + Math.round(track.score * 100) + "%  |  " +
        "Genre: " + track.genre + "\n\n" +
        "Tip: Set clip volume to " + DEFAULT_VOLUME_DB + " dB for background mix."
    );
}

main();
