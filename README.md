# 🏭 Gestor de Estoque Inteligente (GEI)

> Sistema web de gerenciamento de estoque desenvolvido em Python/Flask, com suporte a importação de planilhas Excel, controle de movimentações e alertas de estoque mínimo.

---

## 📋 Sobre o Projeto

O GEI nasceu como projeto de conclusão de curso na **Estácio**, aplicado ao contexto real do almoxarifado do **SENAI**. O sistema permite que equipes de almoxarifado gerenciem seu inventário de forma simples e eficiente — sem depender de planilhas manuais.

A ideia é evoluir o projeto futuramente para algo maior, com mais integrações e funcionalidades avançadas.

---

## ✨ Funcionalidades

- 📦 **Cadastro de itens** — nome, categoria, localização (corredor, armário, prateleira), quantidade e estoque mínimo
- 📊 **Importação de Excel/CSV** — suporte a planilhas com múltiplas abas e detecção automática de cabeçalho
- 🔄 **Modos de importação** — atualizar existentes, adicionar novos ou substituir tudo
- 📉 **Alertas de estoque mínimo** — notificações automáticas para itens abaixo do mínimo
- 🔁 **Movimentações** — registro de entradas, saídas e ajustes com histórico completo
- 📈 **Dashboard** — visão geral do inventário com gráficos de movimentação
- 📤 **Exportação** — exportar inventário em Excel ou CSV
- 👥 **Controle de acesso** — autenticação com perfis de usuário e administrador

---

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 + Flask 3.0 |
| Banco de dados | SQLite (local) / PostgreSQL (produção) |
| ORM | SQLAlchemy 1.4 |
| Planilhas | Pandas + OpenPyXL |
| Frontend | HTML + CSS + JavaScript (vanilla) |
| Autenticação | Werkzeug + Flask Session |
| Deploy | Gunicorn |

---

## 🚀 Como Rodar Localmente

### Pré-requisitos

- Python 3.10+
- PowerShell (Windows) ou Bash (Linux/Mac)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/gei.git
cd gei

# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente virtual
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### Iniciando o servidor

**Windows (recomendado):**
```powershell
.\start.ps1
```

**Manual:**
```bash
python app.py
```

Acesse: [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Login padrão:**
| Campo | Valor |
|---|---|
| Usuário | `user` |
| Senha | `user123` |

> ⚠️ Altere a senha padrão após o primeiro acesso.

---

## 📁 Estrutura do Projeto

```
GEI/
├── app.py                  # Rotas e inicialização do Flask
├── auth.py                 # Autenticação e controle de acesso
├── config.py               # Configurações do sistema
├── db.py                   # Inicialização do banco de dados
├── models.py               # Modelos SQLAlchemy
├── requirements.txt        # Dependências Python
├── start.ps1               # Script de inicialização (Windows)
├── scripts/
│   ├── inventory.py        # Lógica principal de estoque
│   ├── dashboard.py        # Dados do dashboard
│   ├── manager.py          # Gerenciamento de usuários
│   ├── load_inventory.py   # Importação via linha de comando
│   ├── large_import.py     # Importação de arquivos grandes via HTTP
│   └── migrate_sqlite_to_postgres.py  # Migração para PostgreSQL
├── templates/              # Templates HTML (Jinja2)
├── static/                 # CSS, JS e imagens
├── uploads/                # Arquivos enviados pelo usuário
├── exports/                # Arquivos exportados
└── data/                   # Dados de exemplo
```

---

## 📥 Importação de Planilhas

O sistema aceita arquivos `.xlsx`, `.xls` e `.csv` com os seguintes nomes de coluna (em português ou inglês):

| Campo | Colunas aceitas |
|---|---|
| Nome do item | `material`, `nome`, `name`, `item` |
| Quantidade | `quantidade`, `qtd`, `estoque`, `estoque atual` |
| Estoque mínimo | `estoque mínimo`, `mínimo` |
| Categoria | `categoria` |
| Corredor | `corredor` |
| Armário | `armário` |
| Prateleira | `prateleira`, `gaveta` |
| Observação | `observação`, `descrição` |
| Código | `código` |
| Preço | `preço` |

> O cabeçalho pode estar em qualquer linha — o sistema detecta automaticamente.

### Modos de importação

| Modo | Comportamento |
|---|---|
| **Atualizar** | Atualiza itens existentes e adiciona novos |
| **Inserir** | Adiciona apenas itens que ainda não existem |
| **Substituir** | Apaga todo o inventário e reimporta do zero |

---

## ⚙️ Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Chave secreta do Flask (obrigatório em produção)
SECRET_KEY=sua_chave_secreta_aqui

# Banco de dados (opcional — padrão: SQLite local)
DATABASE=sqlite:///gei_database.db
# Para PostgreSQL:
# DATABASE=postgresql://usuario:senha@host:5432/banco

# Habilita limpeza manual do inventário via CLI
ALLOW_CLEAR_INVENTORY=0
```

---

## 🗄️ Migração para PostgreSQL

Para migrar o banco SQLite para PostgreSQL em produção:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --pg-url postgresql://user:pass@host:5432/db \
  --apply
```

Use `--dry-run` para validar antes de aplicar.

---

## 📦 Importação via Linha de Comando

```bash
# Importar um arquivo Excel
python scripts/load_inventory.py --file data/inventario.xlsx --mode update

# Resetar e reimportar
python scripts/load_inventory.py --reset --file data/inventario.xlsx --mode replace
```

---

## 🔮 Próximos Passos

- [ ] API REST completa para integrações externas
- [ ] Aplicativo mobile
- [ ] Leitura de QR Code / código de barras
- [ ] Relatórios em PDF
- [ ] Notificações por e-mail para estoque crítico
- [ ] Multi-unidade (suporte a múltiplos almoxarifados)
- [ ] Integração com sistemas ERP

---

## 🎓 Contexto Acadêmico

Projeto desenvolvido como **Trabalho de Conclusão de Curso** na **Estácio**, com aplicação prática no almoxarifado do **SENAI**. O sistema foi construído do zero com foco em resolver um problema real: a gestão manual de centenas de itens em planilhas desorganizadas.

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">
  Feito com 💙 como projeto acadêmico — com planos de ir muito além.
</div>