"""
SIGALU – Flask backend para Azure App Service
Recibe el formulario de contacto y crea un Caso en Dynamics 365.
"""
import os, json, urllib.request, urllib.parse, logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

def get_config():
    """Lee credenciales en tiempo de petición, no al iniciar."""
    return {
        "tenant":  os.environ.get("D365_TENANT_ID", ""),
        "client":  os.environ.get("D365_CLIENT_ID", ""),
        "secret":  os.environ.get("D365_CLIENT_SECRET", ""),
        "url":     os.environ.get("D365_URL", "").rstrip("/"),
        "origins": os.environ.get("ALLOWED_ORIGINS",
                   "https://claudinhostgo-byte.github.io"),
    }

def get_token(cfg):
    url  = f"https://login.microsoftonline.com/{cfg['tenant']}/oauth2/v2.0/token"
    body = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     cfg["client"],
        "client_secret": cfg["secret"],
        "scope":         f"{cfg['url']}/.default",
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

def d365(cfg, token, method, path, payload=None):
    safe_path = urllib.parse.quote(path, safe="=&$?/@(),'")
    url  = f"{cfg['url']}/api/data/v9.2/{safe_path}"
    data = json.dumps(payload).encode() if payload else None
    req  = urllib.request.Request(url, data=data, method=method)
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
        raise Exception(f"Dynamics {e.code}: {body}")

def get_or_create_contact(cfg, token, nombre, email):
    email_enc = urllib.parse.quote(email, safe="@.")
    result = d365(cfg, token, "GET",
        f"contacts?$filter=emailaddress1 eq '{email_enc}'&$select=contactid&$top=1")
    vals = result.get("value", [])
    if vals:
        return vals[0]["contactid"]
    parts = nombre.strip().split(" ", 1)
    contact = d365(cfg, token, "POST", "contacts", {
        "firstname":     parts[0],
        "lastname":      parts[1] if len(parts) > 1 else ".",
        "emailaddress1": email,
    })
    return contact.get("contactid", "")

@app.after_request
def add_cors(resp):
    cfg    = get_config()
    origin = request.headers.get("Origin", "")
    allowed = [o.strip() for o in cfg["origins"].split(",")]
    resp.headers["Access-Control-Allow-Origin"]  = origin if origin in allowed else allowed[0]
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "SIGALU API"}), 200

@app.route("/api/contacto", methods=["OPTIONS"])
def preflight():
    return "", 204

@app.route("/api/contacto", methods=["POST"])
def contacto():
    try:
        cfg  = get_config()
        body = request.get_json(force=True)

        nombre  = (body.get("nombre",  "") or "").strip()
        email   = (body.get("email",   "") or "").strip()
        perfil  = (body.get("perfil",  "") or "").strip()
        mensaje = (body.get("mensaje", "") or "").strip()

        if not (nombre and email and mensaje):
            return jsonify({"ok": False, "msg": "Campos requeridos vacíos"}), 400

        if not cfg["tenant"]:
            return jsonify({"ok": False, "msg": "Servidor no configurado"}), 500

        token      = get_token(cfg)
        contact_id = get_or_create_contact(cfg, token, nombre, email)

        desc = f"Nombre: {nombre}\nEmail: {email}\nPerfil: {perfil}\n\n{mensaje}"
        payload = {
            "title":       f"Consulta SIGALU – {nombre} ({perfil})",
            "description": desc,
        }
        if contact_id:
            payload["customerid_contact@odata.bind"] = f"/contacts({contact_id})"

        incident     = d365(cfg, token, "POST", "incidents", payload)
        case_id      = incident.get("incidentid", "")
        ticket_number = incident.get("ticketnumber", case_id)
        logging.info(f"Caso creado: {ticket_number} ({case_id})")
        return jsonify({"ok": True, "case": ticket_number, "incidentid": case_id})

    except Exception as e:
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"ok": False, "msg": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
