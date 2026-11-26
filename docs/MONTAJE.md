# Montaje — lista de compra, conexionado, montaje paso a paso y calibración (v4)

Piezas impresas, orientación, tiempos y G-code: [IMPRESION.md](IMPRESION.md).

Esta guía usa el firmware autónomo para ESP32 de `firmware/` (PlatformIO), que se maneja desde el móvil. Para que el ojo siga a las personas con [ztrak-ojo](https://github.com/ibercomp/ztrak-ojo), usa en su lugar el Arduino Nano con el firmware de [`ViVi_DOIT_3_servos/UNO_AVR`](../ViVi_DOIT_3_servos/UNO_AVR): los servos van a D2 (giro), D3 (cabeceo) y D4 (párpados), con la misma fuente de 5 V y la masa común. El montaje mecánico es el mismo.

## 1. Lista de compra

| Cant. | Elemento | Dónde va |
|---|---|---|
| 3 | Servo **MG90S** (engranajes metálicos), con su tornillería y horns | Yaw (en la cuna), pitch (horquilla der.), parpadeo (detrás) |
| 4 | Rodamiento **684ZZ** (4×9×4) | Bujes de los 4 casquetes |
| 2 | Rodamiento **623ZZ** (3×10×4) | Pivote superior del globo (cuna) y pivote izquierdo de la cuna (horquilla izq.) |
| 2 | Pasador de acero **Ø4×32** h6 (ISO 8734 / DIN 6325) | Ejes de los párpados, a presión en los brazos |
| 4 | Suplemento calibrado **DIN 988 4×8×0,5** (traer también algunos de 0,2–0,3) | Juego axial de los párpados: 2 por lado |
| 19 | Inserto térmico de latón **M3** (para agujero de Ø4,0, largo ≤ 6 mm) | Travesaño 12 (6 delante, 4 en los extremos, 2 detrás), casquillo P23 2, casquetes P19/P21 1 + 1, balancín 1, globo 1, base 1 |
| 10 | **M3×10** DIN 912 | Horquillas (4), soporte del servo (2) y brazos (4) al travesaño |
| 2 | **M3×10** DIN 912 | Refuerzo del nudo P23 (pared trasera) a la cara trasera del travesaño |
| 3 | **M3×8** DIN 7984 (cabeza baja) + arandela M3 | Pivotes de biela con inserto: biela sup ↔ P19, biela sup ↔ balancín, biela inf ↔ P21 |
| 1 | **M3×12** DIN 7984 + tuerca **nyloc M3** + 2 arandelas | Biela inf ↔ balancín (pivote inferior) |
| 1 | **M3×10** DIN 912 + 2 arandelas **DIN 433** M3 (Ø6×0,5) | Pivote superior del globo (por el 623 de la cuna, al inserto del nervio) |
| 1 | **M3×14** DIN 912 + tuerca **nyloc M3** + 4 arandelas **DIN 433** M3 | Pivote izquierdo de la cuna (por el 623 de la horquilla izq.) |
| 3 | Prisionero **M3×6** DIN 916 | Tubo en el casquillo P23 (2) y en la base (1) |
| ~10 | M2×6 autorroscante (suelen venir con los servos) | Horn de yaw al globo (2), horn de pitch a la cuna (4), balancín al horn (4) |
| 1 | **Tubo de aluminio redondo Ø20×1,5**, 300 mm | Poste (solo hay que cortarlo a medida) |
| 1 | **ESP32 DevKitC** (WROOM-32) | Control |
| 1 | Fuente de **5 V / 3 A** (o más) | Servos y ESP32 |
| 1 | Condensador electrolítico de **1000 µF / 10 V** | En la alimentación de los servos |
| 3 | Alargador de servo de 50 cm | Bajan por el tubo hasta la base |
| — | Cianoacrilato, fijador de roscas medio (Loctite 243) | Párpados en casquetes, pupila/iris y pivotes con inserto |

Herramientas: soldador para los insertos (≈ 220 °C en PLA), llave Allen de 2,5 (en L), llave fija de 5,5 y un tornillo de banco o un sargento pequeño para meter los pasadores.

## 2. Conexionado

| Servo | Señal (naranja) | + (rojo) | − (marrón) |
|---|---|---|---|
| Yaw | **GPIO 13** | +5 V de la fuente | GND |
| Pitch | **GPIO 14** | +5 V de la fuente | GND |
| Parpadeo | **GPIO 27** | +5 V de la fuente | GND |

- Los servos se alimentan **directamente de la fuente de 5 V**, nunca del pin de 3,3 V ni del USB del ESP32.
- El ESP32 toma 5 V de la misma fuente por **VIN**. Las masas de la fuente y del ESP32 van unidas.
- Pon el condensador de 1000 µF entre +5 V y GND, junto a los conectores de los servos (polaridad: la franja va a GND).
- **Recorrido de los cables** (sin agujeros en zonas que trabajan):
  - yaw: sale de la cuna por la ranura de su placa izquierda, junto al eje de pitch, y baja por la cara **interior** de la horquilla izquierda;
  - pitch: baja por la cara interior de la horquilla derecha;
  - parpadeo: sale directamente del soporte del servo.
  - Los tres entran en el **canal de la cara delantera del travesaño** (9×4 mm, junto a la fibra neutra: le resta menos de un 2 % de rigidez), que bajo los pies queda tapado.
  - En el nudo P23 el canal sigue por dentro de su pared delantera y baja al tubo.
  - Abajo, el tubo apoya en un escalón y los cables salen por la **pared del cilindro de la base, por detrás**, entre las dos patas traseras (agujero en lágrima de Ø9,5).
  - Un conector Dupont de 3 pines cabe por todo el recorrido sin desmontarlo.

## 3. Antes de montar

1. Imprime la **probeta P99** (1 h 48 min) y prueba en ella un 684, un 623, un inserto, el pasador Ø4 y un tornillo M3. El valor de diseño es siempre el de **2 puntos**. Si tu impresora sale justa u holgada, ajusta las cotas en `parametros/ojo.json` (`rodamiento_alojamiento_D`, `insertos.agujero_D`…) y regenera las piezas.
2. Graba el firmware (`cd firmware && pio run -t upload`) y conecta los 3 servos **sin horns**. Al arrancar se quedan en la posición de montaje: mirada al frente y párpados cerrados. Monta los horns en esa posición.

## 4. Montaje paso a paso

1. **Insertos.** Coloca los 19 insertos con el soldador, rectos y a ras.
2. **Globo.** Pega la pupila (P02) en el iris (P17) y el conjunto en el agujero frontal del globo, desde dentro.
3. **Cuna y yaw.**
   - Atornilla el servo de yaw en la cuna con los tornillos de sus pestañas.
   - Mete el 623 a presión en el alojamiento de la barra superior de la cuna.
   - Atornilla el horn de yaw (doble brazo, agujeros a 8 mm) al nervio inferior del globo con 2 M2.
   - Mete la cuna en el globo por la boca trasera y encaja el horn en el servo.
4. **Pivote superior (yaw).**
   - Desde dentro de la cuna, pasa un M3×10 de abajo arriba por el agujero de Ø8 y el 623, con 2 arandelas DIN 433 entre el rodamiento y el nervio del globo.
   - Rosca el tornillo en el inserto del nervio con una gota de fijador.
   - La cabeza aprieta solo el aro interior; el globo debe girar suave.
   - Usa la llave Allen en L, metida por el lateral, porque el servo queda debajo.
5. **Marco.**
   - **Primero el nudo:** pasa el travesaño por la ranura del nudo P23 (encaje por forma, 0,1 mm de juego) hasta que los 2 insertos traseros queden frente a sus agujeros, y pon los 2 M3×10 de refuerzo por la pared trasera. Después ya no cabe: los pies de las horquillas y del soporte no pasan por el nudo.
   - Horquillas (P06, P07) y soporte del servo (P16) al travesaño, con 6 M3×10.
   - Servo de pitch en la horquilla derecha.
   - 623 en el alojamiento de la horquilla izquierda.
6. **Cuna en el marco.**
   - Atornilla el horn de pitch (en cruz) a la placa derecha de la cuna con 4 M2 y encájalo en el servo de pitch.
   - Pivote izquierdo: pasa el M3×14 desde fuera de la horquilla por el agujero de Ø8, con 1 arandela bajo la cabeza. Atraviesa el 623, luego 3 arandelas DIN 433 (rellenan el hueco de 1,5 mm) y la placa izquierda de la cuna, y cierra con la nyloc por dentro.
   - Aprieta: la cabeza solo debe pisar el aro interior. Comprueba que el pitch gira libre.
7. **Párpados.**
   - Mete un 684 a presión en cada casquete. Los inferiores (P21/P22) entran por la cara de la cama, que lleva el alivio.
   - Presenta cada cáscara en seco sobre sus dos casquetes: apoya en el asiento y su canto toca el escalón radial.
   - Pega con cianoacrilato en el asiento y mantén unos 30 s.
8. **Ejes y juego axial** (en cada lado).
   - Mete a presión el pasador Ø4×32 en el brazo (P09/P10), por la cara exterior.
   - Coloca los párpados alrededor del globo, el inferior primero.
   - En cada lado, la pila es: buje inferior → **suplemento 0,5** → buje superior → **suplemento 0,5** → espiga del brazo.
   - Mete el pasador por los rodamientos y atornilla el brazo al travesaño con 2 M3×10.
   - **Juego axial total ≤ 0,2 mm.** Sin suplementos sería de unos 1,05 mm y el casquete inferior podría rozar el globo (holgura 0,45 mm). Si queda duro, cambia un suplemento de 0,5 por uno de 0,3.
9. **Parpadeo.**
   - Atornilla el servo trasero en el soporte P16.
   - Fija el balancín (P11) al horn redondo con 4 M2 y el tornillo central, con el servo en la posición de **párpados cerrados** (arranque del firmware o comando `b 0`).
   - Biela superior (P13): al saliente del casquete P19 y al pasador superior del balancín, con M3×8 + arandela en los insertos.
   - Biela inferior (P14): al saliente del casquete P21 (M3×8 al inserto) y al pasador inferior del balancín (M3×12 con nyloc).
   - En los tornillos con inserto: aprieta hasta tocar, afloja 1/8 de vuelta y fija con Loctite 243. La biela tiene que girar sin juego.
10. **Poste y base.**
    - Mete el tubo en el casquillo hasta el tope cónico y aprieta los 2 prisioneros.
    - Monta la base abajo y aprieta su prisionero.
    - Pasa los cables por el canal del travesaño, el nudo y el tubo hasta la salida trasera de la base.

## 5. Estabilidad

El conjunto pesa unos 500 g y su centro de gravedad queda a unos 276 mm de la mesa y 35–50 mm **por delante del tubo**, porque el ojo cuelga delante del travesaño.

La base es una **X calculada a partir de esa carga** (`herramientas/estabilidad.py --disenar 15`):
- Cada borde del apoyo es tangente a la zona que ocupa el centro de gravedad en todas las poses, ampliada en altura × tan 15°. Las puntas de las patas son las esquinas.
- **Delanteras**: largas, unos 153 mm a ±36°.
- **Traseras**: cortas y casi laterales, unos 64 mm a ±108°.
- Ninguna pata es más larga de lo necesario.

Resultado:
- Hay que inclinar la mesa **15°** para volcarlo. Las normas de equipos ensayan con 10°.
- Ante arranques bruscos de parpadeo o sacada, la reserva es de ×1,2 o más.
- Si cambian las piezas, se recalculan las patas con el mismo comando y se reconstruye P15.

**Forma de la base:**
- Patas en cuña de 12 a 5 mm de alto y de 18 a 12 mm de ancho, hechas en SolidCraft por solevado de dos secciones.
- Las aristas superiores van redondeadas R2 en la propia sección. Puntas rectas y unión viva con el buje.

## 6. Calibración (consola serie a 115200, comando `ayuda`)

1. `us yaw 1500`: si el ojo no mira recto al frente, ajusta los µs hasta que lo haga y apunta el valor en `CAL_YAW.us_centro` (`firmware/src/config.h`). Haz lo mismo con `us pitch …`.
2. `us parpadeo 1865`: busca los µs con los párpados justo cerrados → `CAL_PARPADEO.us_centro`.
3. `y 30`, `y -30`, `p 25`, `p -25`: si alguno va al revés, cambia el `sentido` (±1) de ese servo.
4. `b 60`: los párpados deben quedar abiertos 60°. Si se quedan cortos o se pasan, corrige `us_por_grado` del parpadeo. El firmware usa la tabla real del cuadrilátero (`parpadeo_tabla.h`, generada por `herramientas/tabla_parpadeo.py`).
5. Vuelve a grabar y `auto 1`. Desde el móvil: WiFi **OjoAnimatronico** (clave `cambia-esta-clave`) y abre `http://192.168.4.1`.

Los límites del firmware (yaw ±30°, pitch ±25°, párpado 0–60°) son los comprobados sin choques en `herramientas/verificar.py`. No los amplíes sin volver a verificar.
