# Control del ojo

Dos firmwares para mover los tres servos del ojo (giro, cabeceo y párpados):

| Carpeta | Placa | Enlace con el ordenador | Uso |
|---|---|---|---|
| [`UNO_AVR/`](UNO_AVR) | Arduino Nano o Uno (ATmega328P) | USB-serie | **Recomendado.** Es el que usamos con [ztrak-ojo](https://github.com/ibercomp/ztrak-ojo) |
| [`ESP8266_RTOS/`](ESP8266_RTOS) | DOIT ViVi (ESP8266 + PCA9685) | Wi-Fi o UART | Alternativa inalámbrica. Contiene también el motor de movimiento que compila `UNO_AVR` |

`ESQUEMAS/` tiene los esquemas de la placa DOIT ViVi: bloques, conexionado de tres servos y cabecera de programación.

## Placa DOIT ViVi

Placa de control del robot ViVi de DOIT:
- módulo ESP8266 ESP-12F, Wi-Fi 2,4 GHz y 4 MB de flash;
- PCA9685 por I²C (dirección 0x40): 16 salidas PWM de 12 bits, a 50 Hz para servos;
- dos salidas de servo más, directas desde el ESP8266.

| Señal | GPIO del ESP8266 |
|---|---|
| SDA I²C | GPIO4 |
| SCL I²C | GPIO5 |
| /OE del PCA9685 (activo en bajo) | GPIO13 |
| Salidas de servo directas | GPIO12 y GPIO14 |
| UART de programación | GPIO1 (TX) y GPIO3 (RX) |

**Cabecera DOWNLOAD**, abajo a la derecha, de arriba abajo: TXD, RXD, 3V3 y GND.
- Usa un adaptador USB-UART de 3,3 V. Uno de 5 V o un RS-232 puede dañar el ESP8266.
- Conecta TXD al RX del adaptador, RXD a su TX y GND con GND.
- No conectes el 3V3 del adaptador si la placa ya tiene fuente.

**Modo de programación:** mantén pulsado S1, pulsa y suelta S2, y suelta S1.

**Conectores de servo:** los números serigrafiados son posiciones del robot ViVi, no canales del PCA9685. Comprueba con el polímetro qué patilla es GND y cuál V+ antes de conectar un servo.

## Alimentación

- Fuente regulada de 5 V y al menos 3 A para tres microservos. Dimensiónala sumando la corriente de bloqueo de los tres servos.
- Comprueba la polaridad y la tensión que admite la entrada DC de tu placa antes de conectarla. No apliques 7,4, 9 o 12 V sin comprobarlo.
- Nunca alimentes los servos desde 3V3.
- Conecta y desconecta los servos sin tensión.
- Con /OE desactivado los servos dejan de sujetar su posición.

## Referencias

- Manual de la placa (DOIT/SmartArduino): https://github.com/SmartArduino/ESPboard/blob/master/vivicontrolboard.pdf
- Código abierto del robot ViVi, de donde salen los GPIO de la tabla: https://github.com/Nicholas3388/ViVi-Robot
- Hoja de datos del PCA9685: https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf
- ESP8266_RTOS_SDK de Espressif: https://github.com/espressif/ESP8266_RTOS_SDK

Los esquemas de `ESQUEMAS/` son una reconstrucción funcional propia, no el esquema oficial de la placa. El manual del fabricante no se incluye por ser de terceros.
