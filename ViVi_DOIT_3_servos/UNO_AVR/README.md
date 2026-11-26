# Firmware del ojo para Arduino Nano / Uno (ATmega328P)

Es el controlador recomendado. El programa [ztrak-ojo](https://github.com/ibercomp/ztrak-ojo) le envía las órdenes por USB.

- Escrito en C sobre avr-libc, sin core Arduino ni biblioteca Servo.
- Protocolo binario por UART: COBS con CRC16, sin JSON ni texto en el cable. Especificación byte a byte en [PROTOCOLO_UART.md](PROTOCOLO_UART.md).
- El motor de movimiento, las trayectorias y los límites combinados son los mismos que en el firmware ESP8266: se compilan desde `../ESP8266_RTOS/main/`, así que esa carpeta tiene que estar presente.

## Conexiones

| Eje | Pin | Señal |
|---|---|---|
| Giro (horizontal) | D2 | Pulso de servo a 50 Hz, generado por software y medido con Timer1 (paso de 0,5 µs) |
| Cabeceo (vertical) | D3 | Igual |
| Párpados | D4 | Igual |

- El Nano o el Uno se alimenta por USB.
- Los servos se alimentan con una fuente externa de 5 V. No uses el pin 5V de la placa.
- Une la masa de la fuente con la de la placa.
- D0 y D1 quedan libres para el puente USB-serie.

Nosotros lo montamos sobre una placa portadora de servos para Nano, alimentando los servos por su borne. Si un servo lleva 1,5 s sin cambiar de posición, deja de recibir pulso hasta la siguiente orden.

En nuestro montaje usamos centros `[1560,1470,1810]` µs y sentidos `[1,-1,-1]`. Son valores de ese montaje: calibra el tuyo.

## Funcionamiento

- El motor trabaja a 50 Hz.
- La aplicación envía órdenes TARGET de 24 bytes sin esperar respuesta. La placa conserva solo la última.
- La placa emite TELEMETRY de 41 bytes a 50 Hz.
- Las operaciones de control sí se confirman.
- Al conectar, la aplicación lee una sola vez los centros y los límites.
- No hay pulso en los servos sin una sesión válida y una orden explícita de encendido.

Seguridad:
- La sesión, la secuencia, el reloj y el CRC evitan aplicar datos corruptos o atrasados.
- Si pasan 700 ms sin una orden TARGET válida, corta la señal y hay que volver a activarla de forma explícita. La telemetría no renueva ese plazo.
- OFF cierra la sesión, de modo que un ARM antiguo no puede volver a encender las salidas.
- Watchdog de CPU de 500 ms.

El seguimiento usa integración críticamente amortiguada, con rampa de arranque, máximo de 80°/s y la envolvente mecánica del ojo.

## Compilar y grabar

Necesitas `gcc-avr`, `avr-libc` y `avrdude` (por ejemplo, `sudo apt install gcc-avr avr-libc avrdude`). Si los tienes en otra carpeta, usa `make AVR_BIN=/ruta/bin`.

```sh
make
python3 tools/grabar.py --port /dev/ttyUSB0 --backup copia-anterior.hex
```

`grabar.py`:
- guarda antes una copia de la flash que tenía la placa;
- graba y verifica el firmware nuevo;
- no toca fuses ni bootloader.

Los Nano con bootloader antiguo necesitan `--baud 57600`.

En Linux, tu usuario debe pertenecer al grupo `dialout` para abrir el puerto serie.

## Monitor

```sh
python3 tools/raw_uart.py --port /dev/ttyUSB0 --seconds 5 --output telemetria.jsonl
```

Abre la placa, comprueba la configuración y que las salidas están apagadas, y guarda la telemetría en un archivo JSONL local. Nunca enciende los servos.

## Pruebas

- `tests/test_raw.c`: COBS y CRC con todos los tamaños, corrupción de cada bit, desbordamiento y resincronización, y vuelta de secuencia y reloj. Con ASan y UBSan.
- `tests/sim_raw.c`: ejecuta el ELF AVR real en simavr (`libsimavr`). Comprueba el PWM, 150 TARGET en 3 s, telemetría a 50 Hz, CRC erróneo, caducidad de sesión, última consigna de una ráfaga, tiempo de espera y que OFF impide reactivar con la sesión cerrada.

Las pruebas comprueban el firmware, no la posición física del servo.
