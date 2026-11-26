# Ojo animatrónico Ø150 · guía del CAD (v4)

Todo el diseño sale del CAD paramétrico: las cotas están en `parametros/ojo.json` y los scripts de `herramientas/` generan las piezas.

## 1. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Cotas maestras (fuente única) | `parametros/ojo.json` |
| Geometría de cada pieza (genera los comandos de SolidCraft) | `herramientas/piezas.py`, `herramientas/piezas2.py`, capa `herramientas/sc.py` |
| Diseños SolidCraft editables | `cad/sc/*.sc` (una pieza por fichero) y `cad/sc/CONJUNTO_ojo.sc` (montaje con articulaciones y estudios de movimiento) |
| Sólidos para otros CAD | `cad/step/*.step` |
| Mallas en posición de montaje | `cad/stl/*.stl` |
| Mallas orientadas para la cama | `imprimir/*.stl` (con `herramientas/bandejas.py`) |
| G-code | No se incluye: se genera con `herramientas/laminar.py` en `imprimir/gcode/` (Ender/Anet, 200×200) |
| Planos A3 | `docs/PLANOS_A3.pdf` |
| Impresión | `docs/IMPRESION.md` |
| Compra, conexionado, montaje y calibración | `docs/MONTAJE.md` |
| Firmware ESP32 autónomo (control por el móvil) | `firmware/` (PlatformIO) |
| Firmware para el seguimiento con [ztrak-ojo](https://github.com/ibercomp/ztrak-ojo) | `ViVi_DOIT_3_servos/` (Arduino Nano recomendado) |

## 2. Coordenadas

- **O** = centro común del globo y de las dos cáscaras de los párpados. Unidades en mm y grados.
- **X** a la derecha mirando el ojo de frente, **Y** arriba, **Z** hacia delante (hacia donde mira el ojo).
- Ángulo **α** de los párpados: desde +Z hacia +Y alrededor de X.
- **Pitch** (la cuna) y los **dos párpados** giran sobre el eje X por O. El **yaw** (el globo) gira sobre el eje Y de la cuna.
- Las piezas están modeladas **en su posición de montaje**: un STEP o STL se coloca en el conjunto sin moverlo.
- En los planos, las vistas siguen el **primer diedro (ISO-E)**: alzado desde +Z, planta desde +Y debajo del alzado y perfil izquierdo desde −X a su derecha.

## 3. Cotas maestras (de `parametros/ojo.json`)

| Parámetro | Valor |
|---|---|
| Globo: radio exterior / espesor | R68 / 1,6 |
| Globo: corte trasero (boca) | z = -26 |
| Pupila / iris | Ø42 / Ø58 (pestañas Ø46 y Ø64) |
| Párpado superior: Ri / Ro / sector α | R73,8 / R75 / -5° … 97° |
| Párpado inferior: Ri / Ro / sector α | R72,1 / R73,3 / -95° … 0° |
| Espesor de las cáscaras de párpado | 1,2 (3 perímetros de 0,4) |
| Junta párpado–casquete (cono radial desde ±X) | sup 15°, inf 13,5°, holgura de canto 0,15 |
| Casquetes: cara plana interior | x = ±68,4 |
| Eje de los párpados | pasador Ø4 en 684ZZ (alojamiento Ø9,1) |
| Movimientos | yaw ±30°, pitch ±25°, párpados 0–60° |
| Servo de parpadeo: eje H (Y, Z) | (12,87; -63,51) |
| Balancín: brazos (r, ángulo) | sup 14,32 a -47,11° · inf 14,62 a -81,83° |
| Palancas de los casquetes (r, ángulo) | sup 17 a 68,94° · inf 16,95 a -75,75° |
| Bielas (entre centros) | sup 61,37 · inf 67,26 |
| Recorrido del servo de parpadeo | 73,1° para 0–60° |
| Travesaño (perfil común del marco) | 24 × 12 (Y ±12, Z -95 … -83), X ±94,6 |
| Poste | tubo de aluminio Ø20 × 1,5, 300 mm, eje en x = 3,5, z = -89 |
| Nudo P23 | ranura = perfil del travesaño + 0,1; tope del tubo a 16 bajo la cara superior |
| Base en X (calculada para vuelco a 15°) | delanteras 152,8 mm a ±35,9°, traseras 63,5 mm a ±108,1° (desde +Z); patas 18→12 en cuña de 12 a 5 de alto, por solevado, aristas superiores R2, puntas rectas; cámara de cables Ø16, salida Ø9,5 por detrás |
| Insertos térmicos M3 | agujero Ø4 × 6,5; paso de tornillo Ø3,4 |
| Servo MG90S (envolvente; mide los tuyos) | 22,8 × 12,2 × 22,7, holgura 0,3 |

Para cambiar una cota: edita `parametros/ojo.json` y reconstruye las piezas afectadas
(`.venv/bin/python herramientas/construir.py P05_cuna …`). Después repite la verificación (apartado 6).

## 4. Piezas

| Ref. | Pieza | Cant. | Material | Qué hace |
|---|---|---:|---|---|
| P01 | Globo | 1 | PLA blanco | Esfera R68 × 1,6 con boca trasera (z = −26). Lleva el iris y la pupila delante y dos nervios internos: el superior pivota en el 623 de la cuna (yaw) y el inferior recibe el horn del servo de yaw. |
| P17 | Iris | 1 | PLA de color | Aro Ø58 alrededor de la pupila con pestaña Ø64 bajo la cáscara del globo; entra por dentro del globo. |
| P02 | Pupila | 1 | PLA negro | Disco Ø42 que atraviesa el iris, con pestaña Ø46 por detrás. Se pega al iris. |
| P03 | Párpado superior | 1 | PLA (color párpado) | Cáscara esférica R73,8–75 (1,2 mm, 3 perímetros) de α −5° a 97°. Termina en cortes radiales que asientan sobre los casquetes P19/P20, donde se pega. |
| P04 | Párpado inferior | 1 | PLA (color párpado) | Cáscara esférica R72,1–73,3 de α −95° a 0°. Al cerrar queda por dentro del superior (solape de 5°). Se pega sobre los casquetes P21/P22. |
| P19 | Casquete superior derecho | 1 | PLA (color párpado) | Polo de la esfera del párpado superior con asiento, buje con 684 y saliente de palanca con inserto M3 para la biela superior. |
| P20 | Casquete superior izquierdo | 1 | PLA (color párpado) | Polo izquierdo del párpado superior con asiento y buje con 684 (sin palanca). |
| P21 | Casquete inferior derecho | 1 | PLA (color párpado) | Polo derecho del párpado inferior con buje 684, saliente de palanca con inserto M3 (biela inferior) y chaflán a 45°. |
| P22 | Casquete inferior izquierdo | 1 | PLA (color párpado) | Polo izquierdo del párpado inferior con buje 684 y alivio de pata de elefante. |
| P05 | Cuna (pitch) | 1 | PLA | Gira sobre X en O. Lleva el servo de yaw en la bandeja inferior, el 623 del pivote superior del globo y el horn de pitch en su placa derecha; su placa izquierda gira en el 623 de la horquilla izquierda. |
| P06 | Horquilla izquierda | 1 | PLA | Brazo fijo que entra por la boca trasera del globo; aloja el 623 del pivote izquierdo de la cuna. Pie con redondeos cóncavos y 2 M3 al travesaño. |
| P07 | Horquilla derecha | 1 | PLA | Brazo fijo con el alojamiento del servo de pitch (MG90S). Pie con redondeos cóncavos y 2 M3 al travesaño. |
| P08 | Travesaño | 1 | PLA | Viga 189 × 24 × 12 (perfil común del marco). Recibe horquillas, soporte del servo y brazos con insertos; canal de cables en la cara delantera; pasa por el nudo P23. |
| P09 | Brazo derecho | 1 | PLA | Lleva el pasador Ø4 de los párpados (lado derecho) y la ventana de las bielas; 2 M3 al extremo del travesaño. |
| P10 | Brazo izquierdo | 1 | PLA | Lleva el pasador Ø4 de los párpados (lado izquierdo); 2 M3 al extremo del travesaño. |
| P11 | Balancín | 1 | PLA | Balancín de doble brazo atornillado al horn del servo de parpadeo; pasadores de las dos bielas. |
| P13 | Biela superior | 1 | PLA | Une el balancín con la palanca del casquete P19 (L = 61,37 entre centros). |
| P14 | Biela inferior | 1 | PLA | Une el balancín con la palanca del casquete P21 (L = 67,26 entre centros). |
| P16 | Soporte del servo de parpadeo | 1 | PLA | Sujeta el servo trasero de parpadeo al travesaño (2 M3), con redondeos cóncavos en la raíz. |
| P23 | Casquillo del poste (nudo) | 1 | PLA | Nudo entre el travesaño y el tubo Ø20: ranura con el perfil del travesaño (+0,1) que lo abraza por forma, tope cónico del tubo, 2 prisioneros M3 y 2 M3 de refuerzo; canal de cables hacia el tubo. |
| P15 | Base | 1 | PLA | Base en X: buje con escalón de apoyo y cámara de cables con salida trasera; 4 patas por solevado en cuña (12 → 5 mm de alto, 18 → 12 de ancho) con aristas superiores R2 y puntas rectas. Ángulos y longitudes calculados desde el centro de gravedad (`herramientas/estabilidad.py --disenar 15`): vuelco a 15°. |
| P99 | Probeta de ajustes | 1 | PLA | Placa de pruebas: alojamientos de 684 y 623, insertos, pasador Ø4 y tornillos en variantes. Imprimir antes que nada. |

De compra (en el conjunto): Servo MG90S (yaw), Servo MG90S (pitch), Servo MG90S (parpadeo), Horn de yaw, Horn de pitch, Horn del parpadeo, Tubo aluminio Ø20×1,5, además de los rodamientos, pasadores, suplementos, insertos y tornillería de
`docs/MONTAJE.md`.

Cada hoja de pieza de `PLANOS_A3.pdf` trae las tres vistas con aristas ocultas, una isométrica, las cotas de envolvente, la tabla
de agujeros y ejes leída de las caras cilíndricas del STEP (letras en rojo sobre las vistas), las superficies esféricas,
la orientación de impresión y el tiempo y los gramos del G-code.

## 5. Cómo se construye el CAD

1. `herramientas/construir.py [pieza …]` genera cada pieza con SolidCraft (CLI): guarda `cad/sc`, `cad/step` y `cad/stl`. Si la app está abierta con el canal 7878, también la construye en vivo.
2. Reglas del núcleo de SolidCraft 0.30 que respeta el código:
   - 0,05 mm de solape entre revoluciones coaxiales;
   - nada de cuerpos con varias partes;
   - vaciados agrupados;
   - las piezas se construyen en su sitio, sin mover cuerpos ya terminados.
3. Reglas de diseño para FDM (boquilla de 0,4, capa de 0,2):
   - techos sobre agujeros que nacen en la cama con puente escalonado;
   - alivio de 0,4 mm en los ajustes que tocan la cama;
   - insertos horizontales en lágrima;
   - juntas de cáscara con corte radial;
   - redondeos cóncavos en lugar de cartelas;
   - nada que sobresalga del perfil común del marco.

## 6. Verificación

| Comprobación | Orden | Resultado actual |
|---|---|---|
| Interferencias (125 poses, todos los sólidos) | `herramientas/verificar.py` | sin interferencias |
| Imprimibilidad capa a capa | `herramientas/imprimibilidad.py` | todas imprimibles; soporte solo dentro de los párpados |
| Laminado real | `herramientas/laminar.py` (PrusaSlicer 2.9) | sin avisos de estabilidad (salvo el esperado de P19/P20) |

## 7. Montaje en SolidCraft

`cad/sc/CONJUNTO_ojo.sc` inserta las piezas como componentes enlazados, con el marco fijo y las articulaciones de pitch,
yaw y párpados, el balancín y las bielas. Para mover a mano un conjunto que no responde, revisa dos cosas:

- que no esté activa la herramienta de desplazamiento de la barra flotante (✥); se quita con Esc;
- que el marcador del historial esté al final.

## 8. Antes de fabricar

1. **Mide tus servos MG90S** y corrige `servo` en `parametros/ojo.json` si no coinciden.
2. **Imprime la probeta P99** y ajusta los alojamientos de 684 y 623, los insertos y el pasador.
3. Sigue el orden de montaje de `docs/MONTAJE.md`. El nudo P23 va en el travesaño **antes** que las horquillas y el soporte.

