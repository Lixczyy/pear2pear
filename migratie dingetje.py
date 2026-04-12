"""
Run once to update your database:
    python migrate.py
"""
import sqlite3

conn = sqlite3.connect("pear2pear.db")
cur = conn.cursor()

# voeg comulms als ik nieuwe heb
user_columns = [
    "ALTER TABLE users ADD COLUMN age INTEGER",
    "ALTER TABLE users ADD COLUMN location VARCHAR(100)",
    "ALTER TABLE users ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT 1",
]
for sql in user_columns:
    try:
        cur.execute(sql)
        print(f"✓ {sql}")
    except sqlite3.OperationalError as e:
        print(f"⚠ Skipped: {e}")

# friendjes tabel maken
cur.execute("""
CREATE TABLE IF NOT EXISTS friendships (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id    INTEGER NOT NULL REFERENCES users(id),
    to_id      INTEGER NOT NULL REFERENCES users(id),
    status     VARCHAR(10) NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_id, to_id)
)
""")
print("✓ friendships table ready")

# messages tabel maken
cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id   INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    read        BOOLEAN DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
print("✓ messages table ready")

conn.commit()
conn.close()
print("\nDone! Your database is up to date.")
