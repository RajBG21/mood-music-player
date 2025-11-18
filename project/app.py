import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from cs50 import SQL
from datetime import datetime
from spotify import get_tracks_for_mood

load_dotenv()

# Configure Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Session config
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Database
db = SQL("sqlite:///moods.db")


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

    # Check if username exists
    user = db.execute("SELECT * FROM users WHERE username = ?", username)
    if user:
        flash("Username already taken.")
        return redirect("/register")

    # Store user
    hash_pw = generate_password_hash(password)
    db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_pw)

    flash("Registered successfully! Please log in.")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username")
    password = request.form.get("password")

    user = db.execute("SELECT * FROM users WHERE username = ?", username)
    if not user or not check_password_hash(user[0]["hash"], password):
        flash("Invalid username or password.")
        return redirect("/login")

    session["user_id"] = user[0]["id"]
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

    mood = request.form.get("mood")
    note = request.form.get("note")

    if not mood:
        flash("Please select a mood.")
        return redirect("/mood")

    db.execute(
        "INSERT INTO moods (user_id, mood, note, timestamp) VALUES (?, ?, ?, ?)",
        session["user_id"], mood, note, datetime.now()
    )

    flash("Mood logged!")
    return redirect("/playlist?mood=" + mood)


# -------- Playlist Page --------
@app.route("/playlist")
@login_required
def playlist():
    mood = request.args.get("mood")
    if mood is None:
        return redirect("/")


    # Fetch songs from Spotify API
    songs = get_tracks_for_mood(mood)

    # If Spotify fails or returns nothing
    if not songs:
        flash("Couldn't fetch Spotify data. Showing default playlist.")
        songs = [
            {"title": "Default Song", "artist": "Unknown", "url": "https://open.spotify.com/"}
        ]

    return render_template("playlist.html", mood=mood, songs=songs)



# -------- Dashboard --------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    mood_data = db.execute(
        "SELECT mood, timestamp FROM moods WHERE user_id = ? ORDER BY timestamp", user_id
    )
    recent = db.execute(
        "SELECT mood, timestamp FROM moods WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5",
        user_id
    )

    if not mood_data:
        return render_template("dashboard.html", mood_data=None)

    # Data for line chart
    labels = [entry["timestamp"] for entry in mood_data]
    values = []

    mood_map = {"happy": 5, "energetic": 4, "calm": 3, "stressed": 2, "sad": 1}
    for entry in mood_data:
        values.append(mood_map.get(entry["mood"], 0))

    # Pie chart aggregation
    freq_labels = []
    freq_values = []

    grouped = {}
    for entry in mood_data:
        m = entry["mood"]
        grouped[m] = grouped.get(m, 0) + 1

    for k, v in grouped.items():
        freq_labels.append(k)
        freq_values.append(v)

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


# Run app
if __name__ == "__main__":
    app.run(debug=True)

