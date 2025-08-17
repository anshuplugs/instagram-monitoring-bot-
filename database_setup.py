# database_setup.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
DB_FILE = os.getenv('DATABASE_FILE', 'monitor.db')

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS monitored_profiles (
    username TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL, -- 'discord' or 'telegram'
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profile_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    status TEXT NOT NULL,
    follower_count INTEGER,
    bio TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES monitored_profiles(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ban_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'banned' or 'unbanned'
    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES monitored_profiles(username) ON DELETE CASCADE
);
"""

def setup_database():
    """Creates the database and necessary tables."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executescript(TABLES_SQL)
        conn.commit()
        print(f"Database '{DB_FILE}' set up successfully.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_database()
