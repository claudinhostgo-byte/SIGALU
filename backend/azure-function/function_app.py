"""
SIGALU – Azure Function: recibe el formulario de contacto y crea un
Caso (incident) en Dynamics 365 CRM usando OAuth2 client-credentials.
"""

import azure.functions as func
import json
import os
import urllib.request
import urllib.parse
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ── Credenciales (se configuran en Azure → Application Settings) ─────────────
TENANT_ID     = os.environ["D365_TENANT_ID"]
CLIENT_ID     = os.environ["D365_CLIENT_ID"]
CLIENT_SECRET = os.environ["D365_CLIENT_SECRET"]
DYNAMICS_URL  = os.environ["D365_URL"]          # https://w-it.crm2.dynamics.com

# Orígenes permitidos (ajusta si usas dominio propio)
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://claudinhostgo-byte.github.io,http://localhost:3000,http://127.0.0.1:3000"
)

def get_access_token() -> str:
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    body = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         f"{DYNAMICS_URL}/.default",
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def d365_request(token: str, method: str, path: str, payload=None):
    """Helper para llamadas a Dynamics Web API."""
    url = f"{DYNAMICS_URL}/api/data/v9.2/{path}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization",    f"Bearer {token}")
    req.add_header("Content-Type",     "application/json; charset=utf-8")
    req.add_header("Accept",           "application/json")
    req.add_header("OData-MaxVersion", "4.0")
    req.add_header("OData-Version",    "4.0")
    req.add_header("Prefer",           "return=representation")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"Dynamics {e.code} [{method} {path}]: {body}")


def get_or_create_contact(token: str, nombre: str, email: str) -> str:
    """Busca un contacto por email; si no existe lo crea. Devuelve contactid."""
    # Buscar por email
    path = f"contacts?$filter=emailaddress1 eq '{email}'&$select=contactid&$top=1"
    result = d365_request(token, "GET", path)
    values = result.get("value", [])
    if values:
        return values[0]["contactid"]
    # Crear contacto nuevo
    partes = nombre.strip().split(" ", 1)
    firstname = partes[0]
    lastname  = partes[1] if len(partes) > 1 else "."
    contact = d365_request(token, "POST", "contacts", {
        "firstname":      firstname,
        "lastname":       lastname,
        "emailaddress1":  email,
    })
    return contact.get("contactid", "")


def create_incident(nombre: str, email: str, perfil: str, mensaje: str) -> str:
    token = get_access_token()

    # 1. Obtener o crear el contacto
    contact_id = get_or_create_contact(token, nombre, email)

    # 2. Crear el caso vinculado al contacto
    descripcion = (
        f"Nombre: {nombre}\n"
        f"Email:  {email}\n"
        f"Perfil: {perfil}\n"
        f"\n{mensaje}"
    )
    payload = {
        "title":       f"Consulta SIGALU – {nombre} ({perfil})",
        "description": descripcion,
    }
    if contact_id:
        payload["customerid_contact@odata.bind"] = f"/contacts({contact_id})"

    incident = d365_request(token, "POST", "incidents", payload)
    return incident.get("incidentid", "ok")


def cors_headers(req: func.HttpRequest) -> dict:
    origin = req.headers.get("Origin", "")
    allowed = [o.strip() for o in ALLOWED_ORIGINS.split(",")]
    allow   = origin if origin in allowed else allowed[0]
    return {
        "Access-Control-Allow-Origin":  allow,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


@app.route(route="contacto", methods=["GET", "POST", "OPTIONS"])
def contacto(req: func.HttpRequest) -> func.HttpResponse:
    headers = cors_headers(req)

    # Pre-flight CORS
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=headers)

    try:
        body    = req.get_json()
        nombre  = (body.get("nombre",  "") or "").strip()
        email   = (body.get("email",   "") or "").strip()
        perfil  = (body.get("perfil",  "") or "").strip()
        mensaje = (body.get("mensaje", "") or "").strip()

        if not (nombre and email and mensaje):
            return func.HttpResponse(
                json.dumps({"ok": False, "msg": "Campos requeridos vacíos"}),
                status_code=400, headers={**headers, "Content-Type": "application/json"}
            )

        case_id = create_incident(nombre, email, perfil, mensaje)
        logging.info(f"Caso creado: {case_id}")

        return func.HttpResponse(
            json.dumps({"ok": True, "case": case_id, "msg": "Caso creado en CRM"}),
            status_code=200, headers={**headers, "Content-Type": "application/json"}
        )

    except Exception as e:
        import traceback
        detail = traceback.format_exc()
        logging.error(f"Error CRM: {detail}")
        return func.HttpResponse(
            json.dumps({"ok": False, "msg": str(e), "detail": detail}),
            status_code=500, headers={**headers, "Content-Type": "application/json"}
        )
