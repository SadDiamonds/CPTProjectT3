import sqlite3
import uuid
import hashlib
import re
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, current_app
from datetime import datetime
from functools import wraps

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATABASE = "database/data_source.db"


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
      return redirect(url_for('home_page'))
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
    user = db.execute(
        "SELECT * FROM Users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()

    if user["role"] == "Donor":
        donations = db.execute(
            "SELECT * FROM Donations WHERE donor_id = ? ORDER BY date_donated DESC LIMIT 3",
            (user["user_id"],),
        ).fetchall()
    else:  # recipient
        donations = db.execute(
            "SELECT * FROM Donations WHERE donation_id NOT IN (SELECT donation_id FROM Matches WHERE recipient_id = ?) ORDER BY date_donated DESC LIMIT 3",
            (user["user_id"],),
        ).fetchall()
    return render_template("home.html", user=user, donations=donations)


@app.route("/about")
def about():
    return render_template("partials/about.html", user=current_user())


# ----------------- SIGN UP -----------------
@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role = request.form.get("role")

        # Confirm passwords match
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup_page"))

        # Validate email
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email address.", "error")
            return redirect(url_for("signup_page"))

        # Validate password: 8+ chars, 1 uppercase, 1 symbol
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
        creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        user = db.execute(
            "SELECT * FROM Users WHERE email=?", (email,)
        ).fetchone()

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
    user = current_user()  # get logged in user info

    if request.method == "POST":
        items = request.form.get("items")
        category = request.form.get("category")
        date_donated = datetime.now().strftime("%d/%m/%y %H:%M")

        # Handle image
        image_file = request.files.get("image")
        image_filename = None
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(current_app.root_path, "static/uploads", filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image_file.save(image_path)
            image_filename = f"uploads/{filename}"  # relative to /static

        db = get_db()
        db.execute(
            "INSERT INTO Donations (donor_id, category, items, date_donated, image_url) VALUES (?, ?, ?, ?, ?)",
            (user["user_id"], category, items, date_donated, image_filename),
        )
        db.commit()
        flash("Donation added!", "success")
        return redirect(url_for("home_page"))

    return render_template("partials/add.html", user=user)


# ----------------- VIEW MATCHES -----------------
@app.route("/matches")
def matches():
    user = current_user()
    if not user:
        flash("Please sign in to view matches.", "error")
        return redirect(url_for("signin_page"))

    db = get_db()
    matches = db.execute(
        """
        SELECT m.match_id, d.items, d.category, u.name as recipient_name, m.status
        FROM Matches m
        JOIN Donations d ON m.donation_id = d.donation_id
        JOIN Recipients r ON m.recipient_id = r.recipient_id
        WHERE m.status='Pending'
    """
    ).fetchall()

    return render_template("partials/matches.html", matches=matches, user=user)


@app.context_processor
def inject_user():
    return dict(user=session.get("user_id"))


# ----------------- RUN APP -----------------
if __name__ == "__main__":
    app.run(debug=True)
