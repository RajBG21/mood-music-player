# app.py — PythonAnywhere-ready (uses sqlite3, safe filesystem sessions)

import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash, g
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from spotify import get_tracks_for_mood
import sqlite3

# Load environment variables from .env if present
load_dotenv()

# -------------------------
# App setup
# -------------------------
app = Flask(__name__, instance_relative_config=True)

# Secret key
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

app.config["TEMPLATES_AUTO_RELOAD"] = True

# Database file path (absolute, inside the project directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "moods.db")
app.config["DATABASE"] = DATABASE

# -------------------------
# Session config (filesystem)
# -------------------------
# Put session files in the instance folder (not in your repo). This avoids
# accidentally committing session files (like you had previously).
SESSION_DIR = os.path.join(app.instance_path, "flask_session")
os.makedirs(SESSION_DIR, exist_ok=True)

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = SESSION_DIR
app.config["SESSION_PERMANENT"] = False

# Initialize server-side sessions
Session(app)

# -------------------------
# Database helpers
# -------------------------
def get_db():
    """
    Return a sqlite3 connection stored on flask.g for the request.
    """
    if "db_conn" not in g:
        conn = sqlite3.connect(app.config["DATABASE"], check_same_thread=False)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn

@app.teardown_appcontext
def close_db(exception):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()

def init_db_schema():
    """
    Create tables if they don't exist yet.
    This is safe to call on startup.
    """
    conn = sqlite3.connect(app.config["DATABASE"])
    cur = conn.cursor()

    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL
        )
        """
    )

    # Moods table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood TEXT NOT NULL,
            note TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()

# Ensure DB schema exists on import/startup
init_db_schema()

# -------------------------
# Helpers
# -------------------------
def login_required(f):
    """Login decorator"""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in first.")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    return render_template("index.html", current_year=datetime.now().year)

# -------- Authentication --------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    # Validation
    if not username or not password or not confirmation:
        flash("Please fill all fields.")
        return redirect("/register")

    if password != confirmation:
        flash("Passwords do not match.")
        return redirect("/register")

    db = get_db()

    # Check if username exists
    cur = db.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    if user:
        flash("Username already taken.")
        return redirect("/register")

    # Store user
    hash_pw = generate_password_hash(password)
    db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hash_pw))
    db.commit()

    flash("Registered successfully! Please log in.")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username")
    password = request.form.get("password")

    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()

    if not user or not check_password_hash(user["hash"], password):
        flash("Invalid username or password.")
        return redirect("/login")

    session["user_id"] = user["id"]
    flash("Logged in successfully!")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out!")
    return redirect("/")

# -------- Mood Logging --------
@app.route("/mood", methods=["GET", "POST"])
@login_required
def mood():
    if request.method == "GET":
        return render_template("mood.html")

    mood_value = request.form.get("mood")
    note = request.form.get("note")

    if not mood_value:
        flash("Please select a mood.")
        return redirect("/mood")

    db = get_db()
    timestamp = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO moods (user_id, mood, note, timestamp) VALUES (?, ?, ?, ?)",
        (session["user_id"], mood_value, note, timestamp)
    )
    db.commit()

    flash("Mood logged!")
    return redirect("/playlist?mood=" + mood_value)

# -------- Playlist Page --------
@app.route("/playlist")
@login_required
def playlist():
    mood_value = request.args.get("mood")
    if mood_value is None:
        return redirect("/")

    # Fetch songs from Spotify API (your spotify.py)
    songs = []
    try:
        songs = get_tracks_for_mood(mood_value)
    except Exception as e:
        # Log the error server-side if you want (print will go to error log)
        print("Spotify error:", e)

    # If Spotify fails or returns nothing
    if not songs:
        flash("Couldn't fetch Spotify data. Showing default playlist.")
        songs = [
            {"title": "Default Song", "artist": "Unknown", "url": "https://open.spotify.com/"}
        ]

    return render_template("playlist.html", mood=mood_value, songs=songs)

# -------- Dashboard --------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_db()

    mood_cur = db.execute(
        "SELECT mood, timestamp FROM moods WHERE user_id = ? ORDER BY datetime(timestamp)",
        (user_id,)
    )
    mood_data = mood_cur.fetchall()

    recent_cur = db.execute(
        "SELECT mood, timestamp FROM moods WHERE user_id = ? ORDER BY datetime(timestamp) DESC LIMIT 5",
        (user_id,)
    )
    recent = recent_cur.fetchall()

    if not mood_data:
        return render_template("dashboard.html", mood_data=None)

    # Data for line chart
    labels = [entry["timestamp"] for entry in mood_data]
    values = []

    mood_map = {"happy": 5, "energetic": 4, "calm": 3, "stressed": 2, "sad": 1}
    for entry in mood_data:
        values.append(mood_map.get(entry["mood"], 0))

    # Pie chart aggregation
    grouped = {}
    for entry in mood_data:
        m = entry["mood"]
        grouped[m] = grouped.get(m, 0) + 1

    freq_labels = list(grouped.keys())
    freq_values = list(grouped.values())

    return render_template(
        "dashboard.html",
        mood_data=mood_data,
        recent=recent,
        labels=labels,
        values=values,
        freq_labels=freq_labels,
        freq_values=freq_values
    )

# -------- Error Handler --------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", message="Page not found."), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template("error.html", message="Something went wrong."), 500

# Run app locally for development
if __name__ == "__main__":
    app.run(debug=True)
