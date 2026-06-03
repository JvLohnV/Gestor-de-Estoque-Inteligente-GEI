import requests

base = 'http://127.0.0.1:5000'
with requests.Session() as s:
    # login
    r = s.post(base + '/login', data={'username': 'admin', 'password': 'admin123'})
    print('login', r.status_code)
    # upload file
    files = [('data_files', open('data/sample_inventory.csv', 'rb'))]
    data = {'import_mode': 'replace'}
    r = s.post(base + '/inventory/import', files=files, data=data)
    print('import', r.status_code)
    print(r.text[:400])
