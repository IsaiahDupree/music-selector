"""python3 -m djlab: owner-local metadata import, export and HTTP interface."""
import argparse
import json
import os
from pathlib import Path

from .evidence import Invalid, canonical, import_catalog
from .library import Library, private_directory, private_write
from .server import Server, capabilities, prepare_launch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['import','import-analysis','status','serve','launch','export'])
    parser.add_argument('--studio-root',type=Path,default=Path.home()/'Documents/Software/sour-sides-studio')
    parser.add_argument('--state-dir',type=Path,default=Path.home()/'Library/Application Support/DJLab')
    parser.add_argument('--port',type=int,default=5572)
    parser.add_argument('--format',choices=['json','csv','m3u8','xspf','rekordbox'],default='json')
    parser.add_argument('--playlist-id')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--evidence-dir',type=Path)
    parser.add_argument('--collection-receipt-sha256')
    parser.add_argument('--runner-sha256')
    parser.add_argument('--legacy-sha256')
    parser.add_argument('--guard-sha256')
    args=parser.parse_args()
    if args.command=='launch':
        print(json.dumps({'launch_file':str(prepare_launch(args.state_dir,args.port)),'expires_in_seconds':600}));return
    catalog=import_catalog(args.studio_root)
    lib=Library(catalog,args.state_dir)
    if args.command=='import-analysis':
        if not all((args.evidence_dir,args.collection_receipt_sha256,args.runner_sha256,args.legacy_sha256,args.guard_sha256)):
            raise Invalid('Import requires actual evidence directory plus independently reviewed receipt/runner/legacy/guard SHA256 pins')
        print(json.dumps(lib.import_analysis(args.evidence_dir,receipt_sha256=args.collection_receipt_sha256,
              source_pins={'runner':args.runner_sha256,'legacy_analyzer':args.legacy_sha256,'process_guard':args.guard_sha256})));return
    if args.command=='import':
        private_write(lib.state/'catalog.json',canonical(catalog)+b'\n')
        print(json.dumps({'status':'imported','tracks':len(catalog['tracks']),'evidence_files':len(catalog['evidence']),
                          'audio_decoded':False,'audio_rehashed':False,'catalog':str(lib.state/'catalog.json')}));return
    if args.command=='status':
        tracks=lib.tracks();print(json.dumps({'tracks':len(tracks),'media_available':sum(t['media']['available'] for t in tracks),
                                           'playlists':len(lib.playlist_list()),'capabilities':capabilities(lib)},indent=2));return
    if args.command=='export':
        from .exports import export_library
        rows=lib.tracks();playlist=None
        if args.playlist_id:
            playlist=next((p for p in lib.playlist_list() if p['id']==args.playlist_id),None)
            if playlist is None:raise Invalid('Playlist not found')
            by_id={r['id']:r for r in rows};rows=[by_id[i] for i in playlist['track_ids']]
        media={r['id']:catalog['media'][r['id']]['path'] for r in rows if r['media']['available']}
        body,mime,name=export_library(args.format,rows,playlist=playlist,media_paths=media)
        if not args.output:raise Invalid('--output is required; exports may contain private local paths')
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(body)
        print(json.dumps({'output':str(args.output),'format':args.format,'bytes':len(body)}));return
    if not 1024<=args.port<=65535:raise Invalid('Serve port must be 1024–65535')
    server=Server(lib,args.port)
    try:
        launch=prepare_launch(lib.state,server.server_port)
        print(json.dumps({'origin':server.origin,'launch_file':str(launch),'tracks':len(catalog['tracks'])}),flush=True)
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':
    try:main()
    except (Invalid,OSError,ValueError) as exc:raise SystemExit('DJLab: '+str(exc))
