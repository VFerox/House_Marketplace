from flask import Flask, g, render_template, request, redirect, url_for, session
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "devkey")
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()





def create_tables():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT NOT NULL UNIQUE, "
        "password_hash TEXT NOT NULL, "
        "created_at TEXT NOT NULL"
        ")"
    )
    db.commit()

def hash_password(password):
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + derived.hex()

def verify_password(password, stored):
    parts = stored.split(":")
    if len(parts) != 2:
        return False
    salt = bytes.fromhex(parts[0])
    expected = bytes.fromhex(parts[1])
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return secrets.compare_digest(check, expected)

def generate_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def require_csrf():
    token_a = session.get("csrf_token")
    token_b = request.form.get("csrf_token", "")
    if not token_a or not secrets.compare_digest(token_a, token_b):
        abort(400)


app.jinja_env.globals["csrf_token"] = generate_csrf_token


@app.before_request
def before_request():
    create_tables()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="Fill all fields")
        db = get_db()
        exists = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if exists:
            return render_template("register.html", error="Username taken")
        password_hash = hash_password(password)
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        db.execute(
            "INSERT INTO users (username, password_hash, created_at) "
            "VALUES (?, ?, ?)",
            (username, password_hash, created_at),
        )
        db.commit()
        return redirect(url_for("index"))
    return render_template("register.html")








if __name__ == "__main__":
    app.run(debug=True)