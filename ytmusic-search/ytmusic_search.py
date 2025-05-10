import sys
import json
from ytmusicapi import YTMusic

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Missing search query'}))
        sys.exit(1)

    query = sys.argv[1]
    ytmusic = YTMusic()
    results = ytmusic.search(query, filter='songs')

    output = []
    for item in results:
        output.append({
            'title': item.get('title'),
            'videoId': item.get('videoId'),
            'thumbnail': item['thumbnails'][0]['url'] if item.get('thumbnails') else ''
        })

    print(json.dumps(output))

if __name__ == "__main__":
    main()

