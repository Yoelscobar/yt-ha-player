import sys
import json
from ytmusicapi import YTMusic
import traceback # Für besseres Fehler-Logging

def format_duration_seconds(seconds):
    if seconds is None:
        return "N/A"
    try:
        sec = int(seconds) # Stellt sicher, dass es eine Zahl ist
        if sec < 0: # Negative Dauer ist ungültig
            return "N/A"
        
        hrs = sec // 3600
        mns = (sec % 3600) // 60
        scs = sec % 60
        if hrs > 0:
            return f"{hrs:d}:{mns:02d}:{scs:02d}"
        else:
            return f"{mns:02d}:{scs:02d}"
    except (ValueError, TypeError):
        # Falls die Umwandlung fehlschlägt oder der Typ nicht passt
        return "N/A"

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing search query"}))
        sys.exit(1)

    query = sys.argv[1]
    
    try:
        # Initialisiere mit Authentifizierung, falls du private Playlists etc. durchsuchen willst (erfordert setup)
        # Für öffentliche Daten ist keine Authentifizierung nötig.
        # ytmusic = YTMusic('oauth.json') # Beispiel mit Authentifizierung
        ytmusic = YTMusic()
        # Suche ohne spezifischen Filter, um verschiedene Typen zu bekommen. Limit begrenzt die Anzahl der Shelves/Items.
        search_results_raw = ytmusic.search(query, filter=None, limit=20)
    except Exception as e:
        error_output = {
            "error": f"Failed to initialize YTMusic or perform search: {str(e)}",
            "trace": traceback.format_exc()
        }
        print(json.dumps(error_output))
        sys.exit(1)

    output = []
    processed_ids = set() # Um Duplikate zu vermeiden, falls ein Item in mehreren Sektionen auftaucht

    if not search_results_raw:
        print(json.dumps([])) # Leere Liste, wenn keine Ergebnisse
        return

    for item_data in search_results_raw:
        if not isinstance(item_data, dict):
            continue

        current_items_to_parse = []
        # Ergebnisse können direkt in 'results' eines Shelfs sein oder das item_data selbst ist ein Ergebnis
        if 'results' in item_data and isinstance(item_data['results'], list):
            current_items_to_parse.extend(item_data['results'])
        elif 'resultType' in item_data : # item_data ist selbst ein Ergebnis (z.B. Top-Result)
            current_items_to_parse.append(item_data)
        
        for item in current_items_to_parse:
            if not isinstance(item, dict):
                continue

            item_type_raw = item.get('resultType')
            if isinstance(item_type_raw, str):
                item_type = item_type_raw.lower() # Normalisieren (z.B. 'Song' -> 'song')
            else:
                # Manchmal gibt es keinen resultType, aber einen 'type' (z.B. bei ytmusicapi intern)
                item_type_fallback = item.get('type')
                if isinstance(item_type_fallback, str):
                    item_type = item_type_fallback.lower()
                else:
                    continue # Kein Typ identifizierbar

            # Wir interessieren uns primär für Songs, Alben, Playlists und Videos (oft Musikvideos)
            if item_type not in ['song', 'album', 'playlist', 'video']:
                continue

            title = item.get('title')
            if not title: # Ohne Titel macht der Eintrag wenig Sinn
                continue

            thumbnail_url = ''
            thumbnail_list = item.get('thumbnails')
            if isinstance(thumbnail_list, list) and len(thumbnail_list) > 0:
                if isinstance(thumbnail_list[0], dict) and 'url' in thumbnail_list[0]:
                    thumbnail_url = thumbnail_list[0]['url']
            
            # Basis-Struktur für jeden Eintrag
            entry = {
                'title': title,
                'thumbnail': thumbnail_url,
                'type': item_type,
                'duration': "N/A",
                'videoId': None,      # Für Songs/Videos
                'browseId': None,     # Für Alben (führt zur Album-Seite)
                'playlistId': None,   # Für Playlists
                'artist': "N/A",      # Künstlername(n)
                'year': None,         # Erscheinungsjahr für Alben
                'itemCount': None     # Anzahl der Titel in Playlists
            }

            unique_identifier = None

            if item_type == 'song' or item_type == 'video':
                entry['videoId'] = item.get('videoId')
                unique_identifier = entry['videoId']
                
                # Dauer
                if item.get('duration_seconds') is not None:
                    entry['duration'] = format_duration_seconds(item.get('duration_seconds'))
                elif item.get('duration'): # Manchmal ist es ein bereits formatierter String
                    entry['duration'] = item.get('duration')

                # Künstler
                artists_data = item.get('artists')
                if isinstance(artists_data, list) and len(artists_data) > 0 and isinstance(artists_data[0], dict):
                    entry['artist'] = artists_data[0].get('name', "N/A")
                elif artists_data : # Falls es nur ein String ist (selten)
                    entry['artist'] = str(artists_data)


            elif item_type == 'album':
                entry['browseId'] = item.get('browseId') # ID um Albumdetails zu laden
                unique_identifier = entry['browseId']
                entry['year'] = str(item.get('year')) if item.get('year') else None
                
                artists_data = item.get('artists') # Alben haben auch Künstler
                if isinstance(artists_data, list) and len(artists_data) > 0 and isinstance(artists_data[0], dict):
                    entry['artist'] = artists_data[0].get('name', "N/A")


            elif item_type == 'playlist':
                entry['playlistId'] = item.get('playlistId')
                unique_identifier = entry['playlistId']
                
                author_data = item.get('author') # Autor der Playlist
                if isinstance(author_data, list) and len(author_data) > 0 and isinstance(author_data[0], dict):
                    entry['artist'] = author_data[0].get('name', "N/A") # Nutzen 'artist' für Konsistenz
                elif isinstance(author_data, dict) : # Manchmal ist author direkt ein dict
                     entry['artist'] = author_data.get('name', "N/A")
                elif item.get('owner') and isinstance(item.get('owner'),list) and len(item.get('owner')) >0 : # Veraltet?
                    entry['artist'] = item.get('owner')[0].get('name',"N/A")


                item_count_raw = item.get('itemCount') or item.get('trackCount') # Manchmal heißt es trackCount
                if item_count_raw is not None:
                    try:
                        entry['itemCount'] = str(int(item_count_raw))
                    except ValueError:
                        entry['itemCount'] = None


            if unique_identifier and unique_identifier not in processed_ids:
                # Nur hinzufügen, wenn ein primärer Identifier vorhanden ist und noch nicht verarbeitet wurde
                output.append(entry)
                processed_ids.add(unique_identifier)
            
            if len(output) >= 15: # Begrenzen wir die Gesamtzahl der Ergebnisse
                break
        if len(output) >= 15:
            break
            
    print(json.dumps(output)) # Kompaktes JSON für die Ausgabe

if __name__ == "__main__":
    main()