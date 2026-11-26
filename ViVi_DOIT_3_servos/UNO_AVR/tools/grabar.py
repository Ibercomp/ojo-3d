#!/usr/bin/env python3
"""Grabar Uno R3 o Nano (ATmega328P) por bootloader, conservando copia de su flash anterior.

No modifica fuses ni bootloader. El firmware nuevo arranca con salidas apagadas.
"""
import argparse
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--port', required=True)
p.add_argument('--backup', type=Path, required=True)
p.add_argument('--baud', type=int, default=115200,
               help='115200 Uno/Nano nuevo; 57600 Nano con bootloader antiguo')
p.add_argument('--avr-bin', type=Path, default=Path('/usr/bin'),
               help='carpeta con avr-gcc y avrdude (por defecto, las del sistema)')
a = p.parse_args()
project = Path(__file__).resolve().parent.parent
if not os.access(a.port, os.R_OK | os.W_OK):
    raise SystemExit('Sin permiso de lectura/escritura sobre '+a.port)
if a.backup.exists():
    raise SystemExit('La copia ya existe: no se sobrescribe')
subprocess.run(['make', 'AVR_BIN='+str(a.avr_bin)], cwd=project, check=True)
cmd = [str(a.avr_bin/'avrdude'), '-p', 'atmega328p', '-c', 'arduino', '-P', a.port, '-b', str(a.baud)]
a.backup.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(cmd+['-U', 'flash:r:'+str(a.backup.resolve())+':i'], check=True, umask=0o077)
# avrdude verifies the programmed flash by default; do not pass -V.
subprocess.run(cmd+['-D', '-U', 'flash:w:'+str(project/'build/ojo_uno.hex')+':i'], check=True, umask=0o077)
print('Flash grabada y verificada. Salidas desactivadas al arrancar.')
