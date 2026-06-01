import re
from models import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

PASSWORD_POLICY_MESSAGE = (
    'A senha deve ter pelo menos 14 caracteres, conter letra maiúscula, letra minúscula, número e um caractere especial.'
)

class UserManager:
    def __init__(self, db_path=None):
        self.db_path = db_path

    @staticmethod
    def validate_passwords(password, confirm_password):
        if password != confirm_password:
            return False, 'As senhas não coincidem.'
        if len(password) < 14:
            return False, PASSWORD_POLICY_MESSAGE
        if not re.search(r'[A-Z]', password):
            return False, PASSWORD_POLICY_MESSAGE
        if not re.search(r'[a-z]', password):
            return False, PASSWORD_POLICY_MESSAGE
        if not re.search(r'\d', password):
            return False, PASSWORD_POLICY_MESSAGE
        if not re.search(r'[!@#$%^&*()_+\-=[\]{};:\"\\|,.<>/?]', password):
            return False, PASSWORD_POLICY_MESSAGE
        return True, None

    def get_all_users(self):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, role FROM users ORDER BY username')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_user(self, username, password, confirm_password, role='user'):
        if not username:
            return False, 'O nome de usuário é obrigatório.'
        valid, message = self.validate_passwords(password, confirm_password)
        if not valid:
            return False, message
        hashed_password = generate_password_hash(password)
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, hashed_password, role)
            )
            conn.commit()
        except Exception:
            conn.close()
            return False, 'Já existe um usuário com esse nome.'
        conn.close()
        return True, 'Usuário criado com sucesso.'

    def get_user_by_username(self, username):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, role, password FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        return user

    def verify_password(self, stored_password, candidate_password):
        is_hashed = isinstance(stored_password, str) and ':' in stored_password
        if is_hashed:
            try:
                return check_password_hash(stored_password, candidate_password)
            except Exception:
                return False
        return stored_password == candidate_password

    def update_password_hash(self, username, password):
        hashed_password = generate_password_hash(password)
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_password, username))
        conn.commit()
        conn.close()
