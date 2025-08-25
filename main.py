from flask import Flask, render_template, request, redirect, url_for, flash
import re

app = Flask(__name__)
app.secret_key = "supersecretkey"  # required for flash

# ----------------- ROUTES -----------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("partials/about.html")


@app.route("/menu")
def menu():
    return render_template("partials/menu.html")


@app.route("/add")
def add():
    return render_template("partials/add.html")


# ----------------- SIGNUP -----------------
@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Validate email
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            flash("❌ Invalid email address.", "error")
            return redirect(url_for("signup_page"))

        # Validate password: 8+ chars, 1 uppercase, 1 symbol
        if not re.fullmatch(
            r'^(?=.*[A-Z])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$', password
        ):
            flash(
                "❌ Password must be at least 8 chars, include an uppercase and a symbol.",
                "error",
            )
            return redirect(url_for("signup_page"))

        # TODO: Save user to database here
        flash("✅ Account created successfully!", "success")
        return redirect(url_for("signin_page"))

    return render_template("partials/signup.html")


# ----------------- SIGNIN -----------------
@app.route("/signin", methods=["GET", "POST"])
def signin_page():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # TODO: Check user credentials against database
        # For now just flash success
        flash("✅ Signed in successfully!", "success")
        return redirect(url_for("index"))

    return render_template("partials/signin.html")

if __name__ == "__main__":
    app.run(debug=True)
