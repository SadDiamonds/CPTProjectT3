import sqlite3
import uuid
import hashlib
import re
import os
import secrets
import time
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

TOKEN_TTL = 3600

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


# ----------------- UTIL / AUTH -----------------

def allowed_file(filename): 
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

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


@app.route("/")
def root_redirect():
    if "user_id" in session:
        return redirect(url_for("donations_page"))
    else:
        return redirect(url_for("landing_page"))


def opp_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" in session:
            return redirect(url_for("home_page"))
        return f(*args, **kwargs)

    return decorated_function


# ------------------- FORGOT PASSWORD -------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM Users WHERE email=?", (email,)).fetchone()

        if user:
            # create secure random token
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            now = int(time.time())
            expires_at = now + TOKEN_TTL

            db.execute(
                "INSERT INTO PasswordResetTokens (user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (user["user_id"], token_hash, now, expires_at),
            )
            db.commit()

            reset_url = url_for("reset_password", token=raw_token, _external=True)
            # TODO: send this link via email (replace with real SMTP)
            print("Password reset link:", reset_url)

        flash("If the account exists, we sent a reset link.", "info")
        return redirect(url_for("signin_page"))

    return render_template("partials/forgot.html", user=current_user())


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    db = get_db()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())

    record = db.execute(
        "SELECT * FROM PasswordResetTokens WHERE token_hash=? AND used=0 AND expires_at>?",
        (token_hash, now),
    ).fetchone()

    if not record:
        flash("Invalid or expired link.", "error")
        return redirect(url_for("signin_page"))

    if request.method == "POST":
        new_pw = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if new_pw != confirm:
            flash("Passwords do not match.", "error")
            return redirect(request.url)

        if not re.fullmatch(r'^(?=.*[A-Z])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$', new_pw):
            flash(
                "Password must be at least 8 chars, include uppercase & symbol.",
                "error",
            )
            return redirect(request.url)

        hashed = generate_password_hash(new_pw)
        db.execute(
            "UPDATE Users SET password=? WHERE user_id=?", (hashed, record["user_id"])
        )
        db.execute("UPDATE PasswordResetTokens SET used=1 WHERE id=?", (record["id"],))
        db.commit()

        flash("Password has been reset. You can now sign in.", "success")
        return redirect(url_for("signin_page"))

    return render_template("partials/reset.html", user=current_user())


# ------------------ SIGN UP -----------------
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
            return redirect(url_for("donations_page"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("signin_page"))

    return render_template("partials/signin.html", user=current_user())


# ----------------- HOME (donations listing) -----------------
@app.route("/home")
@login_required
def home_page():
    db = get_db()
    user = current_user()
    
    search = request.args.get("q", "").strip()
    search_pattern = f"%{search}%" if search else "%"

    if user["role"] == "Donor":
        donations = db.execute(
            "SELECT * FROM Donations WHERE donor_id = ? AND (items LIKE ? OR category LIKE ?) ORDER BY donation_id DESC",
            (user["user_id"],search_pattern, search_pattern),
        ).fetchall()
    else:
        # For recipients: show donations that are NOT already claimed in matches_ex
        donations = db.execute(
            """
            SELECT * FROM Donations d
            WHERE d.donation_id NOT IN (SELECT donation_id FROM matches_ex)
            AND (d.items LIKE ? OR d.category LIKE ?)
            ORDER BY d.donation_id DESC
            LIMIT 6
            """,
            (search_pattern, search_pattern),
        ).fetchall()

    return render_template("home.html", user=user, donations=donations, search=search)


# ----------------- MATCHES (list user's matches) -----------------
@app.route("/matches")
@login_required
def matches():
    db = get_db()
    user = current_user()

    if user["role"] == "Donor":
        # Donor: show all matches where donor_id = current user
        matches = db.execute(
            """
            SELECT m.match_id, m.donation_id, m.status, m.donor_completed, m.recipient_completed,
                d.items, d.category, d.image_url,
                u.name as recipient_name, m.donor_id, m.recipient_id,
                r.rating AS user_rating, r.comment AS user_comment
            FROM matches_ex m
            JOIN Donations d ON m.donation_id = d.donation_id
            JOIN Users u ON m.recipient_id = u.user_id
            LEFT JOIN Ratings r 
                ON r.match_id = m.match_id AND r.rater_id = ?
            WHERE m.donor_id = ?
            ORDER BY m.match_id DESC
        """,
            (user["user_id"], user["user_id"]),
        ).fetchall()

    else:
        # Recipient: show matches where recipient_id = current user AND status != 'Rejected'
        matches = db.execute(
            """
            SELECT m.match_id, m.donation_id, m.status, m.donor_completed, m.recipient_completed,
                d.items, d.category, d.image_url,
                u.name as donor_name, m.donor_id, m.recipient_id,
                r.rating AS user_rating, r.comment AS user_comment
            FROM matches_ex m
            JOIN Donations d ON m.donation_id = d.donation_id
            JOIN Users u ON m.donor_id = u.user_id
            LEFT JOIN Ratings r 
                ON r.match_id = m.match_id AND r.rater_id = ?
            WHERE m.recipient_id = ? AND m.status != 'Rejected'
            ORDER BY m.match_id DESC
        """,
            (user["user_id"], user["user_id"]),
        ).fetchall()

    return render_template("partials/matches.html", matches=matches, user=user)


# ----------------- ABOUT -----------------
@app.route("/about", endpoint="about")
def about():
    return render_template("partials/about.html", user=current_user())

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
            db.execute( "INSERT INTO Donations (donor_id, category, items, date_donated, image_url) VALUES (?, ?, ?, ?, ?)", (user["user_id"], category, items, date_donated, image_filename), ) 
            db.commit() 
            flash("Donation added!", "success") 
        return redirect(url_for("home_page")) 
    return render_template("partials/add.html", user=user)
# uhhhh

# ------------------- SIGN OUT -------------------
@app.route("/signout") 
def signout(): 
    session.clear() 
    flash("You have been signed out.", "info") 
    return redirect(url_for("landing_page"))


@app.route("/landing")
@opp_login_required
def landing_page():
    return render_template("landing.html")


# ----------------- CLAIM recipient requests a donation) -----------------
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

    # Check existing in matches_ex (use matches_ex table)
    existing = db.execute(
        "SELECT * FROM matches_ex WHERE donation_id = ?",
        (donation_id,),
    ).fetchone()
    if existing:
        flash("This donation has already been requested/claimed.", "warning")
        return redirect(url_for("home_page"))

    # Insert into matches_ex
    db.execute(
        "INSERT INTO matches_ex (donation_id, recipient_id, donor_id, status, donor_completed, recipient_completed) VALUES (?, ?, ?, ?, ?, ?)",
        (donation_id, user["user_id"], donation["donor_id"], "Pending", 0, 0),
    )
    db.commit()

    flash("You have requested this donation.", "success")
    return redirect(url_for("matches"))


# ----------------- UPDATE MATCH STATUS (Donor: Accept / Reject) -----------------
@app.route("/matches/<int:match_id>/<status>", methods=["POST"])
@login_required
def update_match_status(match_id, status):
    db = get_db()
    user = current_user()

    if user["role"] != "Donor":
        flash("Only donors can update match status.", "error")
        return redirect(url_for("matches"))

    # Only update matches_ex
    db.execute(
        "UPDATE matches_ex SET status = ? WHERE match_id = ? AND donor_id = ?",
        (status, match_id, user["user_id"]),
    )
    db.commit()

    # If rejected, you might want to keep or delete the match row; currently we keep it but status changes.
    flash(f"Match {status}.", "success")
    return redirect(url_for("matches"))


# ----------------- MARK AS COMPLETED (either side) -----------------
@app.route("/matches/<int:match_id>/complete", methods=["POST"])
@login_required
def complete_match(match_id):
    db = get_db()
    user = current_user()

    match = db.execute(
        "SELECT * FROM matches_ex WHERE match_id = ?", (match_id,)
    ).fetchone()
    if not match:
        flash("Match not found.", "error")
        return redirect(url_for("matches"))

    # Only donor or recipient may mark completed
    if user["user_id"] == match["donor_id"]:
        db.execute(
            "UPDATE matches_ex SET donor_completed = 1 WHERE match_id = ?", (match_id,)
        )
    elif user["user_id"] == match["recipient_id"]:
        db.execute(
            "UPDATE matches_ex SET recipient_completed = 1 WHERE match_id = ?",
            (match_id,),
        )
    else:
        flash("Unauthorized action.", "error")
        return redirect(url_for("matches"))

    # Re-fetch and if both confirmed => set status to Completed
    match = db.execute(
        "SELECT donor_completed, recipient_completed FROM matches_ex WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if match and match["donor_completed"] and match["recipient_completed"]:
        db.execute(
            "UPDATE matches_ex SET status = 'Completed' WHERE match_id = ?", (match_id,)
        )

    db.commit()
    flash("Marked as completed.", "success")
    return redirect(url_for("matches"))


# ----------------- RATE (only for completed matches) -----------------
@app.route("/rate/<int:match_id>", methods=["GET", "POST"])
@login_required
def rate(match_id):
    db = get_db()
    user = current_user()

    match = db.execute(
        "SELECT * FROM matches_ex WHERE match_id=?", (match_id,)
    ).fetchone()
    if not match or (match["status"] or "").lower() != "completed":
        flash("You can only rate completed matches.", "error")
        return redirect(url_for("matches"))

    # Prevent duplicate rating by same rater for this match
    already = db.execute(
        "SELECT * FROM Ratings WHERE match_id = ? AND rater_id = ?",
        (match_id, user["user_id"]),
    ).fetchone()
    if already:
        flash("You have already rated this match.", "warning")
        return redirect(url_for("matches"))

    if request.method == "POST":
        try:
            rating = int(request.form.get("rating"))
            comment = request.form.get("comment") or ""
            rater_id = user["user_id"]
            # who is being rated?
            rated_id = (
                match["donor_id"]
                if user["role"] == "Recipient"
                else match["recipient_id"]
            )

            db.execute(
                "INSERT INTO Ratings (match_id, rater_id, rated_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
                (match_id, rater_id, rated_id, rating, comment),
            )
            db.commit()
            flash("Rating submitted!", "success")
            return redirect(url_for("matches"))
        except Exception as e:
            flash("Failed to submit rating.", "error")
            return redirect(url_for("rate", match_id=match_id))

    return render_template("partials/rate.html", match=match, user=user)


# ----------------- PROFILE (unchanged but ensure current_user passed) -----------------
@app.route("/profile/<user_id>", methods=["GET"])
@login_required
def profile(user_id):
    db = get_db()
    profile_user = db.execute(
        "SELECT * FROM Users WHERE user_id=?", (user_id,)
    ).fetchone()
    if not profile_user:
        flash("User not found.", "error")
        return redirect(url_for("home_page"))

    # Parse creation date if stored as DD/MM/YYYY HH:MM:SS
    created_str = getattr(profile_user, "creation_date", "")
    try:
        created_dt = datetime.strptime(created_str, "%d/%m/%Y %H:%M:%S")
        created_str = created_dt.strftime("%d %B %Y, %H:%M")
    except Exception:
        pass

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
        profile_user=profile_user,
        ratings=ratings,
        creation_str=created_str,
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
                    SUM(CASE WHEN donation_id IN (SELECT donation_id FROM matches_ex WHERE status = 'Completed') THEN 1 ELSE 0 END) as completed_donations,
                    SUM(CASE WHEN donation_id IN (SELECT donation_id FROM matches_ex WHERE status = 'Pending') THEN 1 ELSE 0 END) as pending_matches
            FROM Donations WHERE donor_id = ?""",
            (user["user_id"],),
        ).fetchone()
    else:
        stats = db.execute(
            """SELECT 
                    COUNT(*) as total_claims,
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_claims,
                    SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_claims
            FROM matches_ex WHERE recipient_id = ?""",
            (user["user_id"],),
        ).fetchone()

    return render_template("partials/dashboard.html", user=user, stats=stats)


# ----------------- DONATION PAGE -----------------
@app.route("/donations")
@login_required
def donations_page():
    db = get_db()
    user = current_user()

    search = request.args.get("q", "")
    category = request.args.get("category", "")

    query = "SELECT * FROM Donations"
    conditions = []
    params = []

    # 🔍 Apply search
    if search:
        conditions.append("(items LIKE ? OR category LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    # 📂 Apply category filter
    if category:
        conditions.append("category = ?")
        params.append(category)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY donation_id DESC"

    donations = db.execute(query, tuple(params)).fetchall()

    # get distinct categories for dropdown
    categories = db.execute("SELECT DISTINCT category FROM Donations").fetchall()

    return render_template(
        "donations.html",
        user=user,
        donations=donations,
        search=search,
        category=category,
        categories=[c["category"] for c in categories],
    )


# ----------------- run -----------------
if __name__ == "__main__":
    app.run(debug=True)
