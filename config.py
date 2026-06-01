import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mudar_para_uma_chave_secreta')
    DATABASE = os.path.join(BASE_DIR, 'gei_database.db')
    CSV_PATH = os.path.join(BASE_DIR, 'data', 'sample_inventory.csv')
