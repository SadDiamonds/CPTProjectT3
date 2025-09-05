import sqlite3
import uuid
import hashlib
import re
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    g,
    session,
    current_app,
)
from datetime import datetime
from functools import wraps

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATABASE = "database/data_source.db"

# ----------------- ABOUT -----------------
@app.route("/about")
def about():
    return render_template("partials/about.html", user=current_user())


# ----------------- DB CONNECTION -----------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db:
        db.close()


# ----------------- UTILS -----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def current_user():
    if "user_id" in session:
        db = get_db()
        return db.execute(
            "SELECT * FROM Users WHERE user_id=?", (session["user_id"],)
        ).fetchone()
    return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for("signin_page"))
        return f(*args, **kwargs)

    return decorated_function


def opp_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" in session:
            return redirect(url_for("home_page"))
        return f(*args, **kwargs)

    return decorated_function


# ----------------- ROUTES -----------------
@app.route("/")
@opp_login_required
def landing_page():
    return render_template("landing.html")


@app.route("/home")
@login_required
def home_page():
    db = get_db()
    user = current_user()

    if user["role"] == "Donor":
        donations = db.execute(
            "SELECT * FROM Donations WHERE donor_id = ? ORDER BY donation_id DESC",
            (user["user_id"],),
        ).fetchall()
    else:
        donations = db.execute(
            """
            SELECT * FROM Donations 
            WHERE donation_id NOT IN (SELECT donation_id FROM Matches WHERE recipient_id = ?)
            ORDER BY donation_id DESC LIMIT 6
            """,
            (user["user_id"],),
        ).fetchall()

    return render_template("home.html", user=user, donations=donations)


# ----------------- SIGN UP -----------------
@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role = request.form.get("role")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup_page"))

        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address.", "error")
            return redirect(url_for("signup_page"))

        if not re.fullmatch(
            r'^(?=.*[A-Z])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$', password
        ):
            flash(
                "Password must be at least 8 chars, include uppercase & symbol.",
                "error",
            )
            return redirect(url_for("signup_page"))

        hashed = generate_password_hash(password)
        user_id = str(uuid.uuid4())
        creation_date = datetime.now().strftime("%d/%m/%y %H:%M:%S")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO Users (user_id, name, email, password, role, creation_date) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, email, hashed, role, creation_date),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Email already exists.", "error")
            return redirect(url_for("signup_page"))

        # If recipient, ask them to set preferences
        session["user_id"] = user_id
        if role == "Recipient":
            return redirect(url_for("preferences"))
        else:
            flash("Account created! Please sign in.", "success")
            return redirect(url_for("signin_page"))

    return render_template("partials/signup.html", user=current_user())


# ----------------- SIGN IN -----------------
@app.route("/signin", methods=["GET", "POST"])
def signin_page():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        user = db.execute("SELECT * FROM Users WHERE email=?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("home_page"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("signin_page"))

    return render_template("partials/signin.html", user=current_user())


# ----------------- SIGN OUT -----------------
@app.route("/signout")
def signout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("landing_page"))


# ----------------- ADD DONATION -----------------
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    user = current_user()
    if request.method == "POST":
        items = request.form.get("items")
        category = request.form.get("category")
        date_donated = datetime.now().strftime("%d/%m/%y %H:%M")

        image_file = request.files.get("image")
        image_filename = None
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(current_app.root_path, "static/uploads", filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image_file.save(image_path)
            image_filename = f"uploads/{filename}"

        db = get_db()
        db.execute(
            "INSERT INTO Donations (donor_id, category, items, date_donated, image_url) VALUES (?, ?, ?, ?, ?)",
            (user["user_id"], category, items, date_donated, image_filename),
        )
        db.commit()
        flash("Donation added!", "success")
        return redirect(url_for("home_page"))

    return render_template("partials/add.html", user=user)


# ----------------- PREFERENCES -----------------
@app.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    db = get_db()
    user = current_user()

    if request.method == "POST":
        categories = request.form.getlist("categories")
        db.execute("DELETE FROM Preferences WHERE user_id=?", (user["user_id"],))
        for c in categories:
            db.execute(
                "INSERT INTO Preferences (user_id, category) VALUES (?, ?)",
                (user["user_id"], c),
            )
        db.commit()
        flash("Preferences saved!", "success")
        return redirect(url_for("home_page"))

    user_prefs = db.execute(
        "SELECT category FROM Preferences WHERE user_id=?", (user["user_id"],)
    ).fetchall()
    return render_template(
        "preferences.html", user=user, user_prefs=[p["category"] for p in user_prefs]
    )


# ----------------- MATCHES -----------------
@app.route("/matches")
@login_required
def matches():
    db = get_db()
    user = current_user()

    if user["role"] == "Donor":
        matches = db.execute(
            """SELECT m.match_id, d.items, d.category, d.image_url, u.name as recipient_name, m.status
              FROM Matches m
              JOIN Donations d ON m.donation_id = d.donation_id
              JOIN Users u ON m.recipient_id = u.user_id
              WHERE m.donor_id = ?""",
            (user["user_id"],),
        ).fetchall()
    else:
        matches = db.execute(
            """SELECT m.match_id, d.items, d.category, d.image_url, u.name as donor_name, m.status
              FROM Matches m
              JOIN Donations d ON m.donation_id = d.donation_id
              JOIN Users u ON m.donor_id = u.user_id
              WHERE m.recipient_id = ?""",
            (user["user_id"],),
        ).fetchall()

    return render_template("partials/matches.html", matches=matches, user=user)


@app.route("/claim/<int:donation_id>", methods=["POST"])
@login_required
def claim_donation(donation_id):
    db = get_db()
    user = current_user()

    if user["role"] != "Recipient":
        flash("Only recipients can claim donations.", "error")
        return redirect(url_for("home_page"))

    donation = db.execute(
        "SELECT donor_id FROM Donations WHERE donation_id = ?", (donation_id,)
    ).fetchone()
    if not donation:
        flash("Donation not found.", "error")
        return redirect(url_for("home_page"))

    existing = db.execute(
        "SELECT * FROM Matches WHERE donation_id = ? AND recipient_id = ?",
        (donation_id, user["user_id"]),
    ).fetchone()
    if existing:
        flash("You’ve already requested this donation.", "warning")
        return redirect(url_for("home_page"))

    db.execute(
        "INSERT INTO Matches (donation_id, recipient_id, donor_id, status) VALUES (?, ?, ?, ?)",
        (donation_id, user["user_id"], donation["donor_id"], "Pending"),
    )
    db.commit()

    flash("You have requested this donation.", "success")
    return redirect(url_for("home_page"))


@app.route("/matches/<int:match_id>/<status>", methods=["POST"])
@login_required
def update_match_status(match_id, status):
    db = get_db()
    user = current_user()

    if user["role"] != "Donor":
        flash("Only donors can update match status.", "error")
        return redirect(url_for("matches"))

    db.execute(
        "UPDATE Matches SET status = ? WHERE match_id = ? AND donor_id = ?",
        (status, match_id, user["user_id"]),
    )
    db.commit()
    flash(f"Match {status}.", "success")
    return redirect(url_for("matches"))


# ----------------- RATINGS -----------------
@app.route("/rate/<int:match_id>", methods=["GET", "POST"])
@login_required
def rate(match_id):
    db = get_db()
    user = current_user()

    match = db.execute("SELECT * FROM Matches WHERE match_id=?", (match_id,)).fetchone()
    if not match or match["status"] != "Completed":
        flash("You can only rate completed matches.", "error")
        return redirect(url_for("matches"))

    if request.method == "POST":
        rating = int(request.form.get("rating"))
        comment = request.form.get("comment")
        rater_id = user["user_id"]
        rated_id = (
            match["donor_id"] if user["role"] == "Recipient" else match["recipient_id"]
        )

        db.execute(
            "INSERT INTO Ratings (match_id, rater_id, rated_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
            (match_id, rater_id, rated_id, rating, comment),
        )
        db.commit()
        flash("Rating submitted!", "success")
        return redirect(url_for("matches"))

    return render_template("partials/rate.html", match=match, user=user)


# ----------------- PROFILE + BADGES -----------------
@app.route("/profile/<user_id>")
@login_required
def profile(user_id):
    db = get_db()
    user_data = db.execute("SELECT * FROM Users WHERE user_id=?", (user_id,)).fetchone()
    ratings = db.execute(
        "SELECT r.rating, r.comment, u.name as rater_name FROM Ratings r JOIN Users u ON r.rater_id = u.user_id WHERE r.rated_id=?",
        (user_id,),
    ).fetchall()
    avg_rating = db.execute(
        "SELECT AVG(rating) as avg FROM Ratings WHERE rated_id=?", (user_id,)
    ).fetchone()["avg"]

    badges = db.execute(
        """
        SELECT b.* 
        FROM Badges b
        JOIN UserBadges ub ON b.badge_id = ub.badge_id
        WHERE ub.user_id=?
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "partials/profile.html",
        user=current_user(),
        profile_user=user_data,
        ratings=ratings,
        avg_rating=avg_rating or 0,
        badges=badges,
    )


# ----------------- DASHBOARD -----------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = current_user()

    if user["role"] == "Donor":
        stats = db.execute(
            """SELECT 
                  COUNT(*) as total_donations,
                  SUM(CASE WHEN donation_id IN (SELECT donation_id FROM Matches WHERE status = 'Completed') THEN 1 ELSE 0 END) as completed_donations,
                  SUM(CASE WHEN donation_id IN (SELECT donation_id FROM Matches WHERE status = 'Pending') THEN 1 ELSE 0 END) as pending_matches
              FROM Donations WHERE donor_id = ?""",
            (user["user_id"],),
        ).fetchone()
    else:
        stats = db.execute(
            """SELECT 
                  COUNT(*) as total_claims,
                  SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_claims,
                  SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_claims
              FROM Matches WHERE recipient_id = ?""",
            (user["user_id"],),
        ).fetchone()

    return render_template("partials/dashboard.html", user=user, stats=stats)


# ----------------- RUN -----------------
if __name__ == "__main__":
    app.run(debug=True)
