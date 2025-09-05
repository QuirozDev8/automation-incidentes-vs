# Auditoría diaria de issues Jira (Mailer)

Script en Python para automatizar un resumen diario de issues resueltos en Jira y enviarlo por correo electrónico (HTML con enlaces). Puede ejecutarse localmente o en GitHub Actions, programado todos los días a las 09:00 a. m. (America/Bogota).

### Tabla de contenidos

¿Qué hace?

Estructura del repositorio (sugerida)

Variables de Entorno

Plantillas de .env

Instalación local

Cómo funciona el script (función por función)

Cambiar “ayer” por “hoy” (prueba rápida)

Programarlo en GitHub Actions (09:00 America/Bogota)

Troubleshooting rápido

Cómo subir a Git y activar la automatización

Personalizaciones útiles

¿Qué hace?

Construye una JQL relativa para “ayer” (o “hoy” si lo ajustas).

Consulta Jira (paginado) y obtiene los issues resueltos.

Agrupa por responsable (assignee), incluyendo un grupo (Sin asignar).

Selecciona N casos aleatorios por analista.

Genera un HTML (con links a cada issue) y lo envía por correo.

En modo DRY_RUN, guarda una vista previa HTML en disco y muestra un resumen en consola.

Pensado para ejecutarse localmente o en GitHub Actions.

### Estructura del repositorio (sugerida)
/automation-risk-vs
  ├─ automation_jira.py        # script principal
  ├─ requirements.txt          # dependencias
  ├─ README.md                 # este archivo
  └─ .gitignore                # ignorar .env, etc.

requirements.txt (ejemplo)
python-dotenv==1.0.1
requests==2.32.3
msal==1.29.0        # solo si usarás Microsoft Graph

.gitignore (fragmento)
.env                  # ¡no commitear nunca!
__pycache__/
auditoria_preview_*.html

Variables de Entorno

Crea un archivo .env (no lo subas a git). No pongas credenciales en el código.

Variable	Obligatoria	Descripción
JIRA_BASE_URL	Sí	Base URL de Jira Cloud (ej. https://empresa.atlassian.net)
JIRA_EMAIL	Sí	Usuario con permisos de lectura en Jira
JIRA_API_TOKEN	Sí	API token de Jira
JIRA_PROJECT_KEYS	Sí	Proyectos separados por coma (ej. DEVS,VSIN,IV)
PER_ANALYST	Sí	Nº de issues aleatorios por analista (entero)
RECIPIENT_EMAIL	Sí	Destinatarios separados por coma
SENDER_EMAIL	Sí	Dirección de envío (debe existir y tener permisos)
SMTP_SERVER	Sí*	Servidor SMTP (ej. smtp.gmail.com, smtp.office365.com)
SMTP_PORT	Sí*	Puerto SMTP (recomendado 587 con STARTTLS)
SMTP_USERNAME	No	Usuario SMTP (por defecto = SENDER_EMAIL)
SMTP_PASSWORD	No	Contraseña/App Password SMTP
DRY_RUN	No	true o false (por defecto true)
FROM_NAME	No	Nombre visible del remitente (ej. “Auditoría Jira VS”)
REPLY_TO	No	Email para respuestas
USE_GRAPH	No	true para Microsoft Graph (OAuth), false para SMTP
TENANT_ID	Cond.	Requerido si USE_GRAPH=true
CLIENT_ID	Cond.	Requerido si USE_GRAPH=true

* Requeridas si USE_GRAPH=false (SMTP).

Plantillas de .env
Gmail (prueba rápida con App Password)
JIRA_BASE_URL=https://empresa.atlassian.net
JIRA_EMAIL=tu.jira@empresa.com
JIRA_API_TOKEN=xxxxxxxxxxxxxxxx
JIRA_PROJECT_KEYS=DEVS,VSIN
PER_ANALYST=3

RECIPIENT_EMAIL=tuusuario@gmail.com
SENDER_EMAIL=tuusuario@gmail.com
SMTP_USERNAME=tuusuario@gmail.com
SMTP_PASSWORD=APP_PASSWORD_16chars
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
DRY_RUN=false

FROM_NAME=Auditoría Jira VS
REPLY_TO=tuusuario@gmail.com
USE_GRAPH=false

Microsoft 365 (SMTP) – requiere SMTP AUTH habilitado por TI
JIRA_BASE_URL=https://empresa.atlassian.net
JIRA_EMAIL=tu.jira@empresa.com
JIRA_API_TOKEN=xxxxxxxxxxxxxxxx
JIRA_PROJECT_KEYS=DEVS,VSIN
PER_ANALYST=3

RECIPIENT_EMAIL=auditoria@empresa.com
SENDER_EMAIL=auditoria-jira@tu-dominio.com
SMTP_USERNAME=auditoria-jira@tu-dominio.com
SMTP_PASSWORD=********
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
DRY_RUN=false
USE_GRAPH=false

Microsoft Graph (sin SMTP, por OAuth – Device Code)
JIRA_BASE_URL=https://empresa.atlassian.net
JIRA_EMAIL=tu.jira@empresa.com
JIRA_API_TOKEN=xxxxxxxxxxxxxxxx
JIRA_PROJECT_KEYS=DEVS,VSIN
PER_ANALYST=3

RECIPIENT_EMAIL=auditoria@empresa.com
SENDER_EMAIL=tu.nombre@tu-dominio.com
DRY_RUN=false

USE_GRAPH=true
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CLIENT_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy


Con Graph, el script mostrará una URL y un código (Device Code Flow) para autorizar el envío como tu usuario (si el tenant lo permite).

Instalación local

Requisitos: Python 3.10+ (recomendado 3.12).

Instalar dependencias:

pip install -r requirements.txt


Crear y completar .env (ver plantillas).

Ejecutar en modo prueba:

# DRY_RUN=true en .env → no envía; guarda auditoria_preview_*.html
python automation_jira.py

Ejecutar envío real (recomendado primero a tu propio correo):

# Cambia DRY_RUN=false en .env
python automation_jira.py


Tip (Windows Git Bash): si ves líneas repetidas, prueba en PowerShell o usa python -u automation_jira.py.

Cómo funciona el script (función por función)

load_settings()
Carga .env, valida variables obligatorias, hace casts (int) y defaults. Imprime un [ENV CHECK] de presencia (no valores).

build_jql_relative(project_keys)
Devuelve una JQL para “ayer”:

resolved >= startOfDay(-1) AND resolved <= endOfDay(-1)


(Para “hoy” usa startOfDay(0) / endOfDay(0).)

fetch_all_issues(base_url, auth, jql)
Llama a /rest/api/3/search con paginado (100 por página). Pide solo campos necesarios:
key, summary, assignee, reporter, resolutiondate. Timeout 30s.

summarize_assignee_stats(issues)
Imprime conteo con/sin assignee (diagnóstico rápido).

group_by_assignee(issues)
Agrupa por analista; si no hay assignee, usa la clave ("UNASSIGNED","(Sin asignar)").

pick_random_per_analyst(groups, per_analyst)
Toma N aleatorios por analista (si hay menos, toma todos).

build_email_html(base_url, target_date, selection, total_issues)
Construye el HTML con:

Título con la fecha (alineada a America/Bogota),

Total de issues,

Bloques por responsable,

Por issue: link, resumen y responsable en negrita.

print_console_summary(base_url, selection, total_issues) (opcional)
Resumen legible en consola (nombre, key, resumen, URL).

send_email(cfg, subject, html_body)

Si USE_GRAPH=true: envía por Microsoft Graph (OAuth Device Code).

Si USE_GRAPH=false: envía por SMTP (STARTTLS).

En DRY_RUN, guarda auditoria_preview_*.html y no envía.

send_email_via_graph(cfg, subject, html_body)
(Solo si activas Graph) Pide token con MSAL (device flow) y llama POST /me/sendMail en Graph.

get_yesterday_bogota()
Calcula la fecha de “ayer” en America/Bogota para asunto/encabezado.

main()
Orquesta: carga config → arma JQL → consulta Jira → agrupa → selecciona → construye HTML → envía/guarda.

Cambiar “ayer” por “hoy” (prueba rápida)

En build_jql_relative() cambia:

- resolved >= startOfDay(-1) AND resolved <= endOfDay(-1)
+ resolved >= startOfDay(0)  AND resolved <= endOfDay(0)


(O crea una función build_jql_today() y úsala en main().)

Programarlo en GitHub Actions (09:00 America/Bogota)

GitHub Actions usa UTC. Bogotá (sin DST) = UTC-5 → 09:00 BOG = 14:00 UTC.

Crea .github/workflows/audit.yml:

name: Jira Daily Audit Mailer

on:
  schedule:
    - cron: "0 14 * * *"    # 14:00 UTC = 09:00 America/Bogota
  workflow_dispatch:        # permitir ejecutarlo manualmente

jobs:
  run-audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      # Opción 1: Enviar por SMTP (ej. Gmail/M365)
      - name: Run audit (SMTP)
        if: ${{ env.USE_GRAPH != 'true' }}
        env:
          JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          JIRA_PROJECT_KEYS: ${{ secrets.JIRA_PROJECT_KEYS }}
          PER_ANALYST: ${{ secrets.PER_ANALYST }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          DRY_RUN: "false"
          FROM_NAME: ${{ secrets.FROM_NAME }}
          REPLY_TO: ${{ secrets.REPLY_TO }}
          USE_GRAPH: "false"
        run: |
          python automation_jira.py

      # Opción 2: Enviar por Microsoft Graph (sin SMTP)
      - name: Run audit (Graph)
        if: ${{ env.USE_GRAPH == 'true' }}
        env:
          JIRA_BASE_URL: ${{ secrets.JIRA_BASE_URL }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          JIRA_PROJECT_KEYS: ${{ secrets.JIRA_PROJECT_KEYS }}
          PER_ANALYST: ${{ secrets.PER_ANALYST }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          DRY_RUN: "false"
          FROM_NAME: ${{ secrets.FROM_NAME }}
          REPLY_TO: ${{ secrets.REPLY_TO }}
          USE_GRAPH: "true"
          TENANT_ID: ${{ secrets.TENANT_ID }}
          CLIENT_ID: ${{ secrets.CLIENT_ID }}
        run: |
          python automation_jira.py


Secrets en GitHub: Settings → Secrets and variables → Actions → New repository secret.
Crea un secret por cada variable usada en el workflow.

Gmail: usar App Password como SMTP_PASSWORD.

M365 (SMTP): requiere Authenticated SMTP habilitado por TI (tenant y usuario).

Graph: necesitas TENANT_ID y CLIENT_ID. Si el tenant no permite “user consent”, TI debe aprobar la app o consentir Mail.Send.

Troubleshooting rápido

535 5.7.139 ... SMTP AUTH disabled (M365): SMTP deshabilitado en el tenant. Usa Graph o pide a TI habilitarlo.

534-5.7.9 Application-specific password required (Gmail): falta App Password.

No muestra links en consola: el correo va en HTML; abre la vista previa auditoria_preview_*.html o usa print_console_summary.

Muchos prints repetidos en Git Bash: es el terminal; prueba en PowerShell o python -u.

Cómo subir a Git y activar la automatización
git init
git add .
git commit -m "feat: auditoría diaria Jira (mailer)"
git branch -M main
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main


En GitHub, agrega Secrets (ver arriba).

Revisa el workflow en Actions y, si quieres, ejecuta Run workflow.

Verifica tu inbox a las 09:00 a. m. (Bogotá).

Personalizaciones útiles

Rango de fechas: añade build_jql_today() o un flag CLI --day=0/-1 con argparse.

Más campos: agrega a fields en fetch_all_issues y muéstralos en el HTML.

Adjuntar CSV/Excel: genera el archivo (p. ej., csv/xlsxwriter) y adjúntalo al correo (MIME multipart).