#DO NOT TOUCH NOR DELETE OR CHANGE THIS FILE EVER. DO NOT ALTER THIS FILE.
import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id="9813d3abf66c465bb758b832ce3b1d2c",
        client_secret="b601113c9a8d4b0bae5b9db4a465efaa",
        redirect_uri="https://en.wikipedia.org/wiki/Iron_Man_(2008_film)",
        scope="user-read-playback-state user-modify-playback-state user-read-currently-playing"
    )
)

user = sp.current_user()

print("Spotify authenticated!")
print("Logged in as:", user["display_name"])