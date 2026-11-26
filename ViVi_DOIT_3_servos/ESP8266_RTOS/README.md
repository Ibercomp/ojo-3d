# Firmware del ojo para ESP8266 (ESP8266_RTOS_SDK)

Firmware en C sobre el SDK RTOS oficial de Espressif, sin Arduino, para la placa DOIT ViVi (ESP8266EX con 4 MB de flash y PCA9685). Es el controlador que usaba el ojo antes de pasar al Arduino Nano por USB (ver [`../UNO_AVR`](../UNO_AVR)). Se mantiene como alternativa por Wi-Fi.

Al arrancar, las salidas de los servos quedan desactivadas hasta que se piden con `/encender`.

## Configurar y compilar

1. Instala ESP8266_RTOS_SDK de Espressif y su toolchain 8.4.0.
2. Crea `main/wifi_privada.h`. Este archivo no se sube a git:

   ```c
   #define WIFI_SSID "nombre de red"
   #define WIFI_PASSWORD "clave de red"
   #define OTA_TOKEN "token largo y aleatorio"
   ```

3. Compila con `idf.py build`. `sdkconfig.defaults` selecciona una tabla con dos particiones OTA de 0xf0000 bytes.

La primera instalación se hace por puerto serie: bootloader, tabla de particiones, datos OTA y aplicación, siguiendo las instrucciones que imprime `idf.py build`. Las siguientes pueden ir por OTA.

`sdkconfig.defaults` desactiva el watchdog NMI (`CONFIG_ESP8266_NMI_WDT`). Según el [Kconfig de Espressif](https://github.com/espressif/ESP8266_RTOS_SDK/blob/master/components/esp8266/Kconfig), ese watchdog no es compatible con el PWM del SDK. El watchdog de tareas sigue activo.

## OTA

```sh
python3 tools/actualizar_ota.py IP_DEL_OJO
```

Envía `build/vivi_ojo.bin`. La placa comprueba el token de `wifi_privada.h`, detiene las salidas, escribe la partición inactiva y solo la selecciona si `esp_ota_end` acepta la imagen. No hay vuelta atrás automática: si una imagen no arranca, hay que recuperarla por serie.

La comunicación es HTTP local sin cifrar. El movimiento no lleva autenticación, así que úsalo solo en una red de confianza.

## Calibración

La calibración se guarda en NVS y se conserva al actualizar por OTA. Con las salidas apagadas se ajusta desde la web o con:

```
/ajuste?eje=giro&canal=N
```

- Ejes: `giro`, `cabeceo` y `parpado`.
- Canales: PCA 0..15, más GPIO12 = 16 y GPIO14 = 17.

En nuestro montaje usamos canales `[0,1,17]`, sentidos `[1,-1,-1]` y centros `[1560,1470,1810]` µs. Son valores de ese montaje: calibra el tuyo.

## API

Por HTTP y por UART, con el mismo intérprete (`control_protocol.h`) y el mismo núcleo (`control_core.h`).

| Orden | Función |
|---|---|
| `/estado` | Versión, salidas, calibración, límites, `actual` (consigna interpolada, no posición medida), diagnóstico |
| `/encender`, `/apagar`, `/centrar` | Activa o desactiva las salidas y centra la mirada |
| `/seguir?giro=G&cabeceo=C&parpado=P&reposo=0\|1` | Última consigna de seguimiento |
| `/parpadear`, `/mover` | Parpadeo y movimiento manual |
| `/patron?nombre=...` | Patrones de demostración: `mezcla`, `natural`, `rapido`, `doble`, `enfadado`, `lado`, `mareado`, `repaso`, `curioso`, `atento`, `busqueda` |
| `/limites?up=...&down=...` | Curva de límites combinados (ver abajo); solo con las salidas apagadas |
| `/pca` | Lectura de registros del PCA9685, para diagnóstico |

Detalles de `/seguir`:
- Con las salidas apagadas responde 409.
- Si faltan ángulos o no son números finitos, responde 400.
- `reposo=1` permite cerrar el párpado hasta 60° y no genera parpadeos espontáneos. En modo normal, el cierre parcial llega hasta 32°.
- Si en 700 ms no llega ninguna consigna, el ojo frena y abre el párpado.
- Durante el parpadeo el globo se queda quieto.

### UART0

230400 baudios, 8N1, sin control de flujo, con niveles de 3,3 V. Formato por líneas:

```
@OJO 42 /seguir?giro=12&cabeceo=-4&parpado=26&reposo=0
@OJO 42 200 {JSON de estado}
```

Se ignoran las líneas sin el prefijo `@OJO`. Si se pierde el Wi-Fi, las salidas solo se apagan cuando la última orden activa no llegó por UART.

### UDP

Flujo binario de seguimiento en el puerto 4210. Formato y reglas en [UDP.md](UDP.md).

## Límites de movimiento

`motion_limits.h` define una región convexa: el margen vertical, hacia arriba y hacia abajo, en siete valores de giro (−55, −45, −30, 0, +30, +45 y +55°).

- `/estado` devuelve esa curva en `limits.up` y `limits.down`.
- `/limites` la valida y la guarda en NVS.
- El motor limita tanto el destino como el recorrido entre alturas.

Los valores por defecto corresponden a nuestro mecanismo.

## Movimiento

- Control y PWM a 50 Hz. El PCA9685 tiene 4096 pasos: unos 4,88 µs por paso, aproximadamente 0,49° con nuestra escala.
- Trayectorias quínticas, con velocidad y aceleración nulas al llegar.
- El seguimiento usa integración críticamente amortiguada.
- Las órdenes de la red se interpolan en una ventana de 40 ms.
- Velocidad máxima de mirada: 80°/s.
- Parpadeo asimétrico: cierre rápido y apertura más lenta con frenado final. Como referencia se tomó la [caracterización de parpadeos con cámara rápida](https://pmc.ncbi.nlm.nih.gov/articles/PMC4043155/).

## Pruebas

Las pruebas en C ejecutan el mismo motor que la placa, sin hardware:

```sh
cc -std=c99 -Wall -Wextra -fsanitize=address,undefined tests/test_animacion.c -lm -o test_animacion && ./test_animacion
```

Otras suites del mismo tipo:
- `tests/test_control.c`
- `tests/test_limits.c`
- `tests/test_servo_output.c`
- `tests/test_stream.c`
- `tests/test_udp.c`
- `tests/test_follow_velocity.c`
- `tests/test_pca_diagnostic.c`

Herramientas en `tools/`:
- `simular_motor.py` ejecuta el motor C con un servidor HTTP/UDP local, para probar la aplicación sin placa.
- `capturar_uart.py` solo lee `/estado` y lo guarda en JSONL.
- `verificar_horizontal.py` hace un barrido físico lento y apaga al terminar.

Ninguna de estas pruebas mide la posición física del servo.
