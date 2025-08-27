import sqlite3
import uuid
import hashlib
import re
from flask import Flask, render_template, request, redirect, url_for, flash, g, session
from datetime import datetime

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
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def current_user():
    if "user_id" in session:
        db = get_db()
        return db.execute(
            "SELECT * FROM Users WHERE user_id=?", (session["user_id"],)
        ).fetchone()
    return None


# ----------------- ROUTES -----------------


@app.route("/")
def landing_page():
    return render_template("landing.html")


@app.route("/home")
def home_page():
    db = get_db()
    donations = db.execute(
        "SELECT donation_id, category, items, date_donated FROM Donations ORDER BY date_donated DESC LIMIT 3"
    ).fetchall()
    return render_template("home.html", donations=donations)


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

        db = get_db()
        user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        try:
            db.execute(
                "INSERT INTO Users (user_id, name, email, password, creation_date, role) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, email, hashed, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "none"),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("Email already exists", "error")
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
        hashed = hash_password(password)

        db = get_db()
        user = db.execute(
            "SELECT * FROM Users WHERE email=? AND password=?", (email, hashed)
        ).fetchone()

        if user:
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
    session.pop("user_id", None)
    flash("Signed out successfully.", "success")
    return redirect(url_for("signin_page"))


# ----------------- ADD DONATION -----------------
@app.route("/add", methods=["GET", "POST"])
def add():
    user = current_user()
    if not user:
        flash("Please sign in to add a donation.", "error")
        return redirect(url_for("signin_page"))

    if request.method == "POST":
        items = request.form.get("items")
        category = request.form.get("category")
        date_donated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # current timestamp

        db = get_db()
        db.execute(
            "INSERT INTO Donations (donor_id, category, items, date_donated) VALUES (?, ?, ?, ?)",
            (user["user_id"], category, items, date_donated),
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
        SELECT m.match_id, d.items, d.category, r.name as recipient_name, m.status
        FROM Matches m
        JOIN Donations d ON m.donation_id = d.donation_id
        JOIN Recipients r ON m.recipient_id = r.recipient_id
        WHERE m.status='Pending'
    """
    ).fetchall()

    return render_template("partials/matches.html", matches=matches, user=user)


# ----------------- RUN APP -----------------
if __name__ == "__main__":
    app.run(debug=True)
