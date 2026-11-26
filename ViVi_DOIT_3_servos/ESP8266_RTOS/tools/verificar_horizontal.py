#!/usr/bin/env python3
"""Barrido físico lento de giro, con vertical centrada y párpados abiertos.
La telemetría son consignas: no detecta contacto ni mide el ángulo mecánico.
"""
import argparse
import http.client
import json
import math
import pathlib
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('ip')
p.add_argument('--limite', type=float, required=True)
p.add_argument('--log', type=pathlib.Path, required=True)
p.add_argument('--mover-ojo', action='store_true')
a = p.parse_args()
if not a.mover_ojo:
    p.error('La prueba mueve los servos: requiere --mover-ojo')
if not math.isfinite(a.limite) or not 0 < a.limite <= 60:
    p.error('Límite de prueba fuera de 0–60°')
c = http.client.HTTPConnection(a.ip, timeout=2)
start = time.monotonic()
reference = None
last_uptime = None
with a.log.open('x') as log:
    def request(uri, check=True):
        global last_uptime
        c.request('GET', uri)
        r = c.getresponse()
        body = r.read()
        if r.status != 200:
            raise RuntimeError(f'HTTP {r.status}: {body!r}')
        s = json.loads(body)
        log.write(json.dumps({'t': time.monotonic()-start, 'uri':uri, 'state':s})+'\n')
        log.flush()
        if check and reference is not None:
            for name in ('centro','sentido','canal'):
                if s[name] != reference[name]:
                    raise RuntimeError(f'Cambió la calibración: {name}')
            d = s['diag']
            if last_uptime is not None and d['uptime_ms'] < last_uptime:
                raise RuntimeError('La placa se reinició')
            if any(d[k] != reference['diag'][k] for k in ('wifi_drops','i2c_errors')):
                raise RuntimeError(f'Incidencia de comunicación: {d}')
            if d['drive_gap_ms'] > max(100, reference['diag']['drive_gap_ms']):
                raise RuntimeError(f'Retraso de control: {d}')
            last_uptime = d['uptime_ms']
        return s
    reference = request('/estado')
    if reference['activo'] or reference['auto'] or reference['seguimiento']:
        raise RuntimeError('Hay otro control activo; detenerlo antes del barrido')
    if reference['giro_max'] < a.limite:
        raise RuntimeError('Firmware sin el recorrido solicitado')
    if max(abs(x) for x in reference['actual']) > 0.5:
        raise RuntimeError('Primero hay que situar el mecanismo en posición neutra')
    print('Inicio:', reference['firmware'], reference['diag'], flush=True)
    try:
        request('/centrar')
        request('/encender')
        def move(yaw, period):
            t = time.monotonic()
            s = request(f'/seguir?giro={yaw:.3f}&cabeceo=0&parpado=0&reposo=1')
            if not s['activo'] or s['auto'] or s['parpadeando'] or max(abs(v) for v in s['actual'][1:]) > .1:
                raise RuntimeError('Estado inesperado durante barrido aislado')
            time.sleep(max(0, period-(time.monotonic()-t)))
            return s
        for side in (1,-1):
            steps = math.ceil(a.limite/.5)
            for i in range(steps+1):
                yaw = min(i*.5,a.limite)
                move(side*yaw, .2 if yaw>45 else 1/30)
            for _ in range(10):
                s = move(side*a.limite,.1)
            if abs(s['actual'][0]-side*a.limite) > .1:
                raise RuntimeError('No se alcanzó la consigna solicitada')
            print('Extremo:', s['actual'], 'pulsos:', s['us'], 'diagnóstico:', s['diag'], flush=True)
            for i in range(steps,-1,-1):
                move(side*min(i*.5,a.limite),.04)
            for _ in range(10):move(0,.1)
        print('Barrido completado. La ausencia de roce requiere observación física.',flush=True)
    finally:
        # A connection failure never triggers another movement or an auto-resume.
        c.close()
        stop = http.client.HTTPConnection(a.ip,timeout=2)
        try:
            stop.request('GET','/apagar');r=stop.getresponse();body=r.read()
            if r.status != 200 or json.loads(body)['activo']:
                raise RuntimeError('No se confirmó el apagado')
            print('Servos apagados.',flush=True)
        finally:stop.close()
