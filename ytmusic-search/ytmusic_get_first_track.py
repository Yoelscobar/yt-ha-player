# ytmusic-search/ytmusic_get_first_track.py
import sys
import json
from ytmusicapi import YTMusic
import traceback

def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Missing collection_id or collection_type arguments'}))
        sys.exit(1)

    collection_id = sys.argv[1]
    collection_type = sys.argv[2].lower() # 'album' or 'playlist'

    try:
        ytmusic = YTMusic() # Authentifizierung ggf. hier hinzufügen: YTMusic('oauth.json')
        first_track_videoId = None

        if collection_type == 'album':
            album_data = ytmusic.get_album(browseId=collection_id)
            if album_data and album_data.get('tracks') and len(album_data['tracks']) > 0:
                # Iteriere durch Tracks, um den ersten mit einer gültigen videoId zu finden
                for track in album_data['tracks']:
                    if track.get('videoId'):
                        first_track_videoId = track.get('videoId')
                        break # Nimm den ersten gefundenen
        elif collection_type == 'playlist':
            # get_playlist gibt eine Liste von Tracks zurück
            playlist_data = ytmusic.get_playlist(playlistId=collection_id, limit=5) # Lade ein paar Tracks, falls der erste nicht abspielbar
            if playlist_data and playlist_data.get('tracks') and len(playlist_data['tracks']) > 0:
                for track in playlist_data['tracks']:
                    if track.get('videoId'):
                        first_track_videoId = track.get('videoId')
                        break # Nimm den ersten gefundenen
        else:
            print(json.dumps({'error': f'Unsupported collection type: {collection_type}'}))
            sys.exit(1)

        if first_track_videoId:
            print(json.dumps({'videoId': first_track_videoId, 'status': 'success'}))
        else:
            print(json.dumps({'error': f'Could not find any playable track in {collection_type} {collection_id}'}))

    except Exception as e:
        error_details = {
            'error': str(e),
            'trace': traceback.format_exc()
        }
        print(json.dumps(error_details))
        sys.exit(1)

if __name__ == "__main__":
    main()