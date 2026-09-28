#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Wep — arranque automático al encender el teléfono
#
#  Instalación (una sola vez):
#    pkg install termux-boot
#    mkdir -p ~/.termux/boot
#    cp wep-boot.sh ~/.termux/boot/start-wep.sh
#    chmod +x ~/.termux/boot/start-wep.sh
#
#  Después abre la app "Termux: Boot" una vez y desactiva la
#  optimización de batería para Termux en Ajustes de Android.
# ============================================================

sleep 15   # espera a que Termux esté listo

termux-wake-lock 2>/dev/null
"$HOME/downloads/wep/wep-service.sh" start
