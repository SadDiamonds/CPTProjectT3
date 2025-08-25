from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
import sqlite3 as sql
import database_manager as dbHandler

app = Flask(__name__)


@app.route("/index.html", methods=["GET"])
@app.route("/", methods=["POST", "GET"])
def index():
    data = dbHandler.listExtension()
    return render_template("index.html", content=data)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/add")
def contact():
    return render_template("add.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form["name"]
        link = request.form["hyperlink"]
        about = request.form["about"]
        # extend for your schema if needed (image, language, etc)
        con = sql.connect("database/data_source.db")
        cur = con.cursor()
        cur.execute(
            "INSERT INTO extension (name, hyperlink, about, image, language) VALUES (?, ?, ?, ?, ?)",
            (name, link, about, "https://via.placeholder.com/300", "Custom"),
        )
        con.commit()
        con.close()
        return redirect("/")
    return render_template("add.html")
