import os
import random
import pylast
from dotenv import load_dotenv
from flask import Flask, render_template, request, session
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# -----------------------------------------------------------------------------
# 1) Load environment variables (Spotify + Last.fm credentials)
# -----------------------------------------------------------------------------
load_dotenv(dotenv_path="C:/Users/cdub4/GSB570/code/.env")
LASTFM_API_KEY        = os.getenv("LASTFM_API_KEY")
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not LASTFM_API_KEY:
    raise ValueError("Missing LASTFM_API_KEY in .env")
if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("Missing Spotify credentials in .env")

# -----------------------------------------------------------------------------
# 2) Initialize Flask, Last.fm, and Spotify clients
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a‐really‐secret‐key‐for‐sessions")

network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=None)
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
))

# -----------------------------------------------------------------------------
# 2.a) Ensure "history" always exists in session
# -----------------------------------------------------------------------------
@app.before_request
def ensure_history_exists():
    if "history" not in session:
        session["history"] = []

# -----------------------------------------------------------------------------
# 3) Helper: find_similar_tracks (Last.fm track → similar tracks)
# -----------------------------------------------------------------------------
def find_similar_tracks(artist_name: str, track_name: str, limit: int = 3):
    try:
        track_obj = network.get_track(artist_name, track_name)
        _ = track_obj.get_similar(limit=1)
    except Exception:
        track_obj = None

    if track_obj is None:
        # Fallback: search for "track_name artist_name"
        try:
            combined = f"{track_name} {artist_name}"
            search_results = network.search_for_track("", combined)
            track_obj = search_results.get_next_page()[0]
        except Exception:
            return None, artist_name, track_name, []

    real_artist = track_obj.artist.name
    real_title  = track_obj.title

    try:
        album_obj = track_obj.get_album()
        input_cover = album_obj.get_cover_image() or None
    except Exception:
        input_cover = None

    try:
        similar_list = track_obj.get_similar(limit=limit)
    except Exception:
        similar_list = []

    results = []
    for sim_track, _ in similar_list:
        sim_artist = sim_track.artist.name
        sim_title  = sim_track.title
        try:
            sim_album = sim_track.get_album()
            cover_url = sim_album.get_cover_image() or None
        except Exception:
            cover_url = None

        results.append({
            "title":     sim_title,
            "artist":    sim_artist,
            "cover_url": cover_url
        })

    return input_cover, real_artist, real_title, results

# -----------------------------------------------------------------------------
# 4) Helper: attempt_lastfm_recommendation (Last.fm fallback)
# -----------------------------------------------------------------------------
def attempt_lastfm_recommendation(query: str):
    query = query.strip()

    # 4.a) If user typed "Artist - Track"
    if " - " in query or " – " in query:
        sep = " - " if " - " in query else " – "
        artist_name, track_name = [p.strip() for p in query.split(sep, 1)]
        input_cover, real_artist, real_title, recs = find_similar_tracks(artist_name, track_name)
        if recs:
            return {
                "input_cover":  input_cover,
                "input_title":  real_title,
                "input_artist": real_artist,
                "similar":      recs
            }

    # 4.b) Otherwise treat `query` as just a track name
    try:
        search_results = network.search_for_track("", query)
        track_obj = search_results.get_next_page()[0]
        real_track  = track_obj.title
        real_artist = track_obj.artist.name

        input_cover, real_artist, real_track, recs = find_similar_tracks(real_artist, real_track)
        if recs:
            return {
                "input_cover":  input_cover,
                "input_title":  real_track,
                "input_artist": real_artist,
                "similar":      recs
            }
    except Exception:
        pass

    # 4.c) No Last.fm results at all
    return {
        "input_cover":  None,
        "input_title":  None,
        "input_artist": None,
        "similar":      []
    }

# -----------------------------------------------------------------------------
# 5) Helper: recommend_similar_tracks (Spotify + Last.fm hybrid)
# -----------------------------------------------------------------------------
def recommend_similar_tracks(track_id, artist_id, track_name, artist_name, country="US"):
    recommendations = []
    existing_ids    = set()

    # 5.1) Fetch audio features for “vibe”
    try:
        features = sp.audio_features([track_id])[0] or {}
    except Exception:
        features = {}

    # 5.2) Fetch Spotify‐artist genres
    try:
        all_genres = sp.artist(artist_id).get("genres", [])
    except Exception:
        all_genres = []

    # 5.3) Narrow to rap/hip‐hop/trap genres (if any)
    genre_seeds = [g.lower() for g in all_genres
                   if any(x in g.lower() for x in ("trap", "hip hop", "rap"))][:5]

    # 5.4) Spotify recommendations with track+artist+genres
    try:
        rec_kwargs = {
            "seed_tracks": [track_id],
            "seed_artists": [artist_id],
            "limit": 20,
            "country": country,
            "target_energy": features.get("energy"),
            "target_tempo": int(features.get("tempo", 0)),
            "target_valence": features.get("valence")
        }
        if genre_seeds:
            rec_kwargs["seed_genres"] = ",".join(genre_seeds)

        rec_items = sp.recommendations(**rec_kwargs).get("tracks", []) or []
    except Exception:
        rec_items = []

    for rec in rec_items:
        if rec["id"] != track_id:
            recommendations.append(rec)
            existing_ids.add(rec["id"])
        if len(recommendations) >= 3:
            break

    # 5.5) If fewer than 3, fallback to artist‐only seed
    if len(recommendations) < 3:
        try:
            rec_items2 = sp.recommendations(
                seed_artists=[artist_id],
                limit=20,
                country=country
            ).get("tracks", []) or []
        except Exception:
            rec_items2 = []

        for rec in rec_items2:
            if rec["id"] not in existing_ids and rec["id"] != track_id:
                recommendations.append(rec)
                existing_ids.add(rec["id"])
            if len(recommendations) >= 3:
                break

    # 5.6) If still < 3, use Last.fm similar → Spotify search
    if len(recommendations) < 3:
        try:
            lfm_similar = network.get_track(artist_name, track_name).get_similar(limit=5)
        except Exception:
            lfm_similar = []

        for sim_track_obj, _ in lfm_similar:
            sim_artist = sim_track_obj.artist.name
            sim_title  = sim_track_obj.title
            try:
                items = sp.search(q=f"track:{sim_title} artist:{sim_artist}", type="track", limit=1)\
                           .get("tracks", {}).get("items", [])
            except Exception:
                items = []

            if items:
                new_track = items[0]
                if new_track["id"] not in existing_ids and new_track["id"] != track_id:
                    recommendations.append(new_track)
                    existing_ids.add(new_track["id"])
            if len(recommendations) >= 3:
                break

    # 5.7) FINAL FALLBACK: pool from **all** top‐tracks of the original artist
    #        and all top-tracks of Last.fm–similar artists (no more “top 50%” filter)
    if len(recommendations) < 3:
        pool = []

        # 5.7.a) Include **all** top-tracks of the original artist (except seed track)
        try:
            orig_top = sp.artist_top_tracks(artist_id, country=country).get("tracks", [])
        except Exception:
            orig_top = []
        for tr in orig_top:
            if tr["id"] != track_id:
                pool.append(tr)

        # 5.7.b) Include **all** top-tracks for each Last.fm similar artist
        try:
            lfm_sim_art = network.get_artist(artist_name).get_similar(limit=5)
        except Exception:
            lfm_sim_art = []
        for sim_art in lfm_sim_art:
            sim_name = sim_art.item.get_name()
            try:
                artists = sp.search(q=f"artist:{sim_name}", type="artist", limit=1)\
                            .get("artists", {}).get("items", [])
            except Exception:
                artists = []
            if not artists:
                continue

            sim_artist_id = artists[0]["id"]
            try:
                top_tracks = sp.artist_top_tracks(sim_artist_id, country=country).get("tracks", [])
            except Exception:
                top_tracks = []
            for tr in top_tracks:
                if tr["id"] != track_id:
                    pool.append(tr)

        random.shuffle(pool)
        for candidate in pool:
            if candidate["id"] not in existing_ids:
                recommendations.append(candidate)
                existing_ids.add(candidate["id"])
            if len(recommendations) >= 3:
                break

    return recommendations[:3]

# -----------------------------------------------------------------------------
# 6) Main helper: find_similar_music (Spotify first, then Last.fm fallback)
# -----------------------------------------------------------------------------
def find_similar_music(query: str):
    query = query.strip()

    # 6.a) Attempt Spotify match
    try:
        if " - " in query:
            artist_part, title_part = [p.strip() for p in query.split(" - ", 1)]
            spotify_search = sp.search(
                q=f"track:{title_part} artist:{artist_part}",
                type="track",
                limit=1
            )
        else:
            spotify_search = sp.search(
                q=f"track:{query}",
                type="track",
                limit=1
            )

        items = spotify_search.get("tracks", {}).get("items", [])
        if items:
            track_obj   = items[0]
            track_id    = track_obj["id"]
            artist_id   = track_obj["artists"][0]["id"]
            artist_name = track_obj["artists"][0]["name"]
            track_name  = track_obj["name"]
            input_cover = track_obj["album"]["images"][0]["url"]

            rec_tracks = recommend_similar_tracks(track_id, artist_id, track_name, artist_name)
            if rec_tracks:
                recs = []
                for rec in rec_tracks:
                    recs.append({
                        "title":     rec["name"],
                        "artist":    rec["artists"][0]["name"],
                        "cover_url": rec["album"]["images"][0]["url"],
                        "url":       rec["external_urls"]["spotify"]
                    })
                return {
                    "input_cover":  input_cover,
                    "input_title":  track_name,
                    "input_artist": artist_name,
                    "similar":      recs
                }
    except Exception:
        pass

    # 6.b) Fallback to Last.fm
    return attempt_lastfm_recommendation(query)

# -----------------------------------------------------------------------------
# 7) Flask route: store session‐based history & render collapsible sidebar
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_query = request.form.get("query", "").strip()
        if not user_query:
            return render_template("index.html", error="Please enter a song or album name.")

        results = find_similar_music(user_query)

        # Append to history only if we have a valid input_title & at least one recommendation
        if results.get("input_title") and results.get("similar"):
            entry = {
                "input_title": results["input_title"],
                "recommendations": [r["title"] for r in results["similar"]]
            }
            hist = session["history"]
            hist.append(entry)
            session["history"] = hist
            session.modified = True

        return render_template(
            "results.html",
            query=user_query,
            results=results,
            history=session["history"]
        )

    # GET: simply render index; history remains in session
    return render_template("index.html")

# -----------------------------------------------------------------------------
# 8) Run Flask app in debug mode
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
