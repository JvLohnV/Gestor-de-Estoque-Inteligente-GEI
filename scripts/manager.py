import re
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_session
from models import User

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
        session = get_session()
        try:
            users = session.query(User.id, User.username, User.role).order_by(User.username).all()
            return [dict(id=u[0], username=u[1], role=u[2]) for u in users]
        finally:
            session.close()

    def add_user(self, username, password, confirm_password, role='user'):
        if not username:
            return False, 'O nome de usuário é obrigatório.'
        valid, message = self.validate_passwords(password, confirm_password)
        if not valid:
            return False, message
        hashed_password = generate_password_hash(password)
        session = get_session()
        try:
            user = User(username=username, password=hashed_password, role=role)
            session.add(user)
            session.commit()
            return True, 'Usuário criado com sucesso.'
        except Exception:
            session.rollback()
            return False, 'Já existe um usuário com esse nome.'
        finally:
            session.close()
            
    def toggle_role(self, user_id):
        session = get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False, 'Usuário não encontrado.'
            user.role = 'user' if user.role == 'admin' else 'admin'
            session.commit()
            new_role = 'administrador' if user.role == 'admin' else 'usuário padrão'
            return True, f'Perfil de "{user.username}" alterado para {new_role}.'
        except Exception:
            session.rollback()
            return False, 'Erro ao alterar perfil.'
        finally:
            session.close()

    def delete_user(self, user_id):
        session = get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False, 'Usuário não encontrado.'
            username = user.username
            session.delete(user)
            session.commit()
            return True, f'Usuário "{username}" deletado com sucesso.'
        except Exception:
            session.rollback()
            return False, 'Erro ao deletar usuário.'
        finally:
            session.close()

    def get_user_by_username(self, username):
        session = get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            return user
        finally:
            session.close()

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
        session = get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                user.password = hashed_password
                session.commit()
        finally:
            session.close()
