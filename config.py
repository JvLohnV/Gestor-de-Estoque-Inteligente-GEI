import os
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mudar_para_uma_chave_secreta')
    # Allow overriding the database path via env var (useful in production)
    env_db = os.environ.get('DATABASE') or os.environ.get('DATABASE_URL')
    default_db = os.path.join(BASE_DIR, 'gei_database.db')

    # Safety: require an explicit persistent DATABASE in common cloud environments
    CLOUD_ENV_VARS = ('RENDER', 'RENDER_SERVICE_ID', 'RENDER_EXTERNAL_URL', 'DYNO', 'HEROKU', 'K_SERVICE')
    _running_in_cloud = any(os.environ.get(v) for v in CLOUD_ENV_VARS)

    # Allow explicit enabling of destructive actions (clearing full inventory)
    ALLOW_CLEAR = os.environ.get('ALLOW_CLEAR_INVENTORY', '0') == '1'

    # Prefer env var if provided; otherwise try default path and fall back to temp dir if not writable
    if env_db:
        DATABASE = env_db
    else:
        # If running in a cloud environment, require an explicit DATABASE env var
        if _running_in_cloud:
            raise RuntimeError(
                'Running in a cloud environment. Set the DATABASE or DATABASE_URL environment variable to a persistent database (e.g. Postgres) to avoid data loss.'
            )
        try:
            # Ensure directory exists and is writable
            db_dir = os.path.dirname(default_db) or BASE_DIR
            os.makedirs(db_dir, exist_ok=True)
            test_path = os.path.join(db_dir, '.db_write_test')
            with open(test_path, 'w') as f:
                f.write('ok')
            os.remove(test_path)
            DATABASE = default_db
        except Exception:
            # Fallback to system temp directory (writable on most hosts)
            DATABASE = os.path.join(tempfile.gettempdir(), 'gei_database.db')

    CSV_PATH = os.path.join(BASE_DIR, 'data', 'sample_inventory.csv')
