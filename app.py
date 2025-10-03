import sqlite3
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, abort
import config
import db
import users
import listings

app = Flask(__name__)
app.secret_key = config.secret_key

def create_tables():
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT NOT NULL UNIQUE, "
        "password_hash TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS listings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "title TEXT NOT NULL, "
        "location TEXT NOT NULL, "
        "price_eur INTEGER NOT NULL, "
        "description TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS categories ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL UNIQUE)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS listing_categories ("
        "listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE, "
        "category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE, "
        "PRIMARY KEY (listing_id, category_id))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS inquiries ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE, "
        "user_id INTEGER NOT NULL REFERENCES users(id), "
        "content TEXT NOT NULL, "
        "sent_at TEXT NOT NULL)"
    )
    rows = db.query("SELECT id FROM categories LIMIT 1")
    if not rows:
        for n in ["Apartment", "House", "Studio", "Townhouse", "Villa"]:
            db.execute("INSERT INTO categories (name) VALUES (?)", [n])

@app.before_request
def before_request():
    create_tables()

def require_login():
    if "user_id" not in session:
        abort(403)

def check_csrf():
    if request.form["csrf_token"] != session["csrf_token"]:
        abort(403)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password1 = request.form.get("password1", "")
        password2 = request.form.get("password2", "")
        if not username or not password1 or not password2:
            return render_template("register.html", error="Fill all fields")
        if password1 != password2:
            return render_template("register.html", error="Passwords differ")
        if len(username) > 32 or len(password1) > 64:
            return render_template("register.html", error="Too long values")
        try:
            users.create_user(username, password1)
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username taken")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = users.find_auth(username)
        if not row or not users.verify_password(row["password_hash"], password):
            return render_template("login.html", error="Invalid credentials")
        session["user_id"] = row["id"]
        session["username"] = username
        session["csrf_token"] = secrets.token_hex(16)
        return redirect(url_for("listings_page"))
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    require_login()
    check_csrf()
    session.clear()
    return redirect(url_for("index"))

@app.route("/listings")
def listings_page():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "").strip()
    cid = int(category_id) if category_id.isdigit() else None
    rows = listings.search_listings(q, cid) if q or cid else listings.search_listings("", None)
    cats = listings.list_categories()
    return render_template("listings.html", rows=rows, q=q, cats=cats, category_id=category_id)

@app.route("/listings/new", methods=["GET", "POST"])
def listing_new():
    require_login()
    cats = listings.list_categories()
    if request.method == "POST":
        check_csrf()
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        price_text = request.form.get("price_eur", "").strip()
        description = request.form.get("description", "").strip()
        ids = [int(x) for x in request.form.getlist("category_ids") if x.isdigit()]
        if not title or not location or not price_text or not description:
            return render_template("listing_new.html", cats=cats, error="Fill all fields")
        if len(title) > 80 or len(location) > 80 or len(description) > 2000:
            return render_template("listing_new.html", cats=cats, error="Too long values")
        if not price_text.isdigit():
            return render_template("listing_new.html", cats=cats, error="Price must be a whole number")
        price = int(price_text)
        if price <= 0:
            return render_template("listing_new.html", cats=cats, error="Price must be positive")
        listing_id = listings.create_listing(session["user_id"], title, location, price, description)
        listings.set_listing_categories(listing_id, ids)
        return redirect(url_for("listings_page"))
    return render_template("listing_new.html", cats=cats)

@app.route("/listings/<int:listing_id>")
def listing_detail(listing_id):
    row = listings.get_listing(listing_id)
    if not row:
        abort(404)
    cats = listings.get_listing_categories(listing_id)
    ins = listings.list_inquiries(listing_id)
    owner = session.get("user_id") == row["user_id"]
    return render_template("listing_detail.html", row=row, cats=cats, inquiries=ins, owner=owner, error=None)

@app.route("/listings/<int:listing_id>/edit", methods=["GET", "POST"])
def listing_edit(listing_id):
    require_login()
    row = listings.get_listing_basic(listing_id)
    if not row:
        abort(404)
    if row["user_id"] != session["user_id"]:
        abort(403)
    cats = listings.list_categories()
    if request.method == "POST":
        check_csrf()
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        price_text = request.form.get("price_eur", "").strip()
        description = request.form.get("description", "").strip()
        ids = [int(x) for x in request.form.getlist("category_ids") if x.isdigit()]
        if not title or not location or not price_text or not description:
            selected = set(ids)
            return render_template("listing_edit.html", row=row, cats=cats, selected=selected, error="Fill all fields")
        if len(title) > 80 or len(location) > 80 or len(description) > 2000:
            selected = set(ids)
            return render_template("listing_edit.html", row=row, cats=cats, selected=selected, error="Too long values")
        if not price_text.isdigit():
            selected = set(ids)
            return render_template("listing_edit.html", row=row, cats=cats, selected=selected, error="Price must be a whole number")
        price = int(price_text)
        if price <= 0:
            selected = set(ids)
            return render_template("listing_edit.html", row=row, cats=cats, selected=selected, error="Price must be positive")
        listings.update_listing(listing_id, title, location, price, description)
        listings.set_listing_categories(listing_id, ids)
        return redirect(url_for("listing_detail", listing_id=listing_id))
    selected_rows = listings.get_listing_categories(listing_id)
    selected = {r["id"] for r in selected_rows}
    return render_template("listing_edit.html", row=row, cats=cats, selected=selected)

@app.route("/listings/<int:listing_id>/delete", methods=["POST"])
def listing_delete(listing_id):
    require_login()
    check_csrf()
    row = listings.get_listing_basic(listing_id)
    if not row:
        abort(404)
    if row["user_id"] != session["user_id"]:
        abort(403)
    listings.delete_listing(listing_id)
    return redirect(url_for("listings_page"))

@app.route("/listings/<int:listing_id>/inquiry", methods=["POST"])
def listing_inquiry(listing_id):
    require_login()
    check_csrf()
    row = listings.get_listing_basic(listing_id)
    if not row:
        abort(404)
    content = request.form.get("content", "").strip()
    if not content or len(content) > 1000:
        row_full = listings.get_listing(listing_id)
        cats = listings.get_listing_categories(listing_id)
        ins = listings.list_inquiries(listing_id)
        owner = session.get("user_id") == row_full["user_id"]
        return render_template("listing_detail.html", row=row_full, cats=cats, inquiries=ins, owner=owner, error="Write a message up to 1000 chars")
    listings.add_inquiry(listing_id, session["user_id"], content)
    return redirect(url_for("listing_detail", listing_id=listing_id))

@app.route("/inquiries/<int:inquiry_id>/delete", methods=["POST"])
def inquiry_delete(inquiry_id):
    require_login()
    check_csrf()
    row = listings.get_inquiry(inquiry_id)
    if not row:
        abort(404)
    if row["user_id"] != session["user_id"]:
        abort(403)
    listings.delete_inquiry(inquiry_id)
    return redirect(url_for("listing_detail", listing_id=row["listing_id"]))

@app.route("/my")
def my_listings():
    require_login()
    rows = listings.list_for_user(session["user_id"])
    return render_template("my.html", rows=rows)

@app.route("/user/<int:user_id>")
def user_page(user_id):
    user = users.get_user(user_id)
    if not user:
        abort(404)
    stats = users.listing_stats(user_id)
    total_inquiries = users.inquiry_total(user_id)
    user_rows = users.user_listings(user_id)
    return render_template(
        "user.html",
        user=user,
        listing_stats=stats,
        inquiry_total=total_inquiries,
        user_listings=user_rows,
    )

if __name__ == "__main__":
    app.run(debug=True)