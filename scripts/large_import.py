import requests
import time

base = 'http://127.0.0.1:5000'
with requests.Session() as s:
    # login
    r = s.post(base + '/login', data={'username': 'admin', 'password': 'admin123'})
    print('login', r.status_code)
    
    # upload large file
    start = time.time()
    files = [('data_files', open('data/large.csv', 'rb'))]
    data = {'import_mode': 'replace'}
    r = s.post(base + '/inventory/import', files=files, data=data, timeout=600)
    elapsed = time.time() - start
    
    print(f'import {r.status_code} in {elapsed:.1f}s')
    
    # Extract flash message from HTML
    if 'Importação concluída' in r.text:
        import re
        match = re.search(r'Importação concluída[^<]*', r.text)
        if match:
            print('Result:', match.group(0))
    elif 'Erro' in r.text:
        import re
        match = re.search(r'Erro[^<]*', r.text)
        if match:
            print('Error:', match.group(0))
