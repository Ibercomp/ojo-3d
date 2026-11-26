#!/usr/bin/env python3
"""Sube una imagen ESP8266 RTOS SDK al ojo. Lee el token local sin mostrarlo."""
import argparse
import pathlib
import re
import urllib.error
import urllib.request

base = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('ip', help='IP o nombre DNS de la placa')
p.add_argument('binario', nargs='?', default=str(base / 'build' / 'vivi_ojo.bin'))
a = p.parse_args()
header = (base / 'main' / 'wifi_privada.h').read_text()
m = re.search(r'^#define\s+OTA_TOKEN\s+"([^"]+)"', header, re.M)
if not m:
    raise SystemExit('No se encuentra OTA_TOKEN en main/wifi_privada.h')
image = pathlib.Path(a.binario).read_bytes()
req = urllib.request.Request('http://' + a.ip + '/ota', data=image,
    headers={'X-Ojo-OTA': m.group(1), 'Content-Type': 'application/octet-stream'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=90) as response:
        print(response.read().decode('utf-8', 'replace'))
except (urllib.error.URLError, TimeoutError) as e:
    raise SystemExit('No se completó la actualización: ' + str(e))
