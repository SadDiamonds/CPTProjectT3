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
    jsonify,
)
from datetime import datetime
from functools import wraps


class User:
    def __init__(self, row):
        self.user_id = row["user_id"]
        self.name = row["name"]
        self.email = row["email"]
        self.password = row["password"]
        self.role = row["role"]
        self.creation_date = row["creation_date"]
        # Use .get with default
        self.notifications_enabled = (
            bool(row["notifications_enabled"])
            if "notifications_enabled" in row.keys()
            else False
        )
        self.public_profile = (
            bool(row["public_profile"]) if "public_profile" in row.keys() else False
        )

    # Save profile & preferences to DB
    def save(self):
        db = get_db()
        db.execute(
            """
            UPDATE Users SET name=?, email=?, password=?, notifications_enabled=?, public_profile=?
            WHERE user_id=?
            """,
            (
                self.name,
                self.email,
                self.password,
                int(self.notifications_enabled),
                int(self.public_profile),
                self.user_id,
            ),
        )
        db.commit()

    # Delete user
    def delete(self):
        db = get_db()
        db.execute("DELETE FROM Users WHERE user_id=?", (self.user_id,))
        db.commit()

AU_SUBURBS = {
    "Sydney": ["Bondi", "Manly", "Parramatta", "Chatswood"],
    "Melbourne": ["Fitzroy", "St Kilda", "South Yarra", "Brunswick"],
    "Brisbane": ["Fortitude Valley", "South Bank", "West End"],
    "Perth": ["Fremantle", "Subiaco", "Cottesloe"],
    "Adelaide": ["North Adelaide", "Glenelg", "Norwood"],
}

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
        row = db.execute(
            "SELECT * FROM Users WHERE user_id=?", (session["user_id"],)
        ).fetchone()
        if row:
            return User(row)
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
        return redirect(url_for("dashboard"))
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
                (user.user_id, token_hash, now, expires_at),
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
                "INSERT INTO Users (user_id, name, email, password, role, creation_date) VALUES (?, ?, ?, ?, ?), ?",
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


# ----------------- PREFERENCES (for new recipients) -----------------
@app.route("/preferences", methods=["GET", "POST"])
def preferences_page():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please sign in first.", "error")
        return redirect(url_for("signin_page"))

    db = get_db()

    if request.method == "POST":
        preferred_category = request.form.get("preferred_category")
        preferred_city = request.form.get("preferred_city")

        db.execute(
            "INSERT OR REPLACE INTO Preferences (user_id, preferred_category, preferred_city) VALUES (?, ?, ?)",
            (user_id, preferred_category, preferred_city),
        )
        db.commit()

        flash("Preferences saved!", "success")
        return redirect(url_for("donations_page"))

    return render_template("partials/preferences.html")


# ----------------- SIGN IN -----------------
@app.route("/signin", methods=["GET", "POST"])
def signin_page():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        row = db.execute("SELECT * FROM Users WHERE email=?", (email,)).fetchone()
        user = User(row) if row else None

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.user_id
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("signin_page"))

    return render_template("partials/signin.html", user=current_user())


# ----------------- MATCHES (list user's matches) -----------------
@app.route("/matches")
@login_required
def matches():
    db = get_db()
    user = current_user()

    if user.role == "Donor":
        # Donor: see matches for their donations
        matches = db.execute(
            """
            SELECT m.match_id, m.donation_id, m.status, m.donor_completed, m.recipient_completed,
                    d.items, d.category, d.image_url,
                    u.name AS recipient_name, m.recipient_id, m.donor_completed, m.recipient_completed
            FROM Matches m
            JOIN Donations d ON m.donation_id = d.donation_id
            JOIN Users u ON m.recipient_id = u.user_id
            WHERE d.donor_id = ?
            ORDER BY m.match_id DESC
            """,
            (user.user_id,),
        ).fetchall()
    else:
        # Recipient: see matches they requested
        matches = db.execute(
            """
            SELECT m.match_id, m.donation_id, m.status, m.donor_completed, m.recipient_completed,
                    d.items, d.category, d.image_url,
                    u.name AS donor_name, m.donor_id
            FROM Matches m
            JOIN Donations d ON m.donation_id = d.donation_id
            JOIN Users u ON d.donor_id = u.user_id
            WHERE m.recipient_id = ?
            ORDER BY m.match_id DESC
            """,
            (user.user_id,),
        ).fetchall()

    return render_template("partials/matches.html", matches=matches, user=user)


# ----------------- FIND MATCHES (for recipients to find donations) -----------------
@app.route("/find_matches", methods=["GET", "POST"])
@login_required
def find_matches():
    user = current_user()
    db = get_db()

    if user.role != "Recipient":
        flash("Only recipients can search for donations.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        donation_id = request.form.get("donation_id")
        if donation_id:
            db = get_db()
            db.execute(
                """
                INSERT INTO Matches (donation_id, recipient_id, status, donor_completed, recipient_completed)
                VALUES (?, ?, 'Pending', 0, 0)
                """,
                (donation_id, user.user_id)
            )
            db.commit()
            flash("Request sent!", "success")
            return redirect(url_for("matches"))

    # Show available donations
    donations = db.execute(
        """
        SELECT d.*, u.name AS donor_name
        FROM Donations d
        JOIN Users u ON d.donor_id = u.user_id
        WHERE d.donation_id NOT IN (
            SELECT donation_id FROM Matches WHERE recipient_id = ?
        )
        ORDER BY d.date_donated DESC
        """,
        (user.user_id,),
    ).fetchall()

    return render_template("partials/find_matches.html", matches=donations, user=user)


@app.route("/request_donation/<donation_id>", methods=["POST"])
@login_required
def request_donation(donation_id):
    user = current_user()
    if user.role != "Recipient":
        flash("Only recipients can request donations.", "error")
        return redirect(url_for("dashboard"))

    donation = db.execute(
        "SELECT * FROM Donations WHERE donation_id=?", (donation_id,)
    ).fetchone()

    db = get_db()
    db.execute(
        "UPDATE Donations SET status='Requested', recipient_id=? WHERE donation_id=?",
        (user.user_id, donation_id),
    )
    db.commit()

    create_notification(
        donation["donor_id"], 
        f"{user.name} requested your donation: {donation['items']}"
    )

    flash("Donation requested!", "success")
    return redirect(url_for("find_matches"))


@app.route("/my_donations")
@login_required
def my_donations():
    user = current_user()
    db = get_db()
    donations = db.execute(
        "SELECT d.*, u.name AS recipient_name FROM Donations d LEFT JOIN Users u ON d.recipient_id = u.user_id WHERE d.donor_id=?",
        (user.user_id,),
    ).fetchall()
    return render_template("partials/my_donations.html", donations=donations, user=user)


@app.route("/mark_donated/<donation_id>", methods=["POST"])
@login_required
def mark_donated(donation_id):
    user = current_user()
    db = get_db()
    db.execute(
        "UPDATE Donations SET status='Donated' WHERE donation_id=? AND donor_id=?",
        (donation_id, user.user_id),
    )
    db.commit()    
    donation = db.execute(
        "SELECT * FROM Donations WHERE donation_id=?", (donation_id,)
    ).fetchone()
    
    create_notification(
        donation["recipient_id"], 
        f"{user.name} marked your requested donation '{donation['items']}' as donated."
    )
    
    flash("Donation marked as donated!", "success")
    return redirect(url_for("my_donations"))


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
        donation_id = str(uuid.uuid4())  # Generate unique donation_id
        db.execute(
            "INSERT INTO Donations (donor_id, category, items, date_donated, image_url) VALUES (?, ?, ?, ?, ?)",
            (user.user_id, category, items, date_donated, image_filename),
        )
        db.commit()
        flash("Donation added!", "success")
        return redirect(url_for("dashboard"))

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

    if user.role != "Recipient":
        flash("Only recipients can claim donations.", "error")
        return redirect(url_for("dashboard"))

    donation = db.execute(
        "SELECT donor_id FROM Donations WHERE donation_id = ?", (donation_id,)
    ).fetchone()
    if not donation:
        flash("Donation not found.", "error")
        return redirect(url_for("dashboard"))

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
        (donation_id, user.user_id, donation["donor_id"], "Pending", 0, 0),
    )
    db.commit()

    flash("You have requested this donation.", "success")
    return redirect(url_for("matches"))


# ----------------- UPDATE MATCH STATUS (Donor: Accept / Reject) -----------------
@app.route("/update_match_status/<int:match_id>/<status>", methods=["POST"])
@login_required
def update_match_status(match_id, status):
    db = get_db()
    user = current_user()

    # Only donor can accept/reject
    if user.role != "Donor":
        flash("Unauthorized action.", "error")
        return redirect(url_for("matches"))

    db.execute("UPDATE Matches SET status = ? WHERE match_id = ?", (status, match_id))
    db.commit()
    flash(f"Match {status.lower()}!", "success")
    return redirect(url_for("matches"))


# ----------------- MARK AS COMPLETED (either side) -----------------
@app.route("/complete_match/<int:match_id>", methods=["POST"])
@login_required
def complete_match(match_id):
    db = get_db()
    user = current_user()

    match = db.execute(
        "SELECT * FROM Matches WHERE match_id = ?", (match_id,)
    ).fetchone()

    if not match:
        flash("Match not found.", "error")
        return redirect(url_for("matches"))

    if user.role == "Donor" and not match["donor_completed"]:
        db.execute(
            "UPDATE Matches SET donor_completed = 1 WHERE match_id = ?", (match_id,)
        )
    elif user.role == "Recipient" and not match["recipient_completed"]:
        db.execute(
            "UPDATE Matches SET recipient_completed = 1 WHERE match_id = ?", (match_id,)
        )
    else:
        flash("Nothing to update.", "info")
        return redirect(url_for("matches"))

    # If both completed, mark status as Completed
    updated_match = db.execute(
        "SELECT donor_completed, recipient_completed FROM Matches WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if updated_match["donor_completed"] and updated_match["recipient_completed"]:
        db.execute(
            "UPDATE Matches SET status = 'Completed' WHERE match_id = ?", (match_id,)
        )

    db.commit()
    flash("Match updated!", "success")
    return redirect(url_for("matches"))


# ---------------- review (recipient leaves review for donor) -----------------
@app.route("/leave_review/<donation_id>", methods=["POST"])
@login_required
def leave_review(donation_id):
    user = current_user()
    review_text = request.form.get("review", "").strip()

    if not review_text:
        flash("Review cannot be empty.", "error")
        return redirect(url_for("my_requests"))

    db = get_db()
    # Make sure the donation is actually completed for this recipient
    donation = db.execute(
        "SELECT * FROM Donations WHERE donation_id=? AND recipient_id=? AND status='Donated'",
        (donation_id, user.user_id),
    ).fetchone()

    donationn = db.execute(
        "SELECT * FROM Donations WHERE donation_id=?", (donation_id,)
    ).fetchone()

    if not donation:
        flash("You cannot review this donation.", "error")
        return redirect(url_for("my_requests"))

    # Save review
    db.execute(
        "UPDATE Donations SET review=? WHERE donation_id=?", (review_text, donation_id)
    )
    db.commit()

    create_notification(
        donationn["donor_id"],
        f"{user.name} left a review for donation: {donation['items']}",
    )

    flash("Review submitted! Thank you for your feedback.", "success")
    return redirect(url_for("my_requests"))


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
    avg_row = db.execute(
        "SELECT AVG(rating) as avg FROM Ratings WHERE rated_id=?", (user_id,)
    ).fetchone()

    if avg_row and avg_row["avg"] is not None:
        avg_rating = round(avg_row["avg"], 1)
    else:
        avg_rating = 0

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

    # Stats and recent activity
    if user.role == "Donor":
        # Count total donations
        stats = db.execute(
            """
            SELECT 
                COUNT(*) AS total_donations,
                SUM(CASE WHEN status = 'Requested' THEN 1 ELSE 0 END) AS requested_donations,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS Completed_donations
            FROM Donations
            WHERE donor_id = ?
            """,
            (user.user_id,),
        ).fetchone()

        # Last 5 donations with status
        recent = db.execute(
            """
            SELECT items, COALESCE(status, 'Available') AS status
            FROM Donations
            WHERE donor_id = ?
            ORDER BY donation_id DESC
            LIMIT 5
            """,
            (user.user_id,),
        ).fetchall()

    else:  # Recipient
        stats = db.execute(
            """
            SELECT 
                COUNT(*) AS total_claims,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_claims,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending_claims
            FROM Donations
            WHERE claimed_by = ?
            """,
            (user.user_id,),
        ).fetchone()

        # Last 5 requests
        recent = db.execute(
            """
            SELECT items, status
            FROM Donations
            WHERE claimed_by = ?
            ORDER BY donation_id DESC
            LIMIT 5
            """,
            (user.user_id,),
        ).fetchall()

    # Account creation date
    creation_str = ""
    try:
        dt = datetime.strptime(user.creation_date.strip(), "%d/%m/%y %H:%M:%S")
        creation_str = dt.strftime("%d %B %Y")
    except Exception:
        creation_str = user.creation_date if hasattr(user, "creation_date") else ""

    # Average rating
    avg_row = db.execute(
        "SELECT AVG(rating) AS avg FROM Ratings WHERE rated_id=?", (user.user_id,)
    ).fetchone()
    avg_rating = (
        round(avg_row["avg"], 1) if avg_row and avg_row["avg"] is not None else 0
    )

    return render_template(
        "partials/dashboard.html",
        user=user,
        stats=stats,
        recent=recent,
        creation_str=creation_str,
        avg_rating=avg_rating,
    )


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


# ----------------- Settings ------------------
@app.route("/settings")
@login_required
def settings():
    user = current_user()    
    db= get_db()
    saved_categories = []
    if user.role == "Recipient":
        rows = db.execute(
            "SELECT category FROM Preferences WHERE user_id = ?",
            (user.user_id,),
        ).fetchall()
        saved_categories = [row["category"] for row in rows]
    return render_template("partials/settings.html", user=user, saved_categories=saved_categories)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    user = current_user()
    name = request.form.get("name")
    email = request.form.get("email")

    if not name or not email:
        flash("Name and Email cannot be empty.", "error")
        return redirect(url_for("settings"))

    user.name = name
    user.email = email
    user.save()  # save to DB
    flash("Profile updated successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/change_password", methods=["POST"])
def change_password():
    user = current_user()
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not check_password_hash(user.password, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("settings"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("settings"))

    user.password = generate_password_hash(new_password)
    user.save()
    flash("Password updated successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/update_preferences", methods=["POST"])
def update_preferences():
    user = current_user()

    # Save normal preferences
    user.notifications_enabled = "notifications" in request.form
    user.public_profile = "public_profile" in request.form
    user.save()

    db = get_db()

    # Only apply category preferences for Recipients
    if user.role == "Recipient":
        selected_categories = request.form.getlist("categories")

        # Clear old preferences
        db.execute("DELETE FROM Preferences WHERE user_id = ?", (user.user_id,))

        # Save new selected ones
        for category in selected_categories:
            db.execute(
                "INSERT INTO Preferences (user_id, category) VALUES (?, ?)",
                (user.user_id, category),
            )

        db.commit()

    flash("Preferences updated!", "success")
    return redirect(url_for("settings"))


@app.route("/delete_account", methods=["POST"])
def delete_account():
    user = current_user()
    # Optional: log them out first
    session.clear()
    user.delete()  # remove from DB
    flash("Your account has been deleted.", "success")
    return redirect(url_for("landing_page"))


# ----------------- Notification ------------------
@app.context_processor
def inject_notifications():
    user = current_user()
    notifications = []
    unread_count = 0
    if user:
        db = get_db()
        notifications = db.execute(
            "SELECT * FROM Notifications WHERE user_id=? ORDER BY created_at DESC",
            (user.user_id,),
        ).fetchall()
        unread_count = sum(1 for n in notifications if n["read"] == 0)
    return dict(notifications=notifications, notif_count=unread_count)


@app.route("/notifications")
def get_notifications():
    user = current_user()
    if not user:
        return jsonify([]), 403
    db = get_db()
    notifications = db.execute(
        "SELECT id, message, created_at, read FROM Notifications WHERE user_id=? ORDER BY created_at DESC",
        (user.user_id,),
    ).fetchall()

    return jsonify(
        [
            {
                "id": n["id"],
                "message": n["message"],
                "created_at": n["created_at"],
                "read": n["read"],
            }
            for n in notifications
        ]
    )


def create_notification(user_id, message):
    db = get_db()
    notif_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO Notifications (id, user_id, message, created_at) VALUES (?, ?, ?, ?)",
        (notif_id, user_id, message, datetime.now().isoformat()),
    )
    db.commit()


@app.route("/notifications/mark_read", methods=["POST"])
def mark_notifications_read():
    user = current_user()
    if not user:
        return "", 403
    db = get_db()
    db.execute("UPDATE Notifications SET read=1 WHERE user_id=?", (user.user_id,))
    db.commit()
    return "", 204


@app.route("/my_requests")
@login_required
def my_requests():
    user = current_user()
    db = get_db()

    if user.role != "Recipient":
        flash("Only recipients can view their requests.", "error")
        return redirect(url_for("dashboard"))

    requests = db.execute(
        """
        SELECT d.*, u.name AS donor_name
        FROM Donations d
        LEFT JOIN Users u ON d.donor_id = u.user_id
        WHERE d.recipient_id = ?
        ORDER BY d.donation_id DESC
        """,
        (user.user_id,),
    ).fetchall()

    return render_template("partials/my_requests.html", requests=requests, user=user)


# ----------------- run -----------------
if __name__ == "__main__":
    app.run(debug=True)
