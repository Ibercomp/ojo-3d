"""Genera firmware/src/parpadeo_tabla.h: ángulo del servo de parpadeo para cada apertura del párpado superior
(0..60°, paso 1°), con la MISMA cinemática del cuadrilátero que comprueba verificar.py.

  .venv/bin/python herramientas/tabla_parpadeo.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificar as V

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = int(V.MOV["parpado_max"])
filas = [V.parpadeo_v2(float(t))[:2] for t in range(N + 1)]
gam = [g for g, _ in filas]
out = os.path.join(RAIZ, "firmware", "src", "parpadeo_tabla.h")
with open(out, "w") as f:
    f.write("// GENERADO por herramientas/tabla_parpadeo.py — no editar a mano.\n")
    f.write("// Giro del servo de parpadeo (grados, respecto a la posición de párpados cerrados) para una apertura\n")
    f.write(f"// del párpado superior de 0..{N}° (índice = grados). Párpado inferior real a {N}°: {filas[-1][1]:.2f}°.\n")
    f.write("#pragma once\n")
    f.write(f"constexpr int PARPADO_MAX_DEG = {N};\n")
    f.write(f"constexpr float SERVO_PARPADEO_GIRO[{N + 1}] = {{\n")
    for i in range(0, N + 1, 8):
        f.write("  " + ", ".join(f"{-g:.3f}f" for g in gam[i:i + 8]) + ",\n")
    f.write("};\n")
print(f"{out}: γ(0)={gam[0]:.2f}°, γ({N})={gam[-1]:.2f}°, párpado inf a {N}° = {filas[-1][1]:.2f}°")
