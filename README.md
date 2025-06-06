# music-recommendations
=== Readme.txt ===

Music Recommender Prototype
===========================

Overview
--------
This is a simple Flask-based web app that takes a song query (either “Artist – Track” or just a track name), 
looks up that track via Spotify (with a Last.fm fallback), and then shows you similar songs. 
It also keeps a per-session history of your previous searches and lets you “load 3 more” recommendations on demand.

Directory Structure
-------------------
C:\Users\cdub4\GSB570\code\
├── .env                   ← your API credentials (see below)
├── app.py                 ← main Flask application
├── requirements.txt       ← Python dependencies
├── Readme.txt             ← this file
└── templates\
    ├── index.html         ← search form
    └── results.html       ← recommendations + history + “load more”

Setup
-----
1. Clone or copy this directory to your local machine.
2. In the project root, create a file named `.env` with these entries:
   
LASTFM_API_KEY=your_lastfm_api_key
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret


3. Install dependencies:
pip install -r requirements.txt

Running
-------
1. From the project root:
python app.py
2. Open your browser to `http://127.0.0.1:5000/`
3. Enter a song (e.g. `Drake - God’s Plan` or just `God’s Plan`) and hit Search.
4. See 3 recommendations immediately, view history in the sidebar.

Features
--------
- **Spotify-first** lookup with hybrid fallback to Last.fm.
- **Session history** of all past searches and their recommendations.
- **Progressive loading** of recommendations in batches of 3.
- **Blacklist** (“Artist Running Club”) exclusion in recommendations.
- Responsive, clean UI with a blurred background, sleek fonts, and cards.

Environment Variables
---------------------
Make sure you have valid API credentials in `.env`:
- `LASTFM_API_KEY`  
- `SPOTIFY_CLIENT_ID`  
- `SPOTIFY_CLIENT_SECRET`  
- (optional) `FLASK_SECRET_KEY` — used to sign session cookies.

Next Steps
----------
- Add direct Spotify track/album/artist links.
- Expand to album-based or artist-based recommendation pages.
- Persist history long-term (database) instead of session.
- User authentication to store favorites.

Enjoy exploring new music!


