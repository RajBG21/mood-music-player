import os
import base64
import requests

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


def get_access_token():
    """Get Spotify API access token using Client Credentials Flow."""

    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
    }
    data = {
        "grant_type": "client_credentials"
    }

    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    print("SPOTIFY RESPONSE:", response.json())
    token_info = response.json()

    return token_info.get("access_token")


def get_tracks_for_mood(mood):
    if not mood:
        return []
    """Search Spotify tracks based on mood keyword."""

    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}"
    }

    query = mood + " mood"
    url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=12"

    response = requests.get(url, headers=headers)
    data = response.json()

    tracks = []

    try:
        for item in data["tracks"]["items"]:
            tracks.append({
                "title": item["name"],
                "artist": item["artists"][0]["name"],
                "url": item["external_urls"]["spotify"]
            })
    except KeyError:
        return []

    return tracks
