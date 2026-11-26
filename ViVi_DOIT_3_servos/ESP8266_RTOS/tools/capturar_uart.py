#!/usr/bin/env python3
"""Captura de diagnóstico de solo lectura. Nunca envía órdenes de movimiento.

Requiere pyserial. `actual` y `us` son consignas, no medidas físicas.
El muestreo por petición no captura todos los ticks internos del motor.
"""
import argparse
import json
import time
from pathlib import Path

import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--hz', type=float, default=10)
    args = parser.parse_args()
    if not 0 < args.seconds or not 0 < args.hz <= 20:
        parser.error('Duración positiva y frecuencia entre 0 y 20 Hz')

    device = serial.Serial(port=None, baudrate=230400, timeout=.05,
                           write_timeout=.5, exclusive=True)
    # No pedir reset ni modo de programación mediante DTR/RTS.
    device.dtr = False
    device.rts = False
    device.port = args.port
    start = time.monotonic()
    seq = 0
    received = 0
    errors = 0
    latencies = []
    with args.output.open('x') as log, device:
        device.reset_input_buffer()
        while time.monotonic() - start < args.seconds:
            seq += 1
            sent = time.monotonic()
            row = {'t': sent - start, 'wall_time': time.time(), 'seq': seq,
                   'uri': '/estado'}
            try:
                device.write(f'@OJO {seq} /estado\n'.encode('ascii'))
                deadline = sent + .35
                buffer = bytearray()
                matched = False
                while time.monotonic() < deadline:
                    buffer.extend(device.read_until(b'\n'))
                    while b'\n' in buffer:
                        raw, _, rest = buffer.partition(b'\n')
                        buffer = bytearray(rest)
                        line = raw.decode('utf-8', errors='replace').strip()
                        if not line.startswith(f'@OJO {seq} '):
                            continue
                        _, _, status, body = line.split(' ', 3)
                        state = json.loads(body)
                        if int(status) != 200:
                            raise ValueError(f'Respuesta UART {status}')
                        row.update(state=state, rtt_ms=(time.monotonic()-sent)*1000)
                        latencies.append(row['rtt_ms'])
                        received += 1
                        matched = True
                        break
                    if matched:
                        break
                if not matched:
                    raise TimeoutError('Sin respuesta correspondiente en 350 ms')
            except (serial.SerialException, ValueError, TimeoutError) as exc:
                row['error'] = str(exc)
                errors += 1
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
            time.sleep(max(0, 1 / args.hz - (time.monotonic() - sent)))
    print(json.dumps({'capture': str(args.output), 'responses': received,
                      'errors': errors,
                      'rtt_max_ms': max(latencies, default=None)}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
