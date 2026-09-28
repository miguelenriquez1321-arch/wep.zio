"""
Wep — Página pública de direcciones blockchain.

Proyecto pensado para servir como URL de la Project Card de Etherscan:
    https://TU-URL/address/0xDIRECCION

Filosofía del proyecto:
- La información básica es gratuita y útil (atrae usuarios desde Etherscan).
- Las funciones avanzadas (Wep Pro) son las candidatas a monetización.
- NO se inventan datos: si un dato no se puede obtener, la interfaz lo
  muestra claramente como "No disponible" o "Pendiente de conexión".

Datos blockchain: Etherscan API V2 (https://docs.etherscan.io/).
La clave de API se lee del archivo .env (nunca se escribe en el código).
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal

from flask import Flask, abort, render_template, request

app = Flask(__name__)

# Dirección EVM válida: 0x + 40 caracteres hexadecimales
ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")


# ------------------------------------------------------------------
# Configuración (.env)
# ------------------------------------------------------------------

def load_env(path=None):
    """Carga variables del archivo .env sin dependencias externas."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(
                    key.strip(),
                    value.strip().strip('"').strip("'"),
                )
    except FileNotFoundError:
        pass


load_env()

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "").strip()
CHAIN_ID = os.environ.get("WEP_CHAIN_ID", "1").strip() or "1"
PORT = int(os.environ.get("WEP_PORT", "5000"))

ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"

# Caché sencilla en memoria para respetar los límites de la API
# (5 llamadas/segundo en el plan gratuito) y cargar las páginas rápido.
CACHE_TTL_SECONDS = 300
_cache = {}


# ------------------------------------------------------------------
# Cliente de Etherscan API V2
# ------------------------------------------------------------------

def etherscan_call(params, timeout=10):
    """Llama a Etherscan API V2. Devuelve el campo 'result' o lanza RuntimeError."""
    if not ETHERSCAN_API_KEY:
        raise RuntimeError("API no configurada: falta ETHERSCAN_API_KEY en .env")

    query = {
        "chainid": CHAIN_ID,
        "apikey": ETHERSCAN_API_KEY,
    }
    query.update(params)
    url = ETHERSCAN_API_URL + "?" + urllib.parse.urlencode(query)

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise RuntimeError(f"No se pudo contactar con la API: {error}") from error

    status = str(payload.get("status", ""))
    result = payload.get("result")

    if status == "1":
        return result

    # Módulo "proxy": respuesta estilo JSON-RPC (sin campo "status")
    if "status" not in payload:
        if "error" in payload:
            error = payload["error"]
            raise RuntimeError(error.get("message", str(error)) if isinstance(error, dict) else str(error))
        return result

    # status "0" con resultado textual = respuesta conocida de la API
    if isinstance(result, str):
        if "No transactions found" in result:
            return []
        raise RuntimeError(result)

    raise RuntimeError("Respuesta inesperada de la API")


def wei_to_eth(wei_value):
    """Convierte wei (entero) a ETH con formato legible."""
    try:
        eth = Decimal(int(wei_value)) / Decimal(10 ** 18)
    except (ValueError, TypeError):
        return None
    return f"{eth:.6f} ETH"


def format_timestamp(unix_seconds):
    """Formatea un timestamp Unix en UTC legible."""
    try:
        moment = datetime.fromtimestamp(int(unix_seconds), tz=timezone.utc)
    except (ValueError, TypeError):
        return None
    return moment.strftime("%d/%m/%Y %H:%M UTC")


# ------------------------------------------------------------------
# Datos reales de una dirección
# ------------------------------------------------------------------

def fetch_address_fields(address):
    """
    Obtiene datos REALES de la dirección vía Etherscan API V2.
    Devuelve una lista de campos con estado honesto:
      status = "real"       -> dato obtenido correctamente
      status = "empty"      -> la API confirma que no hay datos (p. ej. 0 txs)
      status = "unavailable"-> la API falló o no está configurada
    """
    cache_key = address.lower()
    cached = _cache.get(cache_key)
    if cached and (datetime.now(timezone.utc) - cached["at"]).seconds < CACHE_TTL_SECONDS:
        return cached["fields"]

    fields = [
        {"label": "Balance nativo", "value": None, "status": "unavailable", "note": ""},
        {"label": "Transacciones enviadas", "value": None, "status": "unavailable", "note": ""},
        {"label": "Última actividad", "value": None, "status": "unavailable", "note": ""},
        {"label": "Tokens en transferencias recientes", "value": None, "status": "unavailable", "note": ""},
    ]

    # 1) Balance nativo (wei -> ETH)
    try:
        result = etherscan_call({
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
        })
        fields[0]["value"] = wei_to_eth(result)
        fields[0]["status"] = "real" if fields[0]["value"] else "unavailable"
    except RuntimeError as error:
        fields[0]["note"] = str(error)

    # 2) Número de transacciones enviadas (nonce de la dirección)
    try:
        result = etherscan_call({
            "module": "proxy",
            "action": "eth_getTransactionCount",
            "address": address,
            "tag": "latest",
        })
        sent = int(result, 16)
        fields[1]["value"] = f"{sent:,}".replace(",", ".")
        fields[1]["status"] = "real"
        fields[1]["note"] = "Conteo de transacciones enviadas (nonce)"
    except (RuntimeError, ValueError) as error:
        fields[1]["note"] = str(error)

    # 3) Última actividad (última transacción registrada)
    try:
        result = etherscan_call({
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "desc",
        })
        if isinstance(result, list) and result:
            fields[2]["value"] = format_timestamp(result[0].get("timeStamp"))
            fields[2]["status"] = "real" if fields[2]["value"] else "unavailable"
        else:
            fields[2]["value"] = "Sin transacciones registradas"
            fields[2]["status"] = "empty"
    except RuntimeError as error:
        fields[2]["note"] = str(error)

    # 4) Tokens observados en las últimas transferencias (máx. 100)
    try:
        result = etherscan_call({
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": 1,
            "offset": 100,
            "sort": "desc",
        })
        seen = []
        if isinstance(result, list):
            for transfer in result:
                symbol = (transfer.get("tokenSymbol") or "?").strip()
                if symbol and symbol not in seen:
                    seen.append(symbol)
                if len(seen) >= 8:
                    break
        if seen:
            fields[3]["value"] = ", ".join(seen)
            fields[3]["status"] = "real"
            fields[3]["note"] = "Observados en las últimas 100 transferencias"
        else:
            fields[3]["value"] = "Sin transferencias de tokens recientes"
            fields[3]["status"] = "empty"
    except RuntimeError as error:
        fields[3]["note"] = str(error)

    _cache[cache_key] = {
        "at": datetime.now(timezone.utc),
        "fields": fields,
    }
    return fields


# ------------------------------------------------------------------
# Configuración de producto y monetización
# ------------------------------------------------------------------
# Orden lógico del proyecto:
#   1º definir el valor que ofrece Wep
#   2º decidir qué funciones son gratuitas y cuáles de pago
#   3º integrar un proveedor de pagos (p. ej. Stripe Payment Links)
#
# Cuando lleguemos al paso 3º, bastará con poner la URL de pago en
# WEP_PLANS["pro"]["payment_url"] y activar el botón.

WEP_PLANS = {
    "free": {
        "name": "Wep Básico",
        "price": "Gratis",
        "features": [
            "Página pública específica para cada dirección (/address/0x...)",
            "Balance y transacciones reales de la dirección",
            "Última actividad registrada y tokens recientes",
            "Enlace directo al explorador de la red",
            "Interfaz rápida y sin registro",
        ],
    },
    "pro": {
        "name": "Wep Pro",
        "price": "Próximamente",
        "status": "Funciones en definición — sin cobros activos",
        "features": [
            "Análisis ampliado de la dirección",
            "Historial detallado de movimientos",
            "Métricas adicionales de actividad",
            "Seguimiento de actividad y alertas",
            "Herramientas avanzadas para usuarios frecuentes",
        ],
        "payment_url": None,  # aquí irá el enlace de pago cuando se defina
    },
}

NETWORK_NAME = "Ethereum"
EXPLORER_URL = "https://etherscan.io/address/{address}"

# Texto legal compartido: Wep no custodia fondos (usado en /pay y /about).
NON_CUSTODY_NOTICE = (
    "Wep no controla ni custodia los fondos del usuario: la transacción se "
    "realiza mediante la cartera seleccionada por el usuario y queda sujeta "
    "a las condiciones y comisiones de la red blockchain utilizada."
)


# ------------------------------------------------------------------
# Rutas
# ------------------------------------------------------------------

@app.route("/")
def home():
    """Página principal: qué es Wep, cómo funciona y planes."""
    return render_template(
        "home.html",
        plans=WEP_PLANS,
        api_configured=bool(ETHERSCAN_API_KEY),
        current_year=datetime.now(timezone.utc).year,
    )


@app.route("/address/<address>")
def address_page(address):
    """Página específica de una dirección blockchain (datos reales)."""
    if not ADDRESS_REGEX.match(address):
        abort(404)

    fields = fetch_address_fields(address)
    data = {
        "address": address,
        "network_name": NETWORK_NAME,
        "explorer_url": EXPLORER_URL.format(address=address),
        "fields": fields,
        "fetched_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "api_configured": bool(ETHERSCAN_API_KEY),
    }
    return render_template(
        "address.html",
        data=data,
        plans=WEP_PLANS,
        current_year=datetime.now(timezone.utc).year,
    )


@app.route("/about")
def about():
    """Acerca de Wep: qué es, visión y aviso de no custodia."""
    return render_template(
        "about.html",
        current_year=datetime.now(timezone.utc).year,
    )


@app.route("/pay")
def pay():
    """
    Generador de solicitudes de pago no custodiales (estándar EIP-681).

    Wep NO ejecuta transacciones ni toca fondos: solo construye el enlace
    de pago que el usuario abrirá y firmará en SU cartera compatible.
    """
    to = (request.args.get("to") or "").strip()
    amount = (request.args.get("amount") or "").strip()

    request_uri = None
    error = None

    if to or amount:
        if not ADDRESS_REGEX.match(to):
            error = "La dirección de destino no es válida (formato: 0x + 40 caracteres hexadecimales)."
        else:
            try:
                amount_value = Decimal(amount.replace(",", "."))
                if amount_value <= 0:
                    raise ValueError
                wei_value = int(amount_value * (10 ** 18))
                if wei_value <= 0:
                    raise ValueError
                # EIP-681: ethereum:<direccion>@<chainid>?value=<wei>
                request_uri = f"ethereum:{to}@{CHAIN_ID}?value={wei_value}"
            except (ValueError, ArithmeticError):
                error = "La cantidad no es válida. Introduce un número mayor que 0 (por ejemplo: 0.01)."

    return render_template(
        "pay.html",
        to=to,
        amount=amount,
        request_uri=request_uri,
        error=error,
        network_name=NETWORK_NAME,
        current_year=datetime.now(timezone.utc).year,
    )


@app.route("/health")
def health():
    """Endpoint de salud para comprobar el despliegue y el servicio en segundo plano."""
    return {
        "status": "ok",
        "project": "Wep",
        "api_configured": bool(ETHERSCAN_API_KEY),
    }


@app.errorhandler(404)
def not_found(_error):
    return (
        render_template(
            "base.html",
            title="Página no encontrada — Wep",
            content=(
                "La dirección proporcionada no es válida o la página no existe. "
                "Una dirección EVM válida tiene el formato 0x seguido de 40 "
                "caracteres hexadecimales."
            ),
            current_year=datetime.now(timezone.utc).year,
        ),
        404,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
