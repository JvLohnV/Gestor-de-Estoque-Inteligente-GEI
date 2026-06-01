from functools import wraps
from flask import session, redirect, url_for, flash
from models import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash


def login_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, password, role FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return False

    stored_password = user['password']
    # Detect whether the stored value looks like a password hash (e.g. 'pbkdf2:...', 'scrypt:...')
    is_hashed = isinstance(stored_password, str) and ':' in stored_password
    is_valid = False
    if is_hashed:
        try:
            is_valid = check_password_hash(stored_password, password)
        except Exception:
            is_valid = False
    else:
        is_valid = stored_password == password

    if is_valid:
        session['username'] = user['username']
        session['role'] = user['role'] or 'user'
        if not is_hashed:
            cursor.execute('UPDATE users SET password = ? WHERE username = ?', (generate_password_hash(password), username))
            conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def logout_user():
    session.pop('username', None)
    session.pop('role', None)


def require_login(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('username') is None:
            flash('Faça login para acessar essa página.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def require_admin(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('username') is None:
            flash('Faça login para acessar essa página.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
            return redirect(url_for('dashboard'))
        return view(*args, **kwargs)
    return wrapped_view
