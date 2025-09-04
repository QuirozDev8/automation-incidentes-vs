"""
jira_daily_audit_mailer.py
--------------------------------
Script para Jira Cloud que:
1. Consulta issues resueltos el día anterior.
2. Agrupa por analista (asignee).
3. Selecciona N aleatorios por analista.
4. Envía un correo con los resultados.

Se puede ejecutar:
- Localmente (con DRY_RUN=true para no enviar correos).
- En GitHub Actions (con secrets configurados).

Buenas prácticas incluidas:
- Configuración via variables de entorno (no hardcodear credenciales).
- Manejo de errores si faltan variables críticas.
- Comentarios explicativos a lo largo del código.
"""

import os
import sys
import smtplib
import random
import requests
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ================================================================
# 1. CONFIGURACIÓN
# ================================================================


def load_settings():
    """
    Lee configuración desde variables de entorno.

    Si alguna variable crítica falta, el script falla de inmediato.
    Esto es importante para no correr con parámetros incompletos.
    """
    required_vars = [
        "JIRA_BASE_URL",    # URL base de tu Jira Cloud, ej: https://empresa.atlassian.net
        "JIRA_EMAIL",       # Email del usuario con permisos para consultar
        "JIRA_API_TOKEN",   # Token API de Jira para autenticación
        "JIRA_PROJECT_KEYS",# Lista de proyectos (ej: PROJ1,PROJ2) => *|*
        "PER_ANALYST",      # Número de casos aleatorios por analista
        "RECIPIENT_EMAIL",  # Destinatario del correo de auditoría
        "SENDER_EMAIL",     # Remitente del correo
        "SMTP_SERVER",      # Servidor SMTP (ej: smtp.office365.com)
        "SMTP_PORT",        # Puerto SMTP (ej: 587)
    ]

    cfg = {}
    # valida si falta alguna vrble de entorno
    for var in required_vars:
        val = os.getenv(var)
        if not val:
            print(f"[ERROR] Falta variable de entorno: {var}", file=sys.stderr)
            sys.exit(1)
        cfg[var] = val

    # Variables opcionales (con valores por defecto)
    cfg["SMTP_USERNAME"] = os.getenv("SMTP_USERNAME", cfg["SENDER_EMAIL"])
    cfg["SMTP_PASSWORD"] = os.getenv("SMTP_PASSWORD", "")
    cfg["DRY_RUN"] = os.getenv("DRY_RUN", "true").lower() == "true"

    # Conversiones necesarias
    cfg["PER_ANALYST"] = int(cfg["PER_ANALYST"])
    cfg["SMTP_PORT"] = int(cfg["SMTP_PORT"])
    return cfg



# ================================================================
# 2. CONSULTA DE ISSUES EN JIRA
# ================================================================

def build_jql(target_date: datetime, project_keys: str) -> str:
    """
    Construye un query JQL para filtrar issues resueltos en una fecha específica.

    Ejemplo de salida:
    project in (PROJ1,PROJ2) AND resolution IS NOT EMPTY
    AND resolved >= "2025-09-03 00:00"
    AND resolved <= "2025-09-03 23:59"
    """
    start = target_date.strftime("%Y-%m-%d 00:00")
    end = target_date.strftime("%Y-%m-%d 23:59")

    projects = ",".join([p.strip() for p in project_keys.split(",")])
    jql = (
        f"project in ({projects}) "
        f"AND resolution IS NOT EMPTY "
        f"AND resolved >= \"{start}\" "
        f"AND resolved <= \"{end}\""
    )
    return jql


def fetch_all_issues(base_url, auth, jql):
    """
    Llama al API de Jira para obtener todos los issues que cumplen con la JQL.
    Usa paginación porque Jira devuelve máximo 100 resultados por petición.
    """
    issues = []
    start_at = 0
    max_results = 100
    session = requests.Session()

    while True:
        url = f"{base_url}/rest/api/3/search"
        params = {"jql": jql, "startAt": start_at, "maxResults": max_results}

        # Petición al API
        resp = session.get(url, params=params, auth=auth)
        if resp.status_code != 200:
            raise Exception(f"Error en Jira API: {resp.status_code} {resp.text}")

        data = resp.json()
        issues.extend(data.get("issues", []))

        # Si ya llegamos al total, cortamos
        if start_at + max_results >= data.get("total", 0):
            break
        start_at += max_results

    return issues


# ================================================================
# 3. PROCESAMIENTO DE ISSUES
# ================================================================

def group_by_assignee(issues):
    """
    Agrupa issues por analista (asignee).
    Devuelve un diccionario con clave = (accountId, displayName) y valor = lista de issues.
    """
    groups = {}
    for issue in issues:
        fields = issue.get("fields", {})
        assignee = fields.get("assignee")
        if not assignee:
            continue  # ignorar issues sin asignar
        key = assignee["accountId"]
        name = assignee.get("displayName", "Desconocido")
        groups.setdefault((key, name), []).append(issue)
    return groups


def pick_random_per_analyst(groups, per_analyst):
    """
    Selecciona N issues aleatorios por analista.
    Si un analista resolvió menos de N issues, devuelve todos los que tenga.
    """
    selection = {}
    for (account_id, name), items in groups.items():
        chosen = random.sample(items, k=min(per_analyst, len(items)))
        selection[(account_id, name)] = chosen
    return selection


# ================================================================
# 4. CONSTRUCCIÓN DE CORREO
# ================================================================

def build_email_html(base_url, target_date, selection, total_issues):
    """
    Construye el cuerpo del correo en HTML.
    Incluye:
    - Total de issues resueltos en el día.
    - Listado por analista con enlaces a los issues.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    html = [f"<h2>Auditoría de issues resueltos el {date_str}</h2>"]
    html.append(f"<p>Total de issues resueltos ayer: {total_issues}</p>")

    for (_, name), issues in selection.items():
        html.append(f"<h3>{name}</h3><ul>")
        for issue in issues:
            key = issue["key"]
            summary = issue["fields"].get("summary", "(sin resumen)")
            url = f"{base_url}/browse/{key}"
            html.append(f"<li><a href='{url}'>{key}</a>: {summary}</li>")
        html.append("</ul>")

    return "\n".join(html)


def send_email(cfg, subject, html_body):
    """
    Envía correo usando servidor SMTP.
    Si DRY_RUN=true, no lo envía, solo imprime el contenido en consola.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["SENDER_EMAIL"]
    msg["To"] = cfg["RECIPIENT_EMAIL"]

    # Cuerpo HTML
    part = MIMEText(html_body, "html")
    msg.attach(part)

    if cfg["DRY_RUN"]:
        print("[DRY_RUN] No se envió correo. Contenido:")
        print(msg.as_string())
        return

    # Conexión al servidor SMTP
    with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"]) as server:
        server.starttls()  # seguridad TLS
        if cfg["SMTP_PASSWORD"]:
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
        server.sendmail(cfg["SENDER_EMAIL"], [cfg["RECIPIENT_EMAIL"]], msg.as_string())
        
        
# ================================================================
# 5. PROGRAMA PRINCIPAL
# ================================================================

def main():
    # Cargamos configuración desde variables de entorno
    cfg = load_settings()

    # Calculamos "ayer" en UTC (puedes ajustar zona horaria si lo requieres)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    # Construimos la query JQL
    jql = build_jql(yesterday, cfg["JIRA_PROJECT_KEYS"])
    print(f"[INFO] Ejecutando JQL: {jql}")

    # Consultamos Jira
    issues = fetch_all_issues(cfg["JIRA_BASE_URL"], (cfg["JIRA_EMAIL"], cfg["JIRA_API_TOKEN"]), jql)
    print(f"[INFO] Issues recuperados: {len(issues)}")

    # Agrupamos por analista
    groups = group_by_assignee(issues)

    # Seleccionamos N aleatorios por analista
    selection = pick_random_per_analyst(groups, cfg["PER_ANALYST"])

    # Construimos el HTML del correo
    html = build_email_html(cfg["JIRA_BASE_URL"], yesterday, selection, len(issues))

    # Asunto del correo
    subject = f"[Auditoría] Issues resueltos el {yesterday.strftime('%Y-%m-%d')}"

    # Enviamos
    send_email(cfg, subject, html)


if __name__ == "__main__":
    main()