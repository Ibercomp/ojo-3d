#!/bin/sh
# Abre SolidCraft con el canal de control en 7878 (lo usa herramientas/vivo.py)
# Ajusta la ruta de SolidCraft si lo tienes instalado en otro sitio.
cd "$(dirname "$0")"
exec "$HOME/.local/bin/solidcraft" --control 7878 "${1:-cad/sc/CONJUNTO_ojo.sc}"
