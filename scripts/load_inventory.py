import argparse
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from config import Config
from scripts.inventory import InventoryManager


def main():
    parser = argparse.ArgumentParser(description='Reset and import inventory data.')
    parser.add_argument('--reset', action='store_true', help='Limpa o banco de dados antes da importação')
    parser.add_argument('--file', default=os.path.join(project_root, 'data', 'sample_inventory.csv'), help='Caminho do arquivo CSV ou Excel para importar')
    parser.add_argument('--mode', choices=['update', 'insert', 'replace'], default='update', help='Modo de importação para arquivos')
    args = parser.parse_args()

    manager = InventoryManager(Config.DATABASE)

    if args.reset:
        print('Zerando o banco de dados de inventário...')
        manager.clear_inventory()

    file_path = os.path.abspath(args.file)
    if not os.path.isfile(file_path):
        print(f'Arquivo não encontrado: {file_path}')
        return

    extension = file_path.rsplit('.', 1)[-1].lower()
    if extension == 'csv':
        imported, updated = manager.import_inventory_csv(file_path, import_mode=args.mode)
    else:
        with open(file_path, 'rb') as f:
            class DummyFile:
                def __init__(self, filename, stream):
                    self.filename = filename
                    self.stream = stream
                def save(self, dst):
                    with open(dst, 'wb') as out:
                        out.write(self.stream.read())

            dummy_file = DummyFile(os.path.basename(file_path), f)
            imported, updated = manager.import_inventory_excel([dummy_file], import_mode=args.mode)

    print(f'Importação concluída: {imported} novos itens e {updated} atualizados.')


if __name__ == '__main__':
    main()
