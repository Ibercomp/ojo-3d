# Ojo UART binario v1

Implementación: `main/raw_protocol.h` y `main/raw_device.h` (AVR),
`ztrak-ojo/src/raw_wire.rs` y `raw_uart.rs` (Rust). Firmware Uno 3.x.
No hay JSON, URLs, texto, saltos de línea ni float IEEE754 en el cable del Uno.
El transporte antiguo del ESP a 230400 se conserva aparte por compatibilidad.

## Enlace y delimitación

250000 baudios, 8 bits, sin paridad, 1 stop, sin control de flujo.
USB integrado del Uno; D0/D1 libres. DTR/RTS se inicializan al abrir y se esperan
2,3 s para el arranque. Este coste solo existe al conectar, no en cada orden.

Cada paquete se codifica con COBS y termina en **00**. No hay bytes cero dentro
del bloque codificado. Se permiten ceros vacíos entre tramas, que se ignoran;
el cliente los usa para resincronizar antes de operaciones de control.

Todos los enteros multibyte son **little-endian**. No se transmite un struct C.
Longitud máxima decodificada: 63 bytes; codificada con delimitador: 65 bytes.
Una trama corrupta o demasiado larga se descarta y se vuelve a sincronizar en
el siguiente delimitador. El siguiente paquete completo puede recibirse sin reset.

## Cabecera y CRC, antes de COBS

| Offset | Bytes | Campo |
|---:|---:|---|
| 0 | 1 | Versión del protocolo: `01` |
| 1 | 1 | Tipo de mensaje |
| 2 | 1 | Longitud del payload `L`, 0–48 |
| 3 | 4 | Identificador de sesión, `u32`, distinto de cero |
| 7 | 2 | Secuencia, `u16` |
| 9 | 4 | Tiempo de la placa en ms, `u32` |
| 13 | L | Payload específico |
| 13+L | 2 | CRC16, byte bajo primero |

CRC: **CRC-16/CCITT-FALSE**, polinomio `1021`, inicio `FFFF`, sin reflexión,
XOR final `0000`. Cubre cabecera y payload, excluyendo el propio CRC y COBS.
Vector de comprobación: ASCII `123456789` → `29B1`.

Tamaño por cable por paquete: **L+17 bytes** (incluye COBS y delimitador; excluye
ceros de reposo opcionales). Con 8N1, cada byte consume 40 µs a 250000 baudios.

## Tipos

| Tipo hex | Dirección | Payload | Bytes por cable | Respuesta |
|---|---|---:|---:|---|
| `01 HELLO` | PC→Uno | 0 | 17 | CONFIG y telemetría |
| `02 ARM` | PC→Uno | 1 | 18 | ACK |
| `03 STATE` | PC→Uno | 0 | 17 | TELEMETRY inmediata |
| `04 CENTER` | PC→Uno | 0 | 17 | ACK |
| `05 BLINK` | PC→Uno | 0 | 17 | ACK |
| `06 LIMITS` | PC→Uno | 28 | 45 | CONFIG actualizada |
| `10 TARGET` | PC→Uno | 7 | **24** | **Sin ACK ni espera de respuesta** |
| `81 CONFIG` | Uno→PC | 48 | 65 | — |
| `82 TELEMETRY` | Uno→PC | 24 | **41** | — |
| `83 ACK` | Uno→PC | 2 | 19 | — |

`ARM`: `00` apaga; `01` enciende explícitamente. Otros valores se rechazan.
`CENTER` pone objetivo a cero; `BLINK` inicia un parpadeo coordinado.
Los límites se modifican únicamente con salidas apagadas y se guardan en EEPROM.

## TARGET: movimiento a 50 Hz

Los offsets de esta tabla corresponden al paquete **decodificado completo**.

| Offset | Bytes | Campo y unidad |
|---:|---:|---|
| 13 | 2 | Horizontal, `i16`, centésimas de grado; −5500…5500 |
| 15 | 2 | Vertical, `i16`, centésimas de grado; −3500…3500, luego envolvente mecánica |
| 17 | 2 | Párpados, `u16`, centésimas de grado; 0 abierto, 6000 cerrado |
| 19 | 1 | Flags: bit 0 reposo, bit 1 movimiento manual sin parpadeo automático |
| 20 | 2 | CRC |

Los bits 2–7 deben ser cero. Sin reposo el párpado está limitado a 3200; con
reposo permite 6000. El modo manual usa las curvas punto a punto; el modo normal
usa el seguimiento. Se conservan signos, centros y límites combinados existentes.

El PC envía como máximo una consigna cada 20 ms, sin esperar confirmación.
Si hay salida serie pendiente, omite ese envío; no añade otra consigna a una
cola del programa. El siguiente tick vuelve a usar el objetivo más reciente.
En el Uno hay **una sola casilla de consigna pendiente**, que se sustituye con
la última válida y se aplica en el tick del motor. No se reproduce una ráfaga.

## TELEMETRY: envío independiente a 50 Hz

La cabecera contiene tiempo de muestreo y secuencia de la última **trama
aceptada**, incluidos STATE y controles. No es un ACK individual de movimiento
ni certifica que el servo físico haya alcanzado la consigna.

Offsets relativos al inicio del payload (sumar 13 para offset de paquete):

| Offset payload | Bytes | Campo |
|---:|---:|---|
| 0 | 6 | Tres consignas interpoladas `i16`: horizontal, vertical, párpado, centigrados |
| 6 | 6 | Tres pulsos solicitados `u16`, microsegundos |
| 12 | 2 | Objetivo del párpado en seguimiento, `u16`, centigrados |
| 14 | 1 | Flags de estado |
| 15 | 1 | Último motivo de apagado por fallo |
| 16 | 2 | Errores UART / desbordamientos RX |
| 18 | 2 | Tramas inválidas por COBS, longitud, versión o CRC |
| 20 | 2 | Ticks de cálculo omitidos |
| 22 | 2 | Edad de la última TARGET aplicada, ms; `FFFF` sin seguimiento |

Flags: bit 0 salidas activas, 1 seguimiento, 2 parpadeo, 3 reposo, 4 consigna
pendiente, 6 salidas disponibles. Bits 5 y 7 reservados a cero.
Fallo: `00` ninguno, `01` caducidad de órdenes, `02` error UART/desbordamiento.
Contadores `u16` acumulados módulo 65536; el watchdog no depende de esos contadores.

`actual` y los pulsos son valores calculados, no encoders ni medida eléctrica.
La telemetría se emite incluso con salidas desactivadas mientras exista sesión;
se conserva solo la muestra más reciente. No hay cola de telemetría en firmware.

## CONFIG: datos que se envían al conectar o cambiar límites

Offsets relativos al payload:

| Offset | Bytes | Campo |
|---:|---:|---|
| 0 | 1 | Versión mayor del firmware: 3 |
| 1 | 1 | Versión menor: 1 en el firmware 3.1 (0 en 3.0) |
| 2 | 1 | Placa: 1 = Uno R3 / ATmega328P |
| 3 | 1 | Periodo del motor: 20 ms |
| 4 | 2 | Capacidades: bits 0 PWM hardware de los ejes, 1 límites EEPROM, 2 telemetría asíncrona, 3 caducidad de comandos |
| 6 | 2 | Velocidad máxima de mirada, centigrados/s: 8000 |
| 8 | 6 | Centros de tres servos, `u16` µs: 1560,1470,1810 |
| 14 | 3 | Sentidos, tres `i8`: +1,−1,−1 |
| 17 | 3 | Pines: 9,10,11 |
| 20 | 14 | Siete límites verticales positivos, `u16`, décimas de grado |
| 34 | 14 | Siete límites verticales negativos, `u16`, décimas de grado |

Puntos horizontales de ambas tablas: −55,−45,−30,0,30,45,55 grados.
`LIMITS` contiene solo esos 28 bytes de tablas en el mismo orden.

## ACK

Payload: byte 0 resultado, byte 1 tipo de comando confirmado. La cabecera repite
sesión y secuencia de la solicitud; el tiempo es el de la respuesta de la placa.

Resultados: `00` aceptado; `01` payload/rango inválido; `02` operación no
permitida en el estado actual; `03` orden caducada; `04` HELLO rechazado con
salidas activas; `05` secuencia antigua o repetida; `06` tipo no soportado.
TARGET inválida se ignora sin generar respuesta por comando.

## Sesión, frescura y fallo de enlace

1. Al abrir, el PC genera un identificador de sesión, envía HELLO y recibe CONFIG
   y TELEMETRY. HELLO se admite solo con salidas apagadas y nunca las enciende.
2. En comandos, el tiempo corresponde al reloj de la placa estimado en el PC.
   La app envía un STATE asíncrono cada segundo para resincronizar el reloj.
   En respuestas, el campo es el reloj real del firmware, con paso de 20 ms.
3. Se admiten órdenes con edad entre −40 y +100 ms. HELLO, STATE y OFF no
   necesitan una estimación previa de tiempo. Una orden caducada no renueva lease.
4. Secuencia común `u16`, incremental módulo 65536. Debe avanzar en comparación
   modular de media ventana: diferencia 1…32767. Sesión distinta se ignora.
5. Solo TARGET válida o el primer encendido explícito mantienen/inician el
   plazo de órdenes. A los **700 ms** sin TARGET válida se desactivan las
   salidas, aunque sigan llegando consultas STATE. La CPU tiene además WDT 500 ms.
6. OFF válida puede desactivar incluso con otra sesión o tiempo caducado. Cierra
   la sesión; cualquier ARM que quedase pendiente de esa sesión se ignora.
   Un nuevo encendido requiere HELLO y ARM nuevos. No hay reactivación automática.
7. La app pausa con telemetría >100 ms y declara enlace perdido a los 600 ms.
   Rechaza respuestas antiguas usando su reloj de muestreo, no solo recepción.

## Coste y ejemplo comprobado

A 50 Hz, TARGET usa 1200 bytes/s (4,8% del canal PC→Uno) y TELEMETRY 2050 bytes/s
(8,2% del canal Uno→PC). Son canales dúplex independientes. La trama TARGET tarda
**0,96 ms** en el cable; TELEMETRY **1,64 ms**. No se suman como RTT del movimiento.

Ejemplo: sesión `12345678`, secuencia 42, tiempo 1000 ms, horizontal −12,34°,
vertical +5,67°, párpado 32°, reposo=1. Antes de COBS:

```
01 10 07 78 56 34 12 2A 00 E8 03 00 00 2E FB 37 02 80 0C 01 80 F7
```

Trama exacta de 24 bytes por UART, con COBS y delimitador:

```
09 01 10 07 78 56 34 12 2A 03 E8 03 01 0A 2E FB 37 02 80 0C 01 80 F7 00
```

Vector compartido verificado en C y Rust; CRC `F780` (se transmite `80 F7`).
`tests/test_raw.c` verifica tamaños, CRC, corrupción de cada bit, resincronización
 y wrap de secuencia/reloj. `tests/sim_raw.c` ejecuta el ELF real a 16 MHz;
las pruebas Rust con PTY verifican fragmentación y envío sin ACK de TARGET.
`tools/raw_uart.py` ofrece codec y monitor binario; no enciende las salidas.
