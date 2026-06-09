from werkzeug.security import generate_password_hash, check_password_hash
from db import get_session
from models import User


class UserManager:
    def __init__(self, db_path=None):
        self.db_path = db_path

    @staticmethod
    def validate_passwords(password, confirm_password):
        if password != confirm_password:
            return False, 'As senhas não coincidem.'
        if not password:
            return False, 'A senha é obrigatória.'
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