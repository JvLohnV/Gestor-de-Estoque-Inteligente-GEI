<#  .\start.ps1  #>

# 1. Libera execução de scripts apenas nesta sessão
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. Ativa o ambiente virtual
.\venv\Scripts\Activate.ps1

# 3. Instala dependências
pip install -r requirements.txt

# 5. Inicia o servidor Flask
python app.py
