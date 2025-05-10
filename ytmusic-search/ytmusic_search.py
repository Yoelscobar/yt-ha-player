import sys
import json
from ytmusicapi import YTMusic
import traceback # Für besseres Fehler-Logging

def format_duration_seconds(seconds):
    if seconds is None:
        return "N/A"
    try:
        sec = int(seconds) 
        if sec < 0: 
            return "N/A"
        
        hrs = sec // 3600
        mns = (sec % 3600) // 60
        scs = sec % 60
        if hrs > 0:
            return f"{hrs:d}:{mns:02d}:{scs:02d}"
        else:
            return f"{mns:02d}:{scs:02d}"
    except (ValueError, TypeError):
        return "N/A"

def get_best_thumbnail_url(thumbnails_list):
    if not isinstance(thumbnails_list, list) or not thumbnails_list:
        return "https://placehold.co/200x140/2a2a2a/ccc?text=No+Image" 

    try:
        sorted_thumbnails = sorted(
            [thumb for thumb in thumbnails_list if isinstance(thumb, dict) and 'width' in thumb and 'url' in thumb],
            key=lambda x: x['width'],
            reverse=True
        )
        if sorted_thumbnails:
            for thumb in sorted_thumbnails:
                if thumb['width'] >= 200:
                    return thumb['url']
            return sorted_thumbnails[0]['url'] 
    except (TypeError, KeyError):
        pass

    best_thumb = thumbnails_list[-1]
    if isinstance(best_thumb, dict) and 'url' in best_thumb:
        return best_thumb['url']
    
    if thumbnails_list and isinstance(thumbnails_list[0], dict) and 'url' in thumbnails_list[0]:
        return thumbnails_list[0]['url']
        
    return "https://placehold.co/200x140/2a2a2a/ccc?text=No+Image"


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing search query"}))
        sys.exit(1)

    query = sys.argv[1]
    
    try:
        ytmusic = YTMusic()
        search_results_raw = ytmusic.search(query, filter=None, limit=20) 
    except Exception as e:
        error_output = {
            "error": f"Failed to initialize YTMusic or perform search: {str(e)}",
            "trace": traceback.format_exc()
        }
        print(json.dumps(error_output))
        sys.exit(1)

    output = []
    processed_ids = set() 

    if not search_results_raw:
        print(json.dumps([])) 
        return

    for item_data in search_results_raw:
        if not isinstance(item_data, dict):
            continue

        current_items_to_parse = []
        if 'results' in item_data and isinstance(item_data['results'], list):
            current_items_to_parse.extend(item_data['results'])
        elif 'resultType' in item_data : 
            current_items_to_parse.append(item_data)
        
        for item in current_items_to_parse:
            if not isinstance(item, dict):
                continue

            item_type_raw = item.get('resultType')
            item_type = "" 

            if isinstance(item_type_raw, str):
                item_type = item_type_raw.lower() 
            else:
                item_type_fallback = item.get('type')
                if isinstance(item_type_fallback, str):
                    item_type = item_type_fallback.lower()
                else:
                    continue 

            if item_type not in ['song', 'album', 'playlist', 'video']:
                continue

            title = item.get('title')
            if not title: 
                continue
            
            thumbnail_url = get_best_thumbnail_url(item.get('thumbnails'))
            
            entry = {
                'title': title,
                'thumbnail': thumbnail_url,
                'type': item_type, 
                'duration': "N/A",
                'videoId': None,      
                'browseId': None,     
                'playlistId': None,   
                'artist': "N/A",      
                'year': None,         
                'itemCount': None     
            }
            unique_identifier = None 

            if item_type == 'song' or item_type == 'video':
                entry['videoId'] = item.get('videoId')
                unique_identifier = entry['videoId']
                
                if item.get('duration_seconds') is not None:
                    entry['duration'] = format_duration_seconds(item.get('duration_seconds'))
                elif item.get('duration'): 
                    entry['duration'] = item.get('duration')

                artists_data = item.get('artists')
                if isinstance(artists_data, list) and artists_data and isinstance(artists_data[0], dict):
                    entry['artist'] = artists_data[0].get('name', "N/A")
                elif artists_data : 
                    entry['artist'] = str(artists_data)

            elif item_type == 'album':
                temp_browse_id = item.get('browseId')
                # Versuche, eine audioPlaylistId zu finden, die oft für EPs/Singles verwendet wird
                # oder eine normale playlistId, falls vorhanden.
                # Die Struktur von 'item' kann variieren, daher mehrere Checks.
                found_playlist_id = item.get('audioPlaylistId') or item.get('playlistId')

                if temp_browse_id and temp_browse_id.startswith('MPRE'):
                    entry['browseId'] = temp_browse_id
                    unique_identifier = temp_browse_id
                    # Typ bleibt 'album'
                elif found_playlist_id:
                    # Es ist als 'album' klassifiziert, hat aber keine MPRE-browseId,
                    # aber wir haben eine playlistId gefunden! Behandle es als Playlist.
                    print(f"[YTMusicSearch DEBUG] Item originally 'album' (ID: '{temp_browse_id}'), but found playlistId ('{found_playlist_id}'). Reclassifying as 'playlist'. Full item: {json.dumps(item)}", file=sys.stderr)
                    entry['type'] = 'playlist' # Umklassifizieren!
                    entry['playlistId'] = found_playlist_id
                    entry['browseId'] = None # Sicherstellen, dass die ungültige browseId nicht verwendet wird
                    unique_identifier = found_playlist_id
                else:
                    # Weder MPRE-browseId noch eine alternative playlistId gefunden.
                    print(f"[YTMusicSearch DEBUG] Item classified as 'album' but browseId ('{temp_browse_id}') does not start with 'MPRE' and no fallback playlistId found. Full item: {json.dumps(item)}", file=sys.stderr)
                    entry['type'] = 'album_unsupported_id' 
                    entry['browseId'] = None 
                    unique_identifier = temp_browse_id # Für processed_ids, um Duplikate zu vermeiden

                entry['year'] = str(item.get('year')) if item.get('year') else None
                artists_data = item.get('artists') 
                if isinstance(artists_data, list) and artists_data and isinstance(artists_data[0], dict):
                    entry['artist'] = artists_data[0].get('name', "N/A")

            elif item_type == 'playlist':
                entry['playlistId'] = item.get('playlistId')
                unique_identifier = entry['playlistId']
                
                author_data = item.get('author') 
                if isinstance(author_data, list) and author_data and isinstance(author_data[0], dict):
                    entry['artist'] = author_data[0].get('name', "N/A") 
                elif isinstance(author_data, dict) : 
                     entry['artist'] = author_data.get('name', "N/A")
                
                item_count_raw = item.get('itemCount') or item.get('trackCount') 
                if item_count_raw is not None:
                    try:
                        entry['itemCount'] = str(int(item_count_raw))
                    except ValueError:
                        entry['itemCount'] = None
            
            # Verhindere Duplikate basierend auf dem unique_identifier
            if unique_identifier and unique_identifier not in processed_ids:
                output.append(entry)
                processed_ids.add(unique_identifier)
            # Fallback für 'album_unsupported_id', falls es einen temp_browse_id hatte aber unique_identifier None wurde
            elif entry['type'] == 'album_unsupported_id' and temp_browse_id and temp_browse_id not in processed_ids:
                 output.append(entry)
                 processed_ids.add(temp_browse_id)

            
            if len(output) >= 15: 
                break
        if len(output) >= 15:
            break
            
    print(json.dumps(output))

if __name__ == "__main__":
    main()
