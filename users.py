from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import db

def create_user(username, password):
    password_hash = generate_password_hash(password)
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    sql = "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)"
    db.execute(sql, [username, password_hash, created_at])
    return db.last_insert_id()

def find_auth(username):
    sql = "SELECT id, password_hash FROM users WHERE username = ?"
    rows = db.query(sql, [username])
    return rows[0] if rows else None

def get_user(user_id):
    sql = "SELECT id, username, created_at FROM users WHERE id = ?"
    rows = db.query(sql, [user_id])
    return rows[0] if rows else None

def verify_password(hash_value, password):
    return check_password_hash(hash_value, password)

def listing_stats(user_id):
    sql = """SELECT COUNT(*) total,
                    MIN(created_at) first_created,
                    MAX(created_at) last_created
             FROM listings
             WHERE user_id = ?"""
    rows = db.query(sql, [user_id])
    return rows[0]

def inquiry_total(user_id):
    sql = "SELECT COUNT(*) total FROM inquiries WHERE user_id = ?"
    rows = db.query(sql, [user_id])
    return rows[0]["total"]

def user_listings(user_id):
    sql = """SELECT id, title, location, price_eur, created_at
             FROM listings
             WHERE user_id = ?
             ORDER BY created_at DESC"""
    return db.query(sql, [user_id])