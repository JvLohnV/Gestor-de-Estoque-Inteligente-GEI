import os
from sqlalchemy import Column, Integer, String, Text, Float, TIMESTAMP, func
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from db import Base, init_engine, get_session, get_engine


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, default='user')


class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id = Column(Integer, primary_key=True)
    code = Column(String, default='')
    name = Column(String, nullable=False)
    category = Column(String)
    classification = Column(String, default='')
    quantity = Column(Integer, nullable=False, default=0)
    minimum_quantity = Column(Integer, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0.0)
    corridor = Column(String, default='')
    cabinet = Column(String, default='')
    shelf = Column(String, default='')
    description = Column(Text)
    extra_data = Column(Text, default='{}')


class StockMovement(Base):
    __tablename__ = 'stock_movements'
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)
    item_name = Column(String)
    type = Column(String)
    quantity = Column(Integer)
    previous_quantity = Column(Integer)
    new_quantity = Column(Integer)
    reason = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


def init_db(database_url=None):
    # Initialize engine if not already
    if database_url is None:
        database_url = Config.DATABASE
    init_engine(database_url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # ensure admin user exists
    session = get_session()
    try:
        admin = session.query(User).filter_by(username='admin').first()
        if admin is None:
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            session.add(admin)
        else:
            admin.role = 'admin'
        session.commit()
    finally:
        session.close()


def ensure_admin_user(password, database_url=None):
    if database_url is None:
        database_url = Config.DATABASE
    # Ensure engine initialized
    init_engine(database_url)
    session = get_session()
    try:
        admin = session.query(User).filter_by(username='admin').first()
        hashed = generate_password_hash(password)
        if admin is None:
            admin = User(username='admin', password=hashed, role='admin')
            session.add(admin)
        else:
            stored = admin.password or ''
            needs_update = False
            if not stored.startswith('pbkdf2:'):
                needs_update = True
            else:
                try:
                    if not check_password_hash(stored, password):
                        needs_update = True
                except Exception:
                    needs_update = True
            if needs_update:
                admin.password = hashed
                admin.role = 'admin'
        session.commit()
    finally:
        session.close()

