# ytmusic-search/ytmusic_get_first_track.py
import sys
import json
from ytmusicapi import YTMusic
import traceback

def main():
    # Debug-Ausgabe: Mit welchen Argumenten wurde das Skript aufgerufen?
    print(f"[PYTHON_SCRIPT_DEBUG] Script invoked with args: {sys.argv}", file=sys.stderr)

    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Missing collection_id or collection_type arguments'}), file=sys.stderr)
        print(json.dumps({'error': 'Missing collection_id or collection_type arguments'}))
        sys.exit(1)

    collection_id = sys.argv[1]
    collection_type = sys.argv[2].lower()

    # Debug-Ausgabe: Welche Werte haben collection_id und collection_type?
    print(f"[PYTHON_SCRIPT_DEBUG] collection_id: '{collection_id}', collection_type: '{collection_type}'", file=sys.stderr)

    try:
        ytmusic = YTMusic() 
        first_track_videoId = None

        if collection_type == 'album':
            print(f"[PYTHON_SCRIPT_DEBUG] Processing type 'album' for ID '{collection_id}'", file=sys.stderr)
            
            # Explizite Prüfung der Bedingung und Ausgabe des Ergebnisses
            is_mpre_prefix = collection_id.startswith('MPRE')
            print(f"[PYTHON_SCRIPT_DEBUG] Does collection_id '{collection_id}' start with 'MPRE'? {is_mpre_prefix}", file=sys.stderr)

            if not is_mpre_prefix: 
                error_msg = f"Invalid album browseId format for '{collection_id}'. Expected to start with 'MPRE'."
                print(f"[PYTHON_SCRIPT_DEBUG] Condition (not is_mpre_prefix) is TRUE. Returning with error message.", file=sys.stderr)
                print(json.dumps({'error': error_msg}), file=sys.stderr) 
                print(json.dumps({'error': error_msg})) 
                return # Beende main(), Skript sollte mit Code 0 enden, wenn kein sys.exit() aufgerufen wird

            # Diese Zeile sollte nur erreicht werden, wenn die ID mit 'MPRE' beginnt
            print(f"[PYTHON_SCRIPT_DEBUG] Condition (not is_mpre_prefix) is FALSE. Proceeding to call ytmusic.get_album().", file=sys.stderr)
            album_data = ytmusic.get_album(browseId=collection_id) 
            
            if album_data and album_data.get('tracks') and len(album_data['tracks']) > 0:
                for track in album_data['tracks']:
                    if track.get('videoId'):
                        first_track_videoId = track.get('videoId')
                        break 
        elif collection_type == 'playlist':
            print(f"[PYTHON_SCRIPT_DEBUG] Processing type 'playlist' for ID '{collection_id}'", file=sys.stderr)
            playlist_data = ytmusic.get_playlist(playlistId=collection_id, limit=5) 
            if playlist_data and playlist_data.get('tracks') and len(playlist_data['tracks']) > 0:
                for track in playlist_data['tracks']:
                    if track.get('videoId'):
                        first_track_videoId = track.get('videoId')
                        break 
        else:
            error_msg = f'Unsupported collection type: {collection_type}'
            print(f"[PYTHON_SCRIPT_DEBUG] Unsupported type '{collection_type}'. Exiting with error.", file=sys.stderr)
            print(json.dumps({'error': error_msg}), file=sys.stderr)
            print(json.dumps({'error': error_msg}))
            sys.exit(1) # Dieser Fall ist ein Konfigurationsfehler -> Exit Code 1

        if first_track_videoId:
            print(f"[PYTHON_SCRIPT_DEBUG] Found first_track_videoId: {first_track_videoId}", file=sys.stderr)
            print(json.dumps({'videoId': first_track_videoId, 'status': 'success'}))
        else:
            # Kein Fehler des Skripts, nur kein abspielbarer Track gefunden.
            print(f"[PYTHON_SCRIPT_DEBUG] Could not find any playable track in {collection_type} '{collection_id}'.", file=sys.stderr)
            print(json.dumps({'error': f'Could not find any playable track in {collection_type} {collection_id}'}))
            # Wichtig: Kein sys.exit(1) hier, server.js wertet das 'error'-Feld im JSON aus.

    except Exception as e:
        print(f"[PYTHON_SCRIPT_DEBUG] Exception caught in main try-except block: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) 
        error_details = {
            'error': str(e),
            'trace_summary': traceback.format_exc().splitlines()[-3:] 
        }
        print(json.dumps(error_details)) # JSON-Fehler an stdout für Node.js
        sys.exit(1) # Expliziter Exit Code 1 bei Exceptions

if __name__ == "__main__":
    main()
