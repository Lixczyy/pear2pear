import sqlite3
import os

# Flask stores SQLite DBs in the instance/ folder by default
db_path = os.path.join("instance", "pear2pear.db")
print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(users)")
cols = [row[1] for row in cur.fetchall()]
print("Current columns:", cols)

for sql, col in [
    ("ALTER TABLE users ADD COLUMN friends_public BOOLEAN NOT NULL DEFAULT 0", "friends_public"),
    ("ALTER TABLE users ADD COLUMN age INTEGER", "age"),
    ("ALTER TABLE users ADD COLUMN location VARCHAR(100)", "location"),
    ("ALTER TABLE users ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT 1", "is_public"),
]:
    if col not in cols:
        try:
            cur.execute(sql)
            print(f"✓ Added {col}")
        except Exception as e:
            print(f"✗ {col}: {e}")
    else:
        print(f"⚠ {col} already exists, skipping")

cur.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    body       VARCHAR(300) NOT NULL,
    link       VARCHAR(200),
    read       BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)""")
print("✓ notifications table ready")

cur.execute("""
CREATE TABLE IF NOT EXISTS friendships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL REFERENCES users(id),
    to_id   INTEGER NOT NULL REFERENCES users(id),
    status  VARCHAR(10) NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_id, to_id)
)""")
print("✓ friendships table ready")

cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id   INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    read        BOOLEAN DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)""")
print("✓ messages table ready")

# Add avatar column
for sql, col in [
    ("ALTER TABLE users ADD COLUMN avatar VARCHAR(200)", "avatar"),
]:
    if col not in cols:
        try:
            cur.execute(sql)
            print(f"✓ Added {col}")
        except Exception as e:
            print(f"✗ {col}: {e}")
    else:
        print(f"⚠ {col} already exists, skipping")

conn.commit()
conn.close()
print("\nDone! Restart Flask now.")
