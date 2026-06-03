import os
import json
import tempfile
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from werkzeug.utils import secure_filename
from config import Config
from models import init_db
from auth import login_user, logout_user, require_login, require_admin
from scripts.inventory import InventoryManager
from scripts.dashboard import DashboardService
from scripts.manager import UserManager

app = Flask(__name__)
app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
app.secret_key = app.config['SECRET_KEY']
init_db()
manager = InventoryManager(app.config['DATABASE'])
dashboard_service = DashboardService(manager)
user_manager = UserManager(app.config['DATABASE'])


@app.context_processor
def inject_notifications():
    low_stock_items = manager.get_low_stock_items()
    return {
        'low_stock_count': len(low_stock_items),
        'low_stock_notifications': low_stock_items,
    }


@app.route('/')
def home():
    if session.get('username'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if login_user(username, password):
            flash('Login efetuado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha incorretos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@require_login
def dashboard():
    summary = dashboard_service.get_summary()
    return render_template('dashboard.html', **summary)


@app.route('/manager', methods=['GET', 'POST'])
@require_admin
def manager_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', 'user')
        success, message = user_manager.add_user(username, password, confirm_password, role)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('manager_page'))

    users = user_manager.get_all_users()
    return render_template('manager.html', users=users)


@app.route('/inventory', methods=['GET'])
@require_login
def inventory():
    search = request.args.get('search', '').strip()
    page = max(1, int(request.args.get('page', 1)))
    per_page = int(request.args.get('per_page', 10))
    if per_page not in [5, 10, 20, 50]:
        per_page = 10

    all_items = manager.get_all_items(search if search else None)
    total_items = len(all_items)
    total_pages = max(1, -(-total_items // per_page))
    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    items = all_items[start_index:end_index]
    low_stock_items = manager.get_low_stock_items()

    return render_template(
        'inventory.html',
        items=items,
        low_stock_items=low_stock_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_items=total_items,
        per_page_options=[5, 10, 20, 50],
        search=search,
    )


@app.route('/inventory/movements', methods=['GET'])
@require_login
def inventory_movements():
    recent_movements = manager.get_recent_movements(limit=100)
    today = datetime.now().date()
    labels = []
    entrada_totals = []
    saida_totals = []
    for delta in range(6, -1, -1):
        day = today - timedelta(days=delta)
        labels.append(day.strftime('%d/%m'))
        entrada_totals.append(0)
        saida_totals.append(0)

    for movement in recent_movements:
        try:
            movement_date = datetime.strptime(movement['created_at'], '%Y-%m-%d %H:%M:%S').date()
        except Exception:
            continue
        label = movement_date.strftime('%d/%m')
        if label in labels:
            index = labels.index(label)
            if movement['type'] == 'entrada':
                entrada_totals[index] += movement['quantity']
            elif movement['type'] == 'saida':
                saida_totals[index] += movement['quantity']

    total_entrada = sum(entrada_totals)
    total_saida = sum(saida_totals)
    total_movements = len(recent_movements)

    return render_template(
        'movements.html',
        recent_movements=recent_movements,
        movement_chart_labels=json.dumps(labels, ensure_ascii=False),
        movement_chart_entrada=json.dumps(entrada_totals),
        movement_chart_saida=json.dumps(saida_totals),
        total_entrada=total_entrada,
        total_saida=total_saida,
        total_movements=total_movements,
    )


@app.route('/inventory/add', methods=['POST'])
@require_login
def inventory_add():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    quantity = int(request.form.get('quantity', 0))
    minimum_quantity = int(request.form.get('minimum_quantity', 0))
    corridor = request.form.get('corridor', '').strip()
    cabinet = request.form.get('cabinet', '').strip()
    shelf = request.form.get('shelf', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Material obrigatório.', 'warning')
        return redirect(url_for('inventory'))
    manager.add_item('', name, category, quantity, minimum_quantity, 0.0, corridor, cabinet, shelf, description, '')
    flash('Item adicionado ao estoque.', 'success')
    return redirect(url_for('inventory'))


@app.route('/inventory/update-meta', methods=['POST'])
@require_login
def inventory_update_meta():
    item_id = int(request.form.get('item_id', 0))
    category = request.form.get('category', '').strip()
    minimum_quantity_value = request.form.get('minimum_quantity', '').strip()
    minimum_quantity = int(minimum_quantity_value) if minimum_quantity_value != '' else None
    if not category and minimum_quantity is None:
        flash('Informe categoria ou mínimo.', 'warning')
        return redirect(url_for('inventory'))

    success = manager.update_item_meta(
        item_id,
        category=category if category else None,
        minimum_quantity=minimum_quantity,
    )
    if success:
        flash('Dados do item atualizados.', 'success')
    else:
        flash('Item não encontrado.', 'danger')
    return redirect(url_for('inventory'))


@app.route('/inventory/update', methods=['POST'])
@require_login
def inventory_update():
    item_id = int(request.form.get('item_id', 0))
    new_quantity = int(request.form.get('new_quantity', 0))
    result = manager.record_movement(item_id, 'ajuste', new_quantity, 'Atualização rápida')
    if result is not False:
        flash('Quantidade atualizada.', 'success')
    else:
        flash('Item não encontrado.', 'danger')
    return redirect(url_for('inventory'))


@app.route('/inventory/movement', methods=['POST'])
@require_login
def inventory_movement():
    item_id = int(request.form.get('item_id', 0))
    movement_type = request.form.get('movement_type', 'ajuste')
    movement_quantity = int(request.form.get('movement_quantity', 0))
    movement_reason = request.form.get('movement_reason', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if movement_quantity <= 0:
        if is_ajax:
            return jsonify(success=False, message='Informe uma quantidade válida para a movimentação.'), 400
        flash('Informe uma quantidade válida para a movimentação.', 'warning')
        return redirect(url_for('inventory'))

    new_quantity = manager.record_movement(item_id, movement_type, movement_quantity, movement_reason)
    if new_quantity is not False:
        if is_ajax:
            return jsonify(success=True, new_quantity=new_quantity)
        flash('Movimentação registrada.', 'success')
        return redirect(url_for('inventory'))

    if is_ajax:
        return jsonify(success=False, message='Item não encontrado.'), 404
    flash('Item não encontrado.', 'danger')
    return redirect(url_for('inventory'))


@app.route('/inventory/import', methods=['POST'])
@require_login
def import_inventory_file():
    files = request.files.getlist('data_files')
    import_mode = request.form.get('import_mode', 'update')
    imported = 0
    updated = 0

    try:
        for file in files:
            if file and '.' in file.filename:
                extension = file.filename.rsplit('.', 1)[1].lower()
                if extension not in {'xlsx', 'xls', 'csv'}:
                    continue

                if extension == 'csv':
                    temp_dir = tempfile.gettempdir()
                    os.makedirs(temp_dir, exist_ok=True)
                    filepath = os.path.join(temp_dir, secure_filename(f'{uuid.uuid4()}_{file.filename}'))
                    file.save(filepath)
                    imported_file, updated_file = manager.import_inventory_csv(filepath, import_mode)
                    imported += imported_file
                    updated += updated_file
                else:
                    imported_file, updated_file = manager.import_inventory_excel([file], import_mode)
                    imported += imported_file
                    updated += updated_file

        flash(f'Importação concluída. {imported} novos itens e {updated} atualizados.', 'success')
    except Exception as e:
        app.logger.exception('Erro durante a importação de arquivos')
        flash('Erro ao importar arquivos: ' + str(e), 'danger')

    return redirect(url_for('inventory'))


@app.route('/inventory/export')
@require_login
def export_inventory():
    # Compatibilidade com chamadas antigas no template.
    return redirect(url_for('export_inventory_csv'))


@app.route('/inventory/export/csv')
@require_login
def export_inventory_csv():
    export_path = manager.export_csv(os.path.join('data', 'inventory_export.csv'))
    return send_file(export_path, as_attachment=True)


@app.route('/inventory/export/excel')
@require_login
def export_inventory_excel():
    export_path = manager.export_excel(os.path.join('data', 'inventory_export.xlsx'))
    return send_file(export_path, as_attachment=True)


@app.route('/api/create_admin', methods=['POST'])
def api_create_admin():
    token = request.headers.get('X-Admin-Token')
    if token != app.config.get('SECRET_KEY'):
        return {'success': False, 'message': 'Unauthorized'}, 401
    from models import ensure_admin_user
    ensure_admin_user('admin123', app.config['DATABASE'])
    return {'success': True, 'message': 'Admin user created/updated.'}


@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    # Return low stock notifications for frontend consumption
    items = manager.get_low_stock_items()
    # Serialize rows to plain dicts suitable for JSON
    simplified = [
        {
            'id': item.get('id'),
            'name': item.get('name'),
            'quantity': item.get('quantity'),
            'minimum_quantity': item.get('minimum_quantity'),
            'category': item.get('category'),
            'classification': item.get('classification'),
        }
        for item in items
    ]
    return jsonify(count=len(simplified), items=simplified)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host=host, port=port)
