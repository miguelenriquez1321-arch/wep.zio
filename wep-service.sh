#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Wep — servicio en segundo plano para Termux
#  Uso:
#     ./wep-service.sh start     arranca el servidor (aunque cierres la terminal)
#     ./wep-service.sh stop      detiene el servidor
#     ./wep-service.sh status    comprueba si está corriendo
#     ./wep-service.sh logs      muestra el registro en vivo
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/.wep.pid"
LOGFILE="$DIR/wep.log"
PORT="${WEP_PORT:-5000}"

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Wep ya está corriendo (PID $(cat "$PIDFILE"))."
        return 0
    fi

    # Evita que Android duerma el proceso (si termux-api está disponible)
    if command -v termux-wake-lock >/dev/null 2>&1; then
        termux-wake-lock
        echo "Wake lock activado (el teléfono no dormirá el proceso)."
    fi

    cd "$DIR" || exit 1

    if [ -x "$DIR/.venv/bin/python" ]; then
        PY="$DIR/.venv/bin/python"
    else
        PY="$(command -v python3 || command -v python)"
    fi

    echo "Arrancando Wep en el puerto $PORT ..."
    if "$PY" -c "import gunicorn" >/dev/null 2>&1; then
        nohup "$PY" -m gunicorn -b "127.0.0.1:$PORT" -w 2 app:app \
            >> "$LOGFILE" 2>&1 &
    else
        nohup "$PY" app.py >> "$LOGFILE" 2>&1 &
    fi

    echo $! > "$PIDFILE"
    sleep 2

    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Wep corriendo en segundo plano (PID $(cat "$PIDFILE"))."
        echo "URL local: http://127.0.0.1:$PORT"
        echo "Puedes cerrar la terminal: el servidor seguirá activo."
        echo "Registro: $LOGFILE"
    else
        echo "Error al arrancar. Revisa el registro:"
        tail -n 20 "$LOGFILE"
        return 1
    fi
}

stop() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        kill "$(cat "$PIDFILE")"
        rm -f "$PIDFILE"
        if command -v termux-wake-unlock >/dev/null 2>&1; then
            termux-wake-unlock
        fi
        echo "Wep detenido."
    else
        echo "Wep no estaba corriendo."
        rm -f "$PIDFILE"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Wep corriendo (PID $(cat "$PIDFILE"))."
    else
        echo "Wep NO está corriendo."
    fi
}

case "$1" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    logs)   tail -f "$LOGFILE" ;;
    restart) stop; sleep 1; start ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
