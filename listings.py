from datetime import datetime
import db

def list_categories():
    sql = "SELECT id, name FROM categories ORDER BY name"
    return db.query(sql)

def create_listing(user_id, title, location, price_eur, description):
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    sql = """INSERT INTO listings (user_id, title, location, price_eur, description, created_at)
             VALUES (?, ?, ?, ?, ?, ?)"""
    db.execute(sql, [user_id, title, location, price_eur, description, created_at])
    return db.last_insert_id()

def update_listing(listing_id, title, location, price_eur, description):
    sql = """UPDATE listings
             SET title = ?, location = ?, price_eur = ?, description = ?
             WHERE id = ?"""
    db.execute(sql, [title, location, price_eur, description, listing_id])

def delete_listing(listing_id):
    sql = "DELETE FROM listings WHERE id = ?"
    db.execute(sql, [listing_id])

def set_listing_categories(listing_id, category_ids):
    sql_del = "DELETE FROM listing_categories WHERE listing_id = ?"
    db.execute(sql_del, [listing_id])
    for cid in category_ids:
        sql_ins = """INSERT OR IGNORE INTO listing_categories (listing_id, category_id)
                     VALUES (?, ?)"""
        db.execute(sql_ins, [listing_id, cid])

def get_listing_basic(listing_id):
    sql = """SELECT id, user_id, title, location, price_eur, description, created_at
             FROM listings
             WHERE id = ?"""
    rows = db.query(sql, [listing_id])
    return rows[0] if rows else None

def get_listing(listing_id):
    sql = """SELECT l.id, l.user_id, l.title, l.location, l.price_eur,
                    l.description, l.created_at, u.username
             FROM listings l JOIN users u ON u.id = l.user_id
             WHERE l.id = ?"""
    rows = db.query(sql, [listing_id])
    return rows[0] if rows else None

def get_listing_categories(listing_id):
    sql = """SELECT c.id, c.name
             FROM categories c, listing_categories lc
             WHERE lc.listing_id = ? AND lc.category_id = c.id
             ORDER BY c.name"""
    return db.query(sql, [listing_id])

def search_listings(q, category_id):
    params = []
    where = []
    if q:
        where.append("(l.title LIKE ? OR l.location LIKE ?)")
        like = "%" + q + "%"
        params.extend([like, like])
    if category_id:
        where.append("""EXISTS (
            SELECT 1 FROM listing_categories lc
            WHERE lc.listing_id = l.id AND lc.category_id = ?
        )""")
        params.append(category_id)
    sql = """SELECT l.id, l.title, l.location, l.price_eur, l.description,
                    l.created_at, u.username
             FROM listings l JOIN users u ON u.id = l.user_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.created_at DESC"
    return db.query(sql, params)

def list_for_user(user_id):
    sql = """SELECT id, title, location, price_eur, description, created_at
             FROM listings
             WHERE user_id = ?
             ORDER BY created_at DESC"""
    return db.query(sql, [user_id])

def add_inquiry(listing_id, user_id, content):
    sent_at = datetime.utcnow().isoformat(timespec="seconds")
    sql = """INSERT INTO inquiries (listing_id, user_id, content, sent_at)
             VALUES (?, ?, ?, ?)"""
    db.execute(sql, [listing_id, user_id, content, sent_at])

def get_inquiry(inquiry_id):
    sql = "SELECT id, user_id, listing_id FROM inquiries WHERE id = ?"
    rows = db.query(sql, [inquiry_id])
    return rows[0] if rows else None

def delete_inquiry(inquiry_id):
    sql = "DELETE FROM inquiries WHERE id = ?"
    db.execute(sql, [inquiry_id])

def list_inquiries(listing_id):
    sql = """SELECT i.id, i.content, i.sent_at, i.user_id, u.username
             FROM inquiries i, users u
             WHERE i.listing_id = ? AND i.user_id = u.id
             ORDER BY i.id DESC"""
    return db.query(sql, [listing_id])