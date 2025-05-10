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
    """
    Wählt das beste verfügbare Thumbnail aus der Liste.
    Bevorzugt größere Auflösungen.
    """
    if not isinstance(thumbnails_list, list) or not thumbnails_list:
        return "https://placehold.co/200x140/2a2a2a/ccc?text=No+Image" # Standard-Platzhalter

    # Sortiere Thumbnails nach Breite (absteigend), falls vorhanden, ansonsten nimm das letzte.
    # YTMusicAPI gibt oft Thumbnails mit 'width' und 'height' Angaben zurück.
    try:
        # Versuche, nach Breite zu sortieren, wenn 'width' vorhanden ist
        sorted_thumbnails = sorted(
            [thumb for thumb in thumbnails_list if isinstance(thumb, dict) and 'width' in thumb and 'url' in thumb],
            key=lambda x: x['width'],
            reverse=True
        )
        if sorted_thumbnails:
            # Wähle ein Thumbnail, das nicht zu klein ist, z.B. >= 200px Breite
            for thumb in sorted_thumbnails:
                if thumb['width'] >= 200:
                    return thumb['url']
            return sorted_thumbnails[0]['url'] # Nimm das größte, wenn alle < 200px sind
    except (TypeError, KeyError):
        # Fallback, wenn 'width' nicht vorhanden ist oder Sortierung fehlschlägt
        pass

    # Fallback: Nimm das letzte Thumbnail in der Liste, da es oft das größte ist,
    # oder das erste, wenn es nur eines gibt.
    best_thumb = thumbnails_list[-1]
    if isinstance(best_thumb, dict) and 'url' in best_thumb:
        return best_thumb['url']
    
    # Allerletzter Fallback, wenn die Struktur unerwartet ist
    # (z.B. wenn die Liste nur ein Element hat und der obige Zugriff fehlschlägt)
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
            
            # Thumbnail-Auswahl verbessert
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
                entry['browseId'] = item.get('browseId') 
                unique_identifier = entry['browseId']
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

            if unique_identifier and unique_identifier not in processed_ids:
                output.append(entry)
                processed_ids.add(unique_identifier)
            
            if len(output) >= 15: 
                break
        if len(output) >= 15:
            break
            
    print(json.dumps(output))

if __name__ == "__main__":
    main()
