#!/usr/bin/env python3
"""Ensayo aislado: posición fija, giro ±3° a 1°/s y apagado final.

Activa motores solo con --activar. No utiliza visión, seguimiento ni rutinas.
Los estados registrados son consignas, no medidas físicas de servos o PWM.
"""
import argparse
import json
import math
import time
import urllib.request
from pathlib import Path

import serial


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--emergency-url', required=True, help='URL completa de /apagar')
    p.add_argument('--activar', action='store_true')
    p.add_argument('--pca', action='store_true', help='Leer y contrastar PCA cada 500 ms')
    a = p.parse_args()
    if not a.activar:
        p.error('El ensayo físico requiere --activar')
    s = serial.Serial(port=None, baudrate=230400, timeout=.05,
                      write_timeout=.4, exclusive=True)
    s.dtr = False
    s.rts = False
    s.port = a.port
    seq = 0
    start = time.monotonic()
    with a.output.open('x') as log, s:
        def record(row):
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()

        def request(uri, phase):
            nonlocal seq
            seq += 1
            sent = time.monotonic()
            row = {'t': sent-start, 'wall_time': time.time(), 'seq': seq,
                   'uri': uri, 'phase': phase}
            try:
                s.write(f'@OJO {seq} {uri}\n'.encode('ascii'))
                buf = bytearray()
                while time.monotonic()-sent < .35:
                    buf.extend(s.read_until(b'\n'))
                    while b'\n' in buf:
                        raw, _, rest = buf.partition(b'\n')
                        buf = bytearray(rest)
                        line = raw.decode(errors='replace').strip()
                        if not line.startswith(f'@OJO {seq} '):
                            continue
                        _, _, status, body = line.split(' ', 3)
                        state = json.loads(body)
                        row.update(status=int(status), state=state,
                                   rtt_ms=(time.monotonic()-sent)*1000)
                        record(row)
                        if int(status) != 200:
                            raise RuntimeError(f'UART {status}')
                        return state
                raise TimeoutError('Respuesta UART ausente en 350 ms')
            except Exception as exc:
                record(row | {'error': str(exc)})
                raise

        def move(yaw, phase):
            return request(f'/mover?giro={yaw:.3f}&cabeceo={pose[1]:.3f}'
                           f'&parpado={pose[2]:.3f}', phase)

        def check_pca(phase):
            state = request('/pca', phase + '_pca')
            if state['mode1'] & 0x7f != 0x20 or state['mode2'] != 4 or state['prescale'] != 121:
                raise RuntimeError('Configuración PCA inesperada; captura conservada')
            for channel, raw in enumerate(state['led']):
                on = raw[0] | ((raw[1] & 15) << 8)
                off = raw[2] | ((raw[3] & 15) << 8)
                ticks = 4096 if raw[3] & 16 else (off-on) & 4095
                if raw[1] & 16 or on != 0 or ticks != state['cached_ticks'][channel]:
                    raise RuntimeError('Registro PWM y caché no coinciden; captura conservada')
            return state

        reference = request('/estado', 'comprobar')
        if any(reference.get(k) for k in ['activo', 'auto', 'seguimiento']):
            raise RuntimeError('Hay otro control activo; ensayo no iniciado')
        pose = reference['actual']
        if len(pose) != 3 or not all(math.isfinite(v) for v in pose):
            raise RuntimeError('Pose inicial no válida')
        # Recorrido pequeño alrededor de la última consigna; no salto al centro.
        limits = reference['limits']['up' if pose[1] >= 0 else 'down']
        knots = [-55, -45, -30, 0, 30, 45, 55]
        for yaw in [pose[0]-3, pose[0]+3]:
            if not -55 <= yaw <= 55:
                raise RuntimeError('Margen horizontal insuficiente')
            i = next(i for i in range(6) if knots[i] <= yaw <= knots[i+1])
            bound = (limits[i] + (limits[i+1]-limits[i]) *
                     (yaw-knots[i])/(knots[i+1]-knots[i]))*.1
            if abs(pose[1]) > bound-.2:
                raise RuntimeError('Margen combinado insuficiente')
        diag = reference['diag']
        if a.pca:
            check_pca('comprobar')
        print('Pose inicial:', pose, '— fijo 8 s, giro ±3° a 1°/s; sin párpados.', flush=True)
        try:
            move(pose[0], 'preparar')
            request('/encender', 'encender')
            phases = [('fijo', 8, 0, 0), ('derecha', 3, 0, 3),
                      ('fijo_derecha', 2, 3, 3), ('izquierda', 6, 3, -3),
                      ('fijo_izquierda', 2, -3, -3), ('volver', 3, -3, 0),
                      ('fijo_final', 4, 0, 0)]
            for phase, duration, begin, end in phases:
                print('Fase:', phase, flush=True)
                for tick in range(round(duration*10)+1):
                    iteration_start = time.monotonic()
                    offset = begin+(end-begin)*min(1, tick*.1/duration)
                    state = move(pose[0]+offset, phase) if begin != end else request('/estado', phase)
                    if not state['activo'] or any(state.get(k) for k in ['auto', 'seguimiento', 'parpadeando']):
                        raise RuntimeError('Modo de control inesperado')
                    if any(state[k] != reference[k] for k in ['centro', 'sentido', 'canal']):
                        raise RuntimeError('Calibración modificada')
                    d = state['diag']
                    if d['uptime_ms'] < diag['uptime_ms'] or d['i2c_errors'] != diag['i2c_errors']:
                        raise RuntimeError('Reinicio o error I2C')
                    if d['drive_gap_ms'] > max(60, diag['drive_gap_ms']):
                        raise RuntimeError('Retraso del ciclo motor')
                    if abs(state['actual'][0]-pose[0]) > 3.1 or any(abs(state['actual'][i]-pose[i]) > .05 for i in [1, 2]):
                        raise RuntimeError('Movimiento fuera del ensayo aislado')
                    if a.pca and tick % 5 == 0:
                        check_pca(phase)
                    # Sin ráfagas para recuperar un retraso del host.
                    time.sleep(max(0, .1-(time.monotonic()-iteration_start)))
            print('Secuencia completada; comprueba a la vista que el movimiento ha sido correcto.', flush=True)
        finally:
            try:
                state = request('/apagar', 'apagar')
                if state['activo']:
                    raise RuntimeError('Apagado UART no confirmado')
                print('Servos apagados por UART.', flush=True)
            except Exception:
                with urllib.request.urlopen(a.emergency_url, timeout=2) as r:
                    state = json.load(r)
                if state['activo']:
                    raise RuntimeError('Apagado de emergencia no confirmado')
                print('Servos apagados por HTTP de emergencia.', flush=True)


if __name__ == '__main__':
    main()
