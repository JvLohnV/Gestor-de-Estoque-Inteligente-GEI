import csv
import json
import os
import uuid
import pandas as pd
from werkzeug.utils import secure_filename
from models import get_db_connection
from config import Config

UPLOAD_FOLDER = 'uploads/excels'
EXPORT_FOLDER = 'exports'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
        'armario': 'cabinet',
        'prateleira': 'shelf',
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


class InventoryManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DATABASE

    def _parse_row(self, row):
        parsed = {normalize_column(str(k)): v for k, v in row.items() if k is not None}

        def parse_int(value):
            try:
                if value is None or str(value).strip() == '':
                    return 0
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        def parse_float(value):
            try:
                if value is None or str(value).strip() == '':
                    return 0.0
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        name = str(parsed.get('name', '')).strip()
        if not name or name.lower() == 'nan':
            return None

        code = str(parsed.get('code', '') or '')
        category = str(parsed.get('category', '') or '')
        classification = str(parsed.get('classification', '') or '')
        quantity = parse_int(parsed.get('quantity', 0))
        minimum_quantity = parse_int(parsed.get('minimum_quantity', 0))
        price = parse_float(parsed.get('price', 0))
        corridor = str(parsed.get('corridor', '') or '')
        cabinet = str(parsed.get('cabinet', '') or '')
        shelf = str(parsed.get('shelf', '') or '')
        description = str(parsed.get('description', '') or '')

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
                extra_data[key] = value

        return {
            'code': code,
            'name': name,
            'category': category,
            'classification': classification,
            'quantity': quantity,
            'minimum_quantity': minimum_quantity,
            'price': price,
            'corridor': corridor,
            'cabinet': cabinet,
            'shelf': shelf,
            'description': description,
            'extra_data': json.dumps(extra_data, ensure_ascii=False),
        }

    def _row_to_item(self, row):
        item = dict(row)
        try:
            item['extra_data'] = json.loads(item.get('extra_data') or '{}')
        except Exception:
            item['extra_data'] = {}
        return item

    def _flatten_items(self, items):
        rows = []
        for item in items:
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

    def clear_inventory(self):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM inventory_items')
        cursor.execute('DELETE FROM stock_movements')
        conn.commit()
        conn.close()

    def get_all_items(self, search=None):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        if search:
            pattern = f'%{search}%'
            cursor.execute(
                '''
                SELECT *
                FROM inventory_items
                WHERE name LIKE ? OR category LIKE ? OR description LIKE ? OR code LIKE ?
                ORDER BY name
                ''',
                (pattern, pattern, pattern, pattern)
            )
        else:
            cursor.execute('SELECT * FROM inventory_items ORDER BY name')
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_item(row) for row in rows]

    def get_low_stock_items(self):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT *
            FROM inventory_items
            WHERE quantity <= minimum_quantity
            ORDER BY quantity ASC
            '''
        )
        rows = cursor.fetchall()
        conn.close()
        items = [self._row_to_item(row) for row in rows]

        # Annotate each item with an alert type for clearer messaging
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
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT *
            FROM stock_movements
            ORDER BY created_at DESC
            LIMIT ?
            ''',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_item(self, code, name, category, quantity, minimum_quantity, price, corridor, cabinet, shelf, description, classification='', extra_data=None):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO inventory_items (
                code, name, category, classification, quantity, minimum_quantity, price,
                corridor, cabinet, shelf, description, extra_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (code, name, category, classification, quantity, minimum_quantity, price, corridor, cabinet, shelf, description, json.dumps(extra_data or {}, ensure_ascii=False))
        )
        conn.commit()
        conn.close()

    def record_movement(self, item_id, movement_type, movement_quantity, movement_reason):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM inventory_items WHERE id = ?', (item_id,))
        item = cursor.fetchone()
        if not item:
            conn.close()
            return False

        previous_quantity = item['quantity']
        if movement_type == 'entrada':
            new_quantity = previous_quantity + movement_quantity
        elif movement_type == 'saida':
            new_quantity = previous_quantity - movement_quantity
            if new_quantity < 0:
                new_quantity = 0
        else:
            new_quantity = movement_quantity

        cursor.execute('UPDATE inventory_items SET quantity = ? WHERE id = ?', (new_quantity, item_id))
        cursor.execute(
            '''
            INSERT INTO stock_movements (
                item_id, item_name, type, quantity,
                previous_quantity, new_quantity, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (item_id, item['name'], movement_type, movement_quantity, previous_quantity, new_quantity, movement_reason)
        )
        conn.commit()
        conn.close()
        return new_quantity

    def update_item_meta(self, item_id, category=None, minimum_quantity=None):
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        updates = []
        params = []
        if category is not None:
            updates.append('category = ?')
            params.append(category)
        if minimum_quantity is not None:
            updates.append('minimum_quantity = ?')
            params.append(minimum_quantity)
        if not updates:
            conn.close()
            return False
        params.append(item_id)
        cursor.execute(f'UPDATE inventory_items SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def import_inventory_csv(self, csv_filepath, import_mode='update', chunk_size=1000):
        total_imported = 0
        total_updated = 0

        if import_mode == 'replace':
            self.clear_inventory()
            import_mode = 'update'

        if not os.path.isfile(csv_filepath):
            return total_imported, total_updated

        with open(csv_filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames:
                reader.fieldnames = [normalize_column(col) for col in reader.fieldnames]
            
            batch_rows = []
            for row in reader:
                batch_rows.append(row)
                if len(batch_rows) >= chunk_size:
                    imported, updated = self._process_csv_batch(batch_rows, import_mode)
                    total_imported += imported
                    total_updated += updated
                    batch_rows = []
            
            # Process remaining rows
            if batch_rows:
                imported, updated = self._process_csv_batch(batch_rows, import_mode)
                total_imported += imported
                total_updated += updated

        return total_imported, total_updated
    
    def _process_csv_batch(self, rows, import_mode):
        total_imported = 0
        total_updated = 0
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        for row in rows:
            parsed = self._parse_row(row)
            if not parsed:
                continue

            cursor.execute('SELECT * FROM inventory_items WHERE name = ?', (parsed['name'],))
            existing = cursor.fetchone()
            if existing:
                if import_mode == 'update':
                    new_quantity = existing['quantity'] + parsed['quantity']
                    cursor.execute(
                        '''
                        UPDATE inventory_items
                        SET quantity = ?, category = ?, classification = ?, description = ?, corridor = ?, cabinet = ?, shelf = ?, price = ?, code = ?, minimum_quantity = ?, extra_data = ?
                        WHERE id = ?
                        ''',
                        (
                            new_quantity,
                            parsed['category'],
                            parsed['classification'],
                            parsed['description'],
                            parsed['corridor'],
                            parsed['cabinet'],
                            parsed['shelf'],
                            parsed['price'],
                            parsed['code'],
                            parsed['minimum_quantity'],
                            parsed['extra_data'],
                            existing['id'],
                        )
                    )
                    total_updated += 1
            else:
                cursor.execute(
                    '''
                    INSERT INTO inventory_items (
                        code, name, category, classification, quantity,
                        minimum_quantity, price, corridor, cabinet,
                        shelf, description, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        parsed['code'],
                        parsed['name'],
                        parsed['category'],
                        parsed['classification'],
                        parsed['quantity'],
                        parsed['minimum_quantity'],
                        parsed['price'],
                        parsed['corridor'],
                        parsed['cabinet'],
                        parsed['shelf'],
                        parsed['description'],
                        parsed['extra_data'],
                    )
                )
                total_imported += 1
        
        conn.commit()
        conn.close()
        return total_imported, total_updated

    def import_inventory_excel(self, files, import_mode='update', chunk_size=1000):
        total_imported = 0
        total_updated = 0

        if import_mode == 'replace':
            self.clear_inventory()
            import_mode = 'update'

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f'{uuid.uuid4()}_{filename}'
                filepath = os.path.join(UPLOAD_FOLDER, unique_name)
                file.save(filepath)
                excel_file = pd.ExcelFile(filepath)

                for sheet_name in excel_file.sheet_names:
                    try:
                        # Read the whole sheet, then process in chunks to avoid loading everything into DB transaction
                        df = pd.read_excel(filepath, sheet_name=sheet_name)
                        if df is None or df.shape[0] == 0:
                            continue
                        df.columns = [normalize_column(col) for col in df.columns]
                        df = df.dropna(how='all')
                        if 'name' not in df.columns:
                            continue

                        # iterate in chunks (DataFrame slicing)
                        for start in range(0, len(df), chunk_size):
                            chunk_df = df.iloc[start:start+chunk_size]
                            imported, updated = self._process_excel_batch(chunk_df, import_mode)
                            total_imported += imported
                            total_updated += updated
                    except Exception:
                        # skip problematic sheets but continue with others
                        continue

        return total_imported, total_updated
    
    def _process_excel_batch(self, df, import_mode):
        total_imported = 0
        total_updated = 0
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            parsed = self._parse_row(row)
            if not parsed:
                continue

            cursor.execute('SELECT * FROM inventory_items WHERE name = ?', (parsed['name'],))
            existing = cursor.fetchone()
            if existing:
                if import_mode == 'update':
                    new_quantity = existing['quantity'] + parsed['quantity']
                    cursor.execute(
                        '''
                        UPDATE inventory_items
                        SET quantity = ?, category = ?, classification = ?, description = ?, corridor = ?, cabinet = ?, shelf = ?, price = ?, code = ?, minimum_quantity = ?, extra_data = ?
                        WHERE id = ?
                        ''',
                        (
                            new_quantity,
                            parsed['category'],
                            parsed['classification'],
                            parsed['description'],
                            parsed['corridor'],
                            parsed['cabinet'],
                            parsed['shelf'],
                            parsed['price'],
                            parsed['code'],
                            parsed['minimum_quantity'],
                            parsed['extra_data'],
                            existing['id'],
                        )
                    )
                    total_updated += 1
            else:
                cursor.execute(
                    '''
                    INSERT INTO inventory_items (
                        code, name, category, classification, quantity,
                        minimum_quantity, price, corridor, cabinet,
                        shelf, description, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        parsed['code'],
                        parsed['name'],
                        parsed['category'],
                        parsed['classification'],
                        parsed['quantity'],
                        parsed['minimum_quantity'],
                        parsed['price'],
                        parsed['corridor'],
                        parsed['cabinet'],
                        parsed['shelf'],
                        parsed['description'],
                        parsed['extra_data'],
                    )
                )
                total_imported += 1
        
        conn.commit()
        conn.close()
        return total_imported, total_updated

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
