from flask import Flask, g, render_template, request, redirect, url_for, session, abort
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


def current_user_id():
    return session.get("user_id")


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return render_template("login.html", error="Invalid credentials")
        session["user_id"] = row["id"]
        session["username"] = username
        generate_csrf_token()
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    require_csrf()
    session.clear()
    return redirect(url_for("index"))


@app.route("/houses")
def houses():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        pattern = "%" + q + "%"
        rows = db.execute(
            "SELECT h.id, h.title, h.location, h.description, h.created_at, u.username "
            "FROM houses h JOIN users u ON u.id = h.user_id "
            "WHERE h.title LIKE ? OR h.location LIKE ? "
            "ORDER BY h.created_at DESC",
            (pattern, pattern),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT h.id, h.title, h.location, h.description, h.created_at, u.username "
            "FROM houses h JOIN users u ON u.id = h.user_id "
            "ORDER BY h.created_at DESC"
        ).fetchall()
    return render_template("houses.html", rows=rows, q=q)


@app.route("/houses/new", methods=["GET", "POST"])
def house_new():
    if not current_user_id():
        return redirect(url_for("login"))
    if request.method == "POST":
        require_csrf()
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not location or not description:
            return render_template("house_new.html", error="Fill all fields")
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        db = get_db()
        db.execute(
            "INSERT INTO houses (user_id, title, location, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (current_user_id(), title, location, description, created_at),
        )
        db.commit()
        return redirect(url_for("houses"))
    return render_template("house_new.html")


def get_house_for_owner(house_id):
    db = get_db()
    row = db.execute(
        "SELECT id, user_id, title, location, description, created_at "
        "FROM houses WHERE id = ?",
        (house_id,),
    ).fetchone()
    if not row:
        abort(404)
    if row["user_id"] != current_user_id():
        abort(403)
    return row


@app.route("/houses/<int:house_id>")
def house_detail(house_id):
    db = get_db()
    row = db.execute(
        "SELECT h.id, h.title, h.location, h.description, h.created_at, "
        "u.username, h.user_id "
        "FROM houses h JOIN users u ON u.id = h.user_id "
        "WHERE h.id = ?",
        (house_id,),
    ).fetchone()
    if not row:
        abort(404)
    owner = row["user_id"] == current_user_id()
    return render_template("house_detail.html", row=row, owner=owner)


@app.route("/houses/<int:house_id>/edit", methods=["GET", "POST"])
def house_edit(house_id):
    if not current_user_id():
        return redirect(url_for("login"))
    if request.method == "POST":
        require_csrf()
        row = get_house_for_owner(house_id)
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not location or not description:
            return render_template("house_edit.html", row=row, error="Fill all fields")
        db = get_db()
        db.execute(
            "UPDATE houses SET title = ?, location = ?, description = ? WHERE id = ?",
            (title, location, description, house_id),
        )
        db.commit()
        return redirect(url_for("house_detail", house_id=house_id))
    row = get_house_for_owner(house_id)
    return render_template("house_edit.html", row=row)


@app.route("/houses/<int:house_id>/delete", methods=["POST"])
def house_delete(house_id):
    if not current_user_id():
        return redirect(url_for("login"))
    require_csrf()
    get_house_for_owner(house_id)
    db = get_db()
    db.execute("DELETE FROM houses WHERE id = ?", (house_id,))
    db.commit()
    return redirect(url_for("houses"))


@app.route("/my")
def my_listings():
    if not current_user_id():
        return redirect(url_for("login"))
    db = get_db()
    rows = db.execute(
        "SELECT id, title, location, description, created_at "
        "FROM houses WHERE user_id = ? "
        "ORDER BY created_at DESC",
        (current_user_id(),),
    ).fetchall()
    return render_template("my.html", rows=rows)





if __name__ == "__main__":
    app.run(debug=True)