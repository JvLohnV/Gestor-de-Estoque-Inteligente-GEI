import os
import sqlite3
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash


def get_db_connection(db_path=None):
    if db_path is None:
        db_path = Config.DATABASE
    # Use a slightly higher timeout and allow multi-thread access within a process.
    # Note: multiple gunicorn processes still require careful handling; we set workers=1 in Procfile.
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db_path = Config.DATABASE
    # Ensure parent directory exists; if not possible, fall back to temp dir
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = get_db_connection(db_path)
    except Exception:
        import tempfile
        fallback = os.path.join(tempfile.gettempdir(), 'gei_database.db')
        conn = get_db_connection(fallback)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT DEFAULT '',
            name TEXT NOT NULL,
            category TEXT,
            classification TEXT DEFAULT '',
            quantity INTEGER NOT NULL DEFAULT 0,
            minimum_quantity INTEGER NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0.0,
            corridor TEXT DEFAULT '',
            cabinet TEXT DEFAULT '',
            shelf TEXT DEFAULT '',
            description TEXT,
            extra_data TEXT DEFAULT '{}'
        )
    ''')

    cursor.execute('PRAGMA table_info(inventory_items)')
    inventory_columns = [row['name'] for row in cursor.fetchall()]
    if 'code' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN code TEXT DEFAULT ''")
    if 'classification' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN classification TEXT DEFAULT ''")
    if 'minimum_quantity' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN minimum_quantity INTEGER NOT NULL DEFAULT 0")
    if 'corridor' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN corridor TEXT DEFAULT ''")
    if 'cabinet' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN cabinet TEXT DEFAULT ''")
    if 'shelf' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN shelf TEXT DEFAULT ''")
    if 'extra_data' not in inventory_columns:
        cursor.execute("ALTER TABLE inventory_items ADD COLUMN extra_data TEXT DEFAULT '{}'")

    cursor.execute('PRAGMA table_info(users)')
    columns = [row['name'] for row in cursor.fetchall()]
    if 'role' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone() is None:
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            ('admin', generate_password_hash('admin123'), 'admin')
        )
    else:
        cursor.execute('UPDATE users SET role = ? WHERE username = ?', ('admin', 'admin'))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            item_name TEXT,
            type TEXT,
            quantity INTEGER,
            previous_quantity INTEGER,
            new_quantity INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def ensure_admin_user(password, db_path=None):
    """Create or update the `admin` user with a securely hashed password.

    If the user does not exist it will be inserted. If it exists but the
    password is not hashed, or does not match the provided password, the
    password will be updated to a secure hash and the role set to 'admin'.
    """
    if db_path is None:
        db_path = Config.DATABASE
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    hashed = generate_password_hash(password)
    cursor.execute('SELECT id, password FROM users WHERE username = ?', ('admin',))
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            ('admin', hashed, 'admin')
        )
    else:
        stored = row['password']
        needs_update = False
        if not stored.startswith('pbkdf2:'):
            needs_update = True
        else:
            try:
                # If the stored hash doesn't validate the provided password,
                # update it to the new hashed value (keeps intent simple).
                if not check_password_hash(stored, password):
                    needs_update = True
            except Exception:
                needs_update = True
        if needs_update:
            cursor.execute('UPDATE users SET password = ?, role = ? WHERE username = ?', (hashed, 'admin', 'admin'))
    conn.commit()
    conn.close()
