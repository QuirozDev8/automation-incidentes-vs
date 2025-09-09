# Auditoría diaria de issues Jira (Mailer)
Automatiza un resumen diario de issues resueltos en Jira Cloud y lo envía por correo HTML (con enlaces a cada issue y responsable). Puede ejecutarse localmente (modo DRY_RUN) o de forma programada con GitHub Actions.

## Contenidos

- Descripción
- Requisitos previos
- Instalación
- Uso (consola)
- Programación con GitHub Actions
- Variables de entorno
- Contribución
- Licencia

## Descripción
El script:
- Construye una JQL relativa para un rango (por defecto “ayer”).
- Consulta Jira (con paginado) y obtiene issues resueltos.
- Agrupa por responsable (assignee) y selecciona N aleatorios por analista.
- Genera un HTML estilado con links a cada issue.
- Envía el resultado por SMTP (o Microsoft Graph, opcional).
- En DRY_RUN=true no envía: guarda una vista previa HTML y muestra un resumen en consola.

## Requisitos previos

- Python 3.10+ (recomendado 3.12)
- Acceso a Jira Cloud con API Token
- Cuenta de correo para envío:
  - Gmail con App Password (16 caracteres), o
  - Microsoft 365 SMTP con SMTP AUTH habilitado, o
  - Microsoft Graph (OAuth, opcional)
- GitHub Actions (si deseas ejecución programada)

# Instalación

```bash
  # 1) Clonar el repositorio
  git clone https://github.com/<tu-usuario>/<tu-repo>.git
  cd <tu-repo>

  # 2) Crear y activar entorno (opcional, recomendado)
  python -m venv .venv
  # Windows
  .venv\Scripts\activate
  # macOS/Linux
  source .venv/bin/activate

  # 3) Instalar dependencias
  pip install -r requirements.txt
```

# Uso (consola)
### 1) Configurar variables
Crea un archivo .env en la raíz (ver Variables de entorno).

### 2) Prueba sin envío (DRY_RUN=true)

```bash
 python automation_jira.py
```
- No envía correo.
- Guarda auditoria_preview_YYYYmmdd_HHMMSS.html para revisar el diseño.

### 3) Envío real (DRY_RUN=false)
 ```bash 
 python automation_jira.py
```
** Tip: para pruebas, deja RECIPIENT_EMAIL solo con tu correo y PER_ANALYST=1. **

# Programación con GitHub Actions
Crea .github/workflows/daily_audit.yml:

```python
name: Jira Daily Audit Mailer

on:
  schedule:
    - cron: "0 14 * * *"   # 14:00 UTC = 09:00 America/Bogota
  workflow_dispatch:       # ejecución manual

jobs:
  run-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements.txt
      - run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run audit
        env:
          # Jira
          JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          JIRA_PROJECT_KEYS: ${{ secrets.JIRA_PROJECT_KEYS }}
          PER_ANALYST: ${{ secrets.PER_ANALYST }}
          # Mail (Gmail SMTP ejemplo)
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          SMTP_SERVER: smtp.gmail.com
          SMTP_PORT: "587"
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}   # App Password
          FROM_NAME: ${{ secrets.FROM_NAME }}
          REPLY_TO: ${{ secrets.REPLY_TO }}
          # Flags
          DRY_RUN: "false"
          USE_GRAPH: "false"
        run: |
          python automation_jira.py
```
> Secrets necesarios: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEYS, PER_ANALYST, RECIPIENT_EMAIL, SENDER_EMAIL, SMTP_USERNAME, SMTP_PASSWORD (y opcionales FROM_NAME, REPLY_TO).
> En repos privados el uso de Actions consume minutos del plan; para este flujo (segundos por día) es despreciable.

# vrbles de entorno
Crea un archivo .env (no lo subas a git). Ejemplo Gmail:

```
# Jira
JIRA_BASE_URL=https://tuorg.atlassian.net
JIRA_EMAIL=tu.usuario@empresa.com
JIRA_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
JIRA_PROJECT_KEYS=SJ,DEVS
PER_ANALYST=3

# Correo (Gmail SMTP)
RECIPIENT_EMAIL=destino@empresa.com
SENDER_EMAIL=tu.gmail@gmail.com
SMTP_USERNAME=tu.gmail@gmail.com
SMTP_PASSWORD=APP_PASSWORD_16CHARS
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Opcionales
DRY_RUN=true
FROM_NAME=Auditoría Jira
REPLY_TO=tu.gmail@gmail.com
USE_GRAPH=false

# Alertas (opcional si configuraste notificación de fallos en Actions)
ALERT_EMAILS=alertas@empresa.com

```
## 📑 Campos admitidos

| Variable         | Oblig. | Descripción                                                                 |
|------------------|--------|-----------------------------------------------------------------------------|
| `JIRA_BASE_URL`  | Sí     | Base de Jira Cloud (p.ej. `https://org.atlassian.net`).                      |
| `JIRA_EMAIL`     | Sí     | Usuario con permisos de lectura.                                            |
| `JIRA_API_TOKEN` | Sí     | API token de Jira (para `JIRA_EMAIL`).                                      |
| `JIRA_PROJECT_KEYS` | Sí  | Claves de proyectos separadas por coma (SJ,DEVS).                           |
| `PER_ANALYST`    | Sí     | Nº de issues aleatorios por analista (entero).                              |
| `RECIPIENT_EMAIL`| Sí     | Destinatarios separados por coma.                                           |
| `SENDER_EMAIL`   | Sí     | Remitente (debe existir y tener permisos de envío).                         |
| `SMTP_SERVER`    | Sí     | SMTP host (Gmail: `smtp.gmail.com`, M365: `smtp.office365.com`).            |
| `SMTP_PORT`      | Sí     | Puerto SMTP (recomendado 587 con STARTTLS).                                |
| `SMTP_USERNAME`  | No     | Usuario SMTP (por defecto `SENDER_EMAIL`).                                  |
| `SMTP_PASSWORD`  | No     | Contraseña/App Password SMTP.                                               |
| `DRY_RUN`        | No     | `true/false`. En `true` no envía y guarda vista previa.                     |
| `FROM_NAME`      | No     | Nombre visible del remitente.                                               |
| `REPLY_TO`       | No     | Dirección para respuestas.                                                  |
| `USE_GRAPH`      | No     | `true` para Microsoft Graph; `false` para SMTP.                             |
| `TENANT_ID`      | Cond.  | Requerido si `USE_GRAPH=true`.                                              |
| `CLIENT_ID`      | Cond.  | Requerido si `USE_GRAPH=true`.                                              |
| `ALERT_EMAILS`   | No     | Lista de correos para alertas en fallo (si configuras notificación).         |


> Gmail: requiere App Password (no la contraseña normal).
> M365 SMTP: requiere Authenticated SMTP habilitado por TI.
> Graph: requiere consentimiento para Mail.Send.


```vbnet
MIT License

Copyright (c) <Año> <Autor>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
```
