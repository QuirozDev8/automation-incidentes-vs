"""
jira_daily_audit_mailer.py
--------------------------------
Script para Jira Cloud que:
1. Consulta issues resueltos el día anterior (JQL relativo).
2. Agrupa por analista (assignee), incluyendo "Sin asignar".
3. Selecciona N aleatorios por analista.
4. Envía un correo con los resultados (o guarda vista previa en DRY_RUN).

Buenas prácticas:
- Carga .env
- Validación de variables
- Pide solo los campos necesarios
- Timeout en requests
- Soporta múltiples destinatarios
"""

import os
import sys
import smtplib
import random
import requests
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo  # Python 3.9+
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv, find_dotenv

# para probar en que liena se imprime una funcion con 
#  => traceback.print_stack(limit=2)  # <-- te mostrará la línea que lo llamó
import traceback

# ================================================================
# 1. CONFIGURACIÓN
# ================================================================

def load_settings():
    """
    Carga variables desde .env si existe y valida requeridas.
    """
    load_dotenv(find_dotenv(usecwd=True), override=False)
    required_vars = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_PROJECT_KEYS",
        "PER_ANALYST",
        "RECIPIENT_EMAIL",
        "SENDER_EMAIL",
        "SMTP_SERVER",
        "SMTP_PORT",
    ]

   

    cfg = {} # almacena todas las configuraciones necesarias
    for var in required_vars:
        val = os.getenv(var)
        if not val:
            print(f"[ERROR] Falta variable de entorno: {var}", file=sys.stderr)
            sys.exit(1)
        cfg[var] = val

    # Opcionales / defaults
    cfg["SMTP_USERNAME"] = os.getenv("SMTP_USERNAME", cfg["SENDER_EMAIL"])
    cfg["SMTP_PASSWORD"] = os.getenv("SMTP_PASSWORD", "")
    cfg["DRY_RUN"] = os.getenv("DRY_RUN", "true").lower() == "true"

    # Casting y validaciones
    try:
        cfg["PER_ANALYST"] = int(cfg["PER_ANALYST"])
    except ValueError:
        print("[ERROR] PER_ANALYST debe ser un entero.", file=sys.stderr)
        sys.exit(1)

    try:
        cfg["SMTP_PORT"] = int(cfg["SMTP_PORT"])
    except ValueError:
        print("[ERROR] SMTP_PORT debe ser un entero.", file=sys.stderr)
        sys.exit(1)

    return cfg  # retornar todas las vrbles de entorno almacenadas


# ================================================================
# 2. CONSULTA DE ISSUES EN JIRA
# ================================================================

# ---- esta funcion que consulta en el portal de Jira la informacion requeridad 
def build_jql_relative(project_keys: str) -> str:
    """
    Usa el día calendario 'ayer' según la zona del usuario en Jira,
    evitando manejar timestamps y husos horarios en el script.
    """
    projects = ",".join([p.strip() for p in project_keys.split(",") if p.strip()])
    # query que extrae los datos de jira  
    # (-1), extrar los datos de ayer
    # (0), los de hoy 

    # consulta que me trae todas las ussues en estado final en el workflow
    return (
        f"project in ({projects}) "
        f'AND status CHANGED TO "Resuelto" DURING (startOfDay(-1), endOfDay(-1))'
    )


    
def fetch_all_issues(base_url: str, auth: tuple, jql: str):
    """
        Llama al API de Jira para obtener todos los issues que cumplen con la JQL.
        Usa paginación porque Jira devuelve máximo 100 resultados por petición.
        Pide solo los campos necesarios y añade timeout.
    """
    issues = []
    start_at = 0
    max_results = 100
    session = requests.Session()

    base_url = base_url.strip().rstrip('/')
    fields = ["key", "summary", "assignee", "reporter", "resolutiondate"]

    while True:
        url = f"{base_url}/rest/api/3/search/jql"
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields,
        }

        resp = session.get(url, params=params, auth=auth, headers={"Accept": "application/json"}, timeout=30)

        if resp.status_code != 200:
            raise Exception(f"Error en Jira API: {resp.status_code} {resp.text}")

        try:
            data = resp.json()
        except ValueError:
            raise Exception(f"Respuesta no es JSON válido: {resp.text}")

        issues.extend(data.get("issues", []))

        total = data.get("total", 0)
        if start_at + max_results >= total:
            break
        start_at += max_results

    return issues



# ================================================================
# 3. PROCESAMIENTO DE ISSUES
# ================================================================
# resumen estadisticas agsinadas
def summarize_assignee_stats(issues):
    with_assignee = sum(1 for i in issues if i.get("fields", {}).get("assignee"))
    without_assignee = len(issues) - with_assignee
    print(f"[INFO] Con assignee: {with_assignee} | Sin assignee: {without_assignee}")
   

def group_by_assignee(issues):
    """
    Agrupa issues por analista (assignee).
    Incluye un grupo especial para 'Sin asignar'.
    Clave: (accountId, displayName) o ("UNASSIGNED", "(Sin asignar)")
    """
    groups = {}
    for issue in issues:
        fields = issue.get("fields", {})
        assignee = fields.get("assignee")
        if not assignee:
            key = ("UNASSIGNED", "(Sin asignar)")
            name = "(Sin asignar)"
        else:
            key = (assignee["accountId"], assignee.get("displayName", "Desconocido"))
            name = assignee.get("displayName", "Desconocido")
        groups.setdefault((key[0], name), []).append(issue)
    return groups


def pick_random_per_analyst(groups, per_analyst: int):
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
from html import escape
from datetime import date

def build_email_html(base_url: str, target_date: date, selection, total_issues: int) -> str:
    """
    funcion para renderizar el html en el correo
    """
    date_str = target_date.isoformat()
    preheader = f"Total de incidentes resueltos: {total_issues} — {date_str}"

    # Paleta y fuentes 
    bg = "#faf6fa"
    card_bg = "#ffffff"
    text = "#0f172a"
    text_muted = "#334155"
    border = "#eaeef2"
    border_soft = "#e5e7eb"
    link = "#0b57d0"

    # view html que se mostrara en el correo
    html_content = f"""\
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8" />
            <meta name="x-apple-disable-message-reformatting" />
            <meta name="color-scheme" content="light only" />
            <title>Auditoría de incidentes</title>
        </head>
        <body style="margin:0; padding:0; background-color:{bg};">
            
            
            <!-- preheader (oculto) -->
            <div style="display:none; overflow:hidden; line-height:1px; opacity:0; max-height:0; max-width:0; mso-hide:all;">
            {escape(preheader)}
            </div>

            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:{bg};">
            <tr>
                <td align="center" style="padding:24px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="width:600px; max-width:600px; background:{card_bg}; border:1px solid {border}; border-radius:8px;">
                    <tr>
                    <td style="padding:24px; font-family:-apple-system,Segoe UI,Roboto,Arial,Helvetica,sans-serif; color:{text}; font-size:14px; line-height:1.6;">
                        <h2 style="margin:0 0 8px 0; font-size:20px; line-height:1.3; color:{text};">
                        Auditoría de incidentes resueltos el {escape(date_str)}
                        </h2>
                        <p style="margin:0 0 16px 0; color:{text_muted};">
                        Total de incidentes resueltos: <strong style="color:{text};">{total_issues}</strong>
                        </p>
     """

    # Mensaje si no hay selección
    if not selection:
         html_content += f"""\
            <p style="margin:0; color:{text_muted};">
            <em>No se encontraron incidentes con analista asignado. Es posible que los incidentes estén sin asignar o que el filtro no aplique.</em>
            </p>
        """

    # Bloques por responsable
    # Ordenar por displayName de analista
    for (account_id, name), items in sorted(selection.items(), key=lambda kv: kv[0][1].lower()):
        safe_name = escape(name or "(Sin asignar)")
        count = len(items)
        html_content += f"""\
                <div style="margin:16px 0; padding:12px; border:1px solid {border_soft}; border-radius:8px;">
                  <h3 style="margin:0 0 8px 0; font-size:16px; color:{text};">
                    {safe_name} <span style="color:{text_muted};">({count})</span>
                  </h3>
                  <ol style="margin:0; padding-left:20px;">
          """
        for issue in items:
            key = escape(issue.get("key", "(sin clave)"))
            fields = issue.get("fields", {}) or {}
            summary = escape(fields.get("summary", "(sin resumen)"))
            assignee = fields.get("assignee")
            assignee_name = escape((assignee or {}).get("displayName") or "(Sin asignar)")
            url = f"{base_url}/browse/{key}"

            html_content += f"""\
                    <li style="margin:0 0 6px 0;">
                      <a href="{url}" style="color:{link}; text-decoration:none;">{key}</a>
                      &nbsp;—&nbsp;{summary}
                      &nbsp;—&nbsp;<strong style="color:{text};">{assignee_name}</strong>
                    </li>
             """
        html_content += """\
                  </ol>
                </div>
         """

    # Cierre de tarjetas y wrapper
    html_content += f"""\
                <p style="margin:16px 0 0 0; color:{text_muted}; font-size:12px;">
                  Reporte generado automáticamente. No responder a este correo.
                </p>
              </td>
            </tr>
          </table>
          <div style="height:24px; line-height:24px;">&nbsp;</div>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    
    return html_content # html listo para pintar en el correo

# envio de correo
def send_email(cfg, subject: str, html_body: str):
    """
    Envía correo usando servidor SMTP.
    Soporta múltiples destinatarios en RECIPIENT_EMAIL (separados por coma).
    En DRY_RUN, guarda vista previa HTML en archivo local.
    """
    # Permite múltiples destinatarios
    recipients = [e.strip() for e in cfg["RECIPIENT_EMAIL"].split(",") if e.strip()]
    if not recipients:
        print("[ERROR] RECIPIENT_EMAIL no tiene destinatarios válidos.", file=sys.stderr)
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["SENDER_EMAIL"]
    msg["To"] = ", ".join(recipients)

    part = MIMEText(html_body, "html")
    msg.attach(part) 

    if cfg["DRY_RUN"]:

        print("\n[DRY_RUN] No se envió correo. Contenido MIME (recortado).")
        # Guarda una copia del HTML para revisión rápida
        fname = f"auditoria_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"[DRY_RUN] Vista previa guardada en: {fname}")
        return

    with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"]) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        if cfg["SMTP_PASSWORD"]:
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
        server.sendmail(cfg["SENDER_EMAIL"], recipients, msg.as_string())


# ================================================================
# Funcion para imprimir en consola el resultado
# ================================================================
def print_console_summary(base_url: str, selection, total_issues: int):
    """
    Imprime en consola un resumen legible:
    - Total de issues
    - Bloques por responsable (incluye '(Sin asignar)')
    - Por issue: KEY — resumen — responsable — URL
    """
    def _short(text: str, maxlen: int = 100) -> str:
        if text is None:
            return "(sin resumen)"
        text = str(text)
        return text if len(text) <= maxlen else text[: maxlen - 3] + "..."

    print("\n=== Resumen de auditoría (consola) ===")
    print(f"Total de issues resueltos: {total_issues}")

    if not selection:
        print("No se encontraron issues con analista asignado para el rango.")
        return

    # Ordenar por nombre del analista
    for (account_id, name), issues in sorted(selection.items(), key=lambda kv: kv[0][1].lower()):
        print(f"\n{name} ({len(issues)}):")
        for issue in issues:
            key = issue.get("key", "(sin clave)")
            fields = issue.get("fields", {}) or {}
            summary = _short(fields.get("summary"))
            assignee = fields.get("assignee")
            assignee_name = (assignee or {}).get("displayName") or "(Sin asignar)"
            url = f"{base_url}/browse/{key}"
            print(f"  - {key} — {summary} — Resp.: {assignee_name} — {url}")

# ================================================================
# 5. PROGRAMA PRINCIPAL
# ================================================================

def get_yesterday_bogota() -> date:
    """
    Devuelve la fecha de 'ayer' para la zona America/Bogota (solo date).
    Se usa para el asunto y el encabezado del HTML, alineado con la JQL relativa.
    """
    now_bog = datetime.now(ZoneInfo("America/Bogota"))
    return (now_bog - timedelta(days=1)).date()



# ------------------ FUNCION PRINCIPAL ----------------------
def main():
    # Cargamos configuración
    cfg = load_settings()

    # JQL para 'ayer' relativo (en Jira)
    jql = build_jql_relative(cfg["JIRA_PROJECT_KEYS"])
   # ver en consola la query que se esta ejecutando
    print(f"\n[INFO] Ejecutando JQL: {jql}")

    # Consultamos Jira
    issues = fetch_all_issues(
        cfg["JIRA_BASE_URL"],
        (cfg["JIRA_EMAIL"], cfg["JIRA_API_TOKEN"]),
        jql
    )
    
    print(f"[INFO] Issues recuperados: {len(issues)}")
    summarize_assignee_stats(issues)

    # Agrupamos por analista (incluye "Sin asignar") y seleccionamos N aleatorios
    groups = group_by_assignee(issues)
    selection = pick_random_per_analyst(groups, cfg["PER_ANALYST"])
    
    if cfg["DRY_RUN"]: 
        # 🔽 Imprimir resumen en consola para pruebas
        print_console_summary(cfg["JIRA_BASE_URL"], selection, len(issues))        
        
    
    # Fecha "ayer" (Bogotá) para asunto y HTML
    yesterday_bog = get_yesterday_bogota()

    # Construimos HTML y asunto (con nombres y links por issue)
    html = build_email_html(cfg["JIRA_BASE_URL"], yesterday_bog, selection, len(issues))
    subject = f"[Auditoría] Issues resueltos el {yesterday_bog.isoformat()}"

    # Envío (o DRY_RUN)
    send_email(cfg, subject, html)


if __name__ == "__main__":
    main()
