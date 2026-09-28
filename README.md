# Wep

Página web para mostrar información **real** sobre direcciones blockchain, con
una URL específica por dirección (`/address/0x...`). Diseñada para ser
utilizada como URL del formulario de **Project Card de Etherscan**.

## Estructura

```
wep/
├── app.py                  ← servidor Flask + conexión a Etherscan API V2
├── .env                    ← tu clave de API (NO publicar)
├── requirements.txt        ← dependencias
├── wep-service.sh          ← servidor en segundo plano (sin terminal abierta)
├── wep-boot.sh             ← arranque automático al encender el teléfono
├── FORMULARIO_ETHERSCAN.md ← borrador de respuestas del formulario
├── README.md
├── templates/
│   ├── base.html           ← diseño común
│   ├── home.html           ← página principal
│   ├── address.html        ← página de cada dirección (datos reales)
│   ├── pay.html            ← generador de solicitudes de pago no custodiales
│   └── about.html          ← acerca de Wep + aviso de no custodia
```

## Instalación en Termux (una sola vez)

```bash
cd ~/downloads/wep
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x wep-service.sh wep-boot.sh
```

## Ejecutar en segundo plano (recomendado)

El servidor **no depende de tener la terminal abierta**:

```bash
cd ~/downloads/wep
./wep-service.sh start     # arranca y puedes cerrar la terminal
./wep-service.sh status    # ¿está corriendo?
./wep-service.sh logs      # ver el registro
./wep-service.sh stop      # detener
```

## Arranque automático al encender el teléfono (opcional)

```bash
pkg install termux-boot
mkdir -p ~/.termux/boot
cp ~/downloads/wep/wep-boot.sh ~/.termux/boot/start-wep.sh
chmod +x ~/.termux/boot/start-wep.sh
```

Después abre la app **Termux: Boot** una vez y en Ajustes de Android desactiva
la optimización de batería para Termux (si no, Android mata el proceso).

## Probar

- Página principal: `http://127.0.0.1:5000`
- Ejemplo de dirección: `http://127.0.0.1:5000/address/0x0000000000000000000000000000000000000000`
- Pagos: `http://127.0.0.1:5000/pay`
- Acerca de: `http://127.0.0.1:5000/about`
- Estado del servidor: `http://127.0.0.1:5000/health`

## Herramienta de pagos (no custodial)

`/pay` genera solicitudes de pago estándar **EIP-681**
(`ethereum:<direccion>@<chainid>?value=<wei>`). El usuario abre la solicitud
en SU cartera compatible y firma la transacción allí.

Compromiso de diseño: **Wep no controla ni custodia fondos**; la ejecución y
confirmación dependen de la cartera del usuario y de su aprobación, y la
operación está sujeta a las condiciones y comisiones de la red.

## Datos en tiempo real

Wep consulta **Etherscan API V2** (Ethereum mainnet) y muestra:

| Campo | Fuente |
|---|---|
| Balance nativo | `module=account&action=balance` |
| Transacciones enviadas (nonce) | `module=proxy&action=eth_getTransactionCount` |
| Última actividad | `module=account&action=txlist` (última tx) |
| Tokens en transferencias recientes | `module=account&action=tokentx` (últimas 100) |

Reglas de honestidad del proyecto:

- Si la API falla, el campo muestra **"No disponible"** (nunca valores inventados).
- Si la dirección no tiene actividad, se dice explícitamente.
- Los resultados se cachean 5 minutos para respetar el límite del plan gratuito
  (5 llamadas/segundo).

La clave de API vive en `.env`. **No subas `.env` a un repositorio público.**

## Estado del proyecto

- ✅ Páginas por dirección con datos reales de Ethereum
- ✅ Herramienta de pagos no custodiales (EIP-681)
- ✅ Página "Acerca de" con aviso de no custodia
- ✅ Servidor en segundo plano + arranque automático opcional
- ✅ Arquitectura preparada para monetización (`WEP_PLANS` en `app.py`)
- ⏳ Wep Pro: funciones definidas como propuesta, **sin cobros activos**
- ⏳ Despliegue público (Render u otro hosting gratuito)

## Importante sobre la URL pública

Aunque Wep quede corriendo "fijo" en el teléfono, `127.0.0.1` **solo es
accesible desde el propio teléfono**. Para el formulario de Etherscan hace
falta una URL pública, que se consigue desplegando el proyecto en un hosting
(p. ej. Render, plan Free, URL tipo `https://wep-xxxx.onrender.com`).
El servicio en segundo plano es útil para desarrollar y demostrar el proyecto;
el despliegue público es el paso siguiente.

## Despliegue público (Render, plan Free, sin dominio)

1. Crea una cuenta gratuita en render.com y un **Web Service** conectado a un
   repositorio GitHub con este proyecto.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app` (ya incluido en el `Procfile`).
4. **NO subas el archivo `.env` al repositorio.** En Render, añade la clave como
   variable de entorno: `ETHERSCAN_API_KEY=*** en el dashboard
   (Environment → Environment Variables).
5. Render da una URL pública tipo `https://wep-xxxx.onrender.com` — esa es la
   URL que necesita el campo 6 del formulario de Etherscan.

⚠️ Si el repositorio es **público**, cualquier archivo que subas queda visible
para todos. Comprueba siempre que `.env` no esté incluido antes de hacer push.

## Activar pagos (etapa futura)

Cuando se decida qué vende Wep Pro y se elija proveedor (p. ej. Stripe
Payment Links):

1. Crear el producto/enlace de pago en el proveedor.
2. Poner la URL en `WEP_PLANS["pro"]["payment_url"]` en `app.py`.
3. El botón "Comprar Wep Pro" se activa automáticamente.
