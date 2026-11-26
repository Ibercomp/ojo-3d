# Movimiento por UDP

Puerto UDP 4210. Orden de 24 bytes y respuesta de telemetría de 36 bytes.
Enteros little-endian; ángulos en centésimas de grado. No HTTP ni JSON dentro
del flujo de movimiento. El cliente envía la consigna más reciente a un máximo
de 50 Hz, sin esperar confirmación ni retransmitir consignas anteriores.

La configuración inicial sigue en HTTP: `/centrar`, `/encender`, `/udp`.
`/udp` devuelve el estado con `udp_port`, `udp_session` y `diag.uptime_ms`;
solo abre una sesión con el motor encendido. Su lectura tiene que ser rápida
para estimar el reloj del dispositivo. El cliente actual usa el punto medio
de un intercambio de hasta 100 ms. UART no depende de este protocolo.

| Offset | Bytes | Orden `OJ19` |
|---:|---:|---|
| 0 | 4 | ASCII `OJ19` |
| 4 | 4 | Sesión u32 obtenida al iniciar |
| 8 | 4 | Secuencia u32 creciente, comparación modular |
| 12 | 4 | Instante de envío en ms del reloj estimado de la placa |
| 16 | 2 | Giro i16 × 0,01° |
| 18 | 2 | Cabeceo i16 × 0,01° |
| 20 | 2 | Párpado u16 × 0,01° |
| 22 | 1 | Reposo: 0 o 1 |
| 23 | 1 | Reservado, debe ser cero |

La placa valida tamaño exacto, firma, sesión, secuencia y rangos. Rechaza
edad >200 ms o más de 100 ms en el futuro. Una sesión caduca después de
700 ms sin órdenes válidas. Nunca enciende motores al recibir UDP. Apagado,
OTA, cambio manual de control y pérdida de Wi-Fi invalidan la sesión.
El motor mantiene la misma envolvente mecánica y el watchdog de 700 ms.

| Offset | Bytes | Telemetría `OS19` |
|---:|---:|---|
| 0 | 4 | ASCII `OS19` |
| 4 | 4 | Sesión |
| 8 | 4 | Secuencia aceptada |
| 12 | 4 | Uptime ms al recibir |
| 16 | 6 | Giro, cabeceo y párpado i16 × 0,01° |
| 22 | 2 | Objetivo del párpado u16 × 0,01° |
| 24 | 1 | Bits: activo, seguimiento, parpadeando, reposo, PCA |
| 25 | 3 | Reservado |
| 28 | 2 | Contador de desconexiones Wi-Fi, 16 bits bajos |
| 30 | 2 | Contador de errores I²C, 16 bits bajos |
| 32 | 2 | Máximo intervalo del motor en ms, 16 bits bajos |
| 34 | 2 | Reservado |

La posición es la consigna interpolada del firmware, **no una medida por encoder**.
La telemetría es asíncrona. El cliente descarta sesiones/secuencias incorrectas,
duplicados y respuestas con RTT >180 ms. Sin telemetría durante 180 ms pausa
la trayectoria; a los 600 ms declara fallo. Reanuda con una pose reciente y
los filtros reiniciados. Una orden manual que invalide la sesión requiere
volver a iniciar el seguimiento. La sesión identifica al controlador; no es
autenticación criptográfica ni protege una red hostil.

Medida de referencia en nuestra red: 1.500 órdenes en 30 s con la placa en
posición neutra dieron 1.496 respuestas, con RTT mediano de 5,7 ms, p95 de
14,6 ms y máximo de 87 ms.

## Límites de cabeceo

El formato binario no cambia. El rango numérico de cabeceo admite ±35°,
pero cada orden se limita a la curva `limits` guardada en NVS. La configuración
se realiza con `/limites` (HTTP o UART) y requiere salidas apagadas; devuelve el
perfil confirmado. Cualquier escritura invalida la sesión UDP previa. La app
negocia una sesión nueva al entrar en manual o seguimiento y lee la misma curva.
