import csv
import json
import os
import uuid
import logging
import pandas as pd
from werkzeug.utils import secure_filename
from config import Config
from db import init_engine, get_session
from models import InventoryItem, StockMovement
from sqlalchemy import func
import re
import unicodedata

UPLOAD_FOLDER = 'uploads/excels'
EXPORT_FOLDER = 'exports'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)

logger = logging.getLogger(__name__)

HEADER_KEYWORDS = {
    'material', 'nome', 'name', 'item',
    'quantidade', 'qtd', 'quantity', 'estoque',
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_item_name(name):
    if not name:
        return ''

    name = str(name).strip().lower()

    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))

    name = re.sub(r'\s+', ' ', name)

    return name

def normalize_column(column):
    column = str(column).strip().lower()
    mapping = {
        'material': 'name',
        'nome': 'name',
        'item': 'name',
        'quantidade': 'quantity',
        'qtd': 'quantity',
        'estoque': 'quantity',
        'estoque atual': 'quantity',
        'estoque mínimo': 'minimum_quantity',
        'estoque minimo': 'minimum_quantity',
        'mínimo': 'minimum_quantity',
        'minimo': 'minimum_quantity',
        'categoria': 'category',
        'classificação': 'classification',
        'classificacao': 'classification',
        'corredor': 'corridor',
        'armário': 'cabinet',
        'armário ': 'cabinet',
        'armario': 'cabinet',
        'prateleira': 'shelf',
        'gaveta': 'shelf',
        'observação': 'description',
        'observacao': 'description',
        'descrição': 'description',
        'descricao': 'description',
        'preço': 'price',
        'preco': 'price',
        'código': 'code',
        'codigo': 'code',
        'fornecedor': 'supplier',
        'unidade': 'unit',
        'localização': 'location',
        'localizacao': 'location',
        'local': 'location',
    }
    return mapping.get(column, column)


def find_header_row(df_raw):
    for i, row in df_raw.iterrows():
        values = [str(v).strip().lower() for v in row if pd.notna(v)]
        if any(v in HEADER_KEYWORDS for v in values):
            return i
    return 0


class InventoryManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE
        try:
            init_engine(self.db_path)
        except Exception as e:
            logger.exception(e)
            raise

    def _find_existing_item(self, session, parsed):

        code = str(parsed.get('code', '')).strip()

        if code:
            item = (
                session.query(InventoryItem)
                .filter(
                    func.lower(InventoryItem.code) == code.lower()
                )
                .first()
            )

            if item:
                return item

        normalized_name = normalize_item_name(parsed['name'])

        items = session.query(InventoryItem).all()

        for item in items:
            if normalize_item_name(item.name) == normalized_name:
                return item

        return None

    def _parse_row(self, row):
        parsed = {normalize_column(str(k)): v for k, v in row.items() if k is not None}

        def parse_int(value):
            try:
                if value is None or str(value).strip() in ('', 'nan'):
                    return 0
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        def parse_float(value):
            try:
                if value is None or str(value).strip() in ('', 'nan'):
                    return 0.0
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        name = str(parsed.get('name', '')).strip()
        if not name or name.lower() == 'nan':
            return None

        reserved_keys = {
            'code', 'name', 'category', 'classification', 'quantity',
            'minimum_quantity', 'price', 'corridor', 'cabinet', 'shelf',
            'description', 'supplier', 'unit', 'location'
        }

        extra_data = {}
        for key, value in parsed.items():
            if key not in reserved_keys and key != '':
                if value is None:
                    continue
                value_str = str(value).strip()
                if value_str == '' or value_str.lower() == 'nan':
                    continue
                extra_data[key] = value_str

        return {
            'code': str(parsed.get('code', '') or '').strip(),
            'name': name,
            'category': str(parsed.get('category', '') or '').strip(),
            'classification': str(parsed.get('classification', '') or '').strip(),
            'quantity': parse_int(parsed.get('quantity', 0)),
            'minimum_quantity': parse_int(parsed.get('minimum_quantity', 0)),
            'price': parse_float(parsed.get('price', 0)),
            'corridor': str(parsed.get('corridor', '') or '').strip(),
            'cabinet': str(parsed.get('cabinet', '') or '').strip(),
            'shelf': str(parsed.get('shelf', '') or '').strip(),
            'description': str(parsed.get('description', '') or '').strip(),
            'extra_data': json.dumps(extra_data, ensure_ascii=False),
        }

    def _row_to_item(self, row):
        if hasattr(row, '__dict__'):
            item = {k: getattr(row, k) for k in row.__dict__ if not k.startswith('_')}
        else:
            item = dict(row)
        try:
            item['extra_data'] = json.loads(item.get('extra_data') or '{}')
        except Exception:
            item['extra_data'] = {}
        return item

    def _flatten_items(self, items):
        rows = []
        for item in items:
            if hasattr(item, '__dict__'):
                row = {k: getattr(item, k) for k in item.__dict__ if not k.startswith('_')}
            else:
                row = dict(item)
            extra_data = row.pop('extra_data', {}) or {}
            if isinstance(extra_data, str):
                try:
                    extra_data = json.loads(extra_data)
                except Exception:
                    extra_data = {}
            if isinstance(extra_data, dict):
                row.update(extra_data)
            rows.append(row)
        return rows

    def _apply_update(self, existing, parsed):
        existing.quantity = parsed['quantity']
        existing.category = parsed['category']
        existing.classification = parsed['classification']
        existing.description = parsed['description']
        existing.corridor = parsed['corridor']
        existing.cabinet = parsed['cabinet']
        existing.shelf = parsed['shelf']
        existing.price = parsed['price']
        existing.code = parsed['code']
        existing.minimum_quantity = parsed['minimum_quantity']
        existing.extra_data = parsed['extra_data']

    def _build_item(self, parsed):
        return InventoryItem(
            code=parsed['code'],
            name=parsed['name'],
            category=parsed['category'],
            classification=parsed['classification'],
            quantity=parsed['quantity'],
            minimum_quantity=parsed['minimum_quantity'],
            price=parsed['price'],
            corridor=parsed['corridor'],
            cabinet=parsed['cabinet'],
            shelf=parsed['shelf'],
            description=parsed['description'],
            extra_data=parsed['extra_data'],
        )
        
    def merge_duplicate_rows(self, rows):
        """
        Une linhas duplicadas vindas do Excel/CSV.
        Soma as quantidades de materiais iguais.
        """

        merged = {}

        for row in rows:

            parsed = self._parse_row(row)

            if not parsed:
                continue

            key = (
                str(parsed.get('code', '')).strip().lower(),
                str(parsed.get('name', '')).strip().lower()
            )

            if key not in merged:
                merged[key] = parsed
                continue

            merged[key]['quantity'] += parsed['quantity']

            if not merged[key]['description']:
                merged[key]['description'] = parsed['description']

            if not merged[key]['category']:
                merged[key]['category'] = parsed['category']

        return list(merged.values())

    # ------------------------------------------------------------------ #
    #  CLEAR                                                               #
    # ------------------------------------------------------------------ #

    def clear_inventory(self):
        """Uso manual via UI — respeita ALLOW_CLEAR_INVENTORY."""
        if not getattr(Config, 'ALLOW_CLEAR', False):
            raise PermissionError(
                'Modo "replace" desabilitado. Habilite ALLOW_CLEAR_INVENTORY=1 no ambiente para usar.'
            )
        self.clear_inventory_force()

    def clear_inventory_force(self):
        """Uso interno pelo import — sem restrição de env var."""
        session = get_session()
        try:
            session.query(StockMovement).delete()
            session.query(InventoryItem).delete()
            session.commit()
            logger.info('Inventário limpo com sucesso.')
        except Exception as e:
            session.rollback()
            logger.exception(f'Erro ao limpar inventário: {e}')
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  QUERIES                                                             #
    # ------------------------------------------------------------------ #

    def get_all_items(self, search=None):
        session = get_session()
        try:
            q = session.query(InventoryItem)
            if search:
                pattern = f'%{search}%'
                q = q.filter(
                    (InventoryItem.name.ilike(pattern)) |
                    (InventoryItem.category.ilike(pattern)) |
                    (InventoryItem.description.ilike(pattern)) |
                    (InventoryItem.code.ilike(pattern))
                )
            rows = q.order_by(InventoryItem.name).all()
            return [self._row_to_item(row) for row in rows]
        finally:
            session.close()

    def get_low_stock_items(self):
        session = get_session()
        try:
            rows = (
                session.query(InventoryItem)
                .filter(InventoryItem.quantity <= InventoryItem.minimum_quantity)
                .order_by(InventoryItem.quantity.asc())
                .all()
            )
            items = [self._row_to_item(row) for row in rows]
        finally:
            session.close()

        for item in items:
            try:
                qty = int(item.get('quantity') or 0)
            except Exception:
                qty = 0
            try:
                minq = int(item.get('minimum_quantity') or 0)
            except Exception:
                minq = 0

            if qty == 0 and minq == 0:
                item['alert_type'] = 'out_of_stock_no_min'
            elif qty == 0:
                item['alert_type'] = 'out_of_stock'
            elif minq == 0:
                item['alert_type'] = 'no_minimum_defined'
            elif qty <= minq:
                item['alert_type'] = 'below_minimum'
            else:
                item['alert_type'] = 'ok'

        return items

    def get_recent_movements(self, limit=20):
        session = get_session()
        try:
            rows = (
                session.query(StockMovement)
                .order_by(StockMovement.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_item(row) for row in rows]
        finally:
            session.close()

    def add_item(
        self,
        code,
        name,
        category,
        quantity,
        minimum_quantity,
        price,
        corridor,
        cabinet,
        shelf,
        description,
        classification='',
        extra_data=None
    ):

        session = get_session()

        try:

            existing = self._find_existing_item(
                session,
                {
                    'code': code,
                    'name': name
                }
            )

            if existing:

                existing.quantity += quantity

                if category:
                    existing.category = category

                if description:
                    existing.description = description

                session.commit()

                return existing.id

            item = InventoryItem(
                code=code,
                name=name,
                category=category,
                classification=classification,
                quantity=quantity,
                minimum_quantity=minimum_quantity,
                price=price,
                corridor=corridor,
                cabinet=cabinet,
                shelf=shelf,
                description=description,
                extra_data=json.dumps(extra_data or {}, ensure_ascii=False),
            )

            session.add(item)
            session.commit()

            return item.id

        finally:
            session.close()

    def record_movement(self, item_id, movement_type, movement_quantity, movement_reason):
        session = get_session()
        try:
            item = session.query(InventoryItem).filter_by(id=item_id).first()
            if not item:
                return False
            previous_quantity = int(item.quantity or 0)
            if movement_type == 'entrada':
                new_quantity = previous_quantity + movement_quantity
            elif movement_type == 'saida':
                new_quantity = max(0, previous_quantity - movement_quantity)
            else:
                new_quantity = movement_quantity
            item.quantity = new_quantity
            movement = StockMovement(
                item_id=item_id, item_name=item.name,
                type=movement_type, quantity=movement_quantity,
                previous_quantity=previous_quantity, new_quantity=new_quantity,
                reason=movement_reason,
            )
            session.add(movement)
            session.commit()
            return new_quantity
        finally:
            session.close()

    def update_item_meta(self, item_id, category=None, minimum_quantity=None):
        session = get_session()
        try:
            item = session.query(InventoryItem).filter_by(id=item_id).first()
            if not item:
                return False
            if category is not None:
                item.category = category
            if minimum_quantity is not None:
                item.minimum_quantity = minimum_quantity
            session.commit()
            return True
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  CSV IMPORT                                                          #
    # ------------------------------------------------------------------ #

    def import_inventory_csv(self, csv_filepath, import_mode='update', chunk_size=1000):
        total_imported = 0
        total_updated = 0

        if import_mode == 'replace':
            self.clear_inventory_force()
            import_mode = 'insert'

        if not os.path.isfile(csv_filepath):
            logger.error(f'Arquivo CSV não encontrado: {csv_filepath}')
            return total_imported, total_updated

        with open(csv_filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames:
                reader.fieldnames = [normalize_column(col) for col in reader.fieldnames]
            batch_rows = []
            for row in reader:
                batch_rows.append(row)
                if len(batch_rows) >= chunk_size:
                    imp, upd = self._process_batch(batch_rows, import_mode, is_excel=False)
                    total_imported += imp
                    total_updated += upd
                    batch_rows = []
            if batch_rows:
                imp, upd = self._process_batch(batch_rows, import_mode, is_excel=False)
                total_imported += imp
                total_updated += upd

        logger.info(f'CSV import concluído: {total_imported} inseridos, {total_updated} atualizados.')
        return total_imported, total_updated

    # ------------------------------------------------------------------ #
    #  EXCEL IMPORT                                                        #
    # ------------------------------------------------------------------ #

    def import_inventory_excel(self, files, import_mode='update', chunk_size=1000):
        total_imported = 0
        total_updated = 0

        if import_mode == 'replace':
            self.clear_inventory_force()
            import_mode = 'insert'

        for file in files:
            if not (file and allowed_file(file.filename)):
                logger.warning(f'Arquivo ignorado: {getattr(file, "filename", "?")}')
                continue

            filename = secure_filename(file.filename)
            unique_name = f'{uuid.uuid4()}_{filename}'
            filepath = os.path.join(UPLOAD_FOLDER, unique_name)

            try:
                file.save(filepath)
                logger.info(f'Arquivo salvo: {filepath}')
            except Exception as e:
                logger.exception(f'Erro ao salvar {filename}: {e}')
                continue

            try:
                excel_file = pd.ExcelFile(filepath)
            except Exception as e:
                logger.exception(f'Erro ao abrir Excel {filepath}: {e}')
                continue

            for sheet_name in excel_file.sheet_names:
                logger.info(f'Processando aba: "{sheet_name}"')
                try:
                    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
                    if df_raw is None or df_raw.shape[0] == 0:
                        continue

                    header_row = find_header_row(df_raw)
                    logger.info(f'Aba "{sheet_name}": cabeçalho na linha {header_row}')

                    df = pd.read_excel(filepath, sheet_name=sheet_name, header=header_row)
                    df.columns = [normalize_column(str(col)) for col in df.columns]
                    df = df.dropna(how='all')

                    if 'name' not in df.columns:
                        logger.warning(f'Aba "{sheet_name}" sem coluna name. Colunas: {list(df.columns)}')
                        continue

                    df = df[df['name'].notna()]
                    df = df[df['name'].astype(str).str.strip().str.lower() != 'nan']
                    df = df[df['name'].astype(str).str.strip() != '']

                    logger.info(f'Aba "{sheet_name}": {len(df)} linhas válidas.')

                    for start in range(0, len(df), chunk_size):
                        chunk_df = df.iloc[start:start + chunk_size]
                        imp, upd = self._process_batch(chunk_df.to_dict('records'), import_mode, is_excel=True)
                        total_imported += imp
                        total_updated += upd

                except Exception as e:
                    logger.exception(f'Erro na aba "{sheet_name}": {e}')
                    continue

        logger.info(f'Excel import concluído: {total_imported} inseridos, {total_updated} atualizados.')
        return total_imported, total_updated

    # ------------------------------------------------------------------ #
    #  BATCH PROCESSOR (unificado para CSV e Excel)                        #
    # ------------------------------------------------------------------ #

    def _process_batch(self, rows, import_mode, is_excel=False):
        total_imported = 0
        total_updated = 0
        session = get_session()
        
        rows = self.merge_duplicate_rows(rows)
        
        try:
            rows = self.merge_duplicate_rows(rows)
            
            for parsed in rows:
                
                existing = self._find_existing_item(session, parsed)
                
                if existing:
                    if import_mode == 'update':
                        self._apply_update(existing, parsed)
                        total_updated += 1
                else:
                    session.add(self._build_item(parsed))
                    total_imported += 1
            session.commit()
            return total_imported, total_updated
        except Exception as e:
            session.rollback()
            logger.exception(f'Erro no batch: {e}')
            return total_imported, total_updated
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  EXPORT                                                              #
    # ------------------------------------------------------------------ #

    def export_csv(self, export_path):
        items = self.get_all_items()
        rows = self._flatten_items(items)
        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        df.to_csv(export_path, index=False)
        return export_path

    def export_excel(self, export_path):
        items = self.get_all_items()
        rows = self._flatten_items(items)
        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        df.to_excel(export_path, index=False)
        return export_path