# Jira Daily Audit


Automatización para enviar, diariamente, 2 issues aleatorios resueltos el día anterior por cada analista a una dirección fija.


## Requisitos
- Python 3.10+
- Cuenta de servicio en Jira con **Browse projects**
- Cuenta SMTP para enviar correos (o integrar Microsoft Graph)


## Setup local
1. Crear virtualenv
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Edita .env con tus credenciales



## Pruba en local 
# Activar entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar pruebas unitarias
pytest -q

# Ejecutar script en modo prueba (no manda correo)
DRY_RUN=true python automation_jira.py
