"""Lamina con PrusaSlicer (CLI, flatpak) todas las piezas ya orientadas (imprimir/*.stl de bandejas.py) y comprueba
el resultado real del laminador:

  1. G-CODE FINAL: lamina con la configuración de cada pieza (soportes solo donde están previstos, borde…) y
     guarda imprimir/gcode/<pieza>.gcode con tiempo, gramos, puentes y perímetros en voladizo.
  2. ESTABILIDAD: en las piezas sin soportes, el análisis de PrusaSlicer ("Detected print stability issues":
     anclajes de puente en el aire, extrusiones sueltas, puentes largos, poca adherencia) no debe avisar.
     Es el mismo análisis que muestra la interfaz. Única excepción documentada: P19/P20, cuyo buje imprime
     sobre el tapón suelto con 1 capa de hueco (como un soporte del laminador, que PrusaSlicer no reconoce).
  Informativo: cuánto soporte añadiría PrusaSlicer en automático (umbral 45°, conservador: también soporta
  puentes cortos que imprimen bien).

  .venv/bin/python herramientas/laminar.py [pieza ...]

Perfil: imprimir/perfiles/ender3pro_pla_0.2.ini (Marlin 2, cama 200×200, boquilla 0,4, PLA 1,75).
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imprimibilidad import CFG, RAIZ

PERFIL = os.path.join(RAIZ, "imprimir", "perfiles", "ender3pro_pla_0.2.ini")
GC = os.path.join(RAIZ, "imprimir", "gcode")
APP = ["flatpak", "run", f"--filesystem={RAIZ}", "com.prusa3d.PrusaSlicer"]

# «Floating bridge anchors» esperados: P19/P20 (buje sobre el tapón suelto), P05 (puente escalonado de 13,6 mm del
# agujero central, a z ≈ 53) y P23 (techo de la ranura del travesaño, 12 mm entre las paredes curvas del cilindro).
# imprimibilidad.py: puentes ≤ 13,6 mm, sin ménsulas ni islas.
AVISO_ESPERADO = {"P19_casquete_sup_der", "P20_casquete_sup_izq", "P05_cuna", "P23_casquillo_poste"}

# ajustes por pieza para el G-code final (además del perfil)
AJUSTES = {
    "P03_parpado_sup": ["--support-material", "--brim-width", "5"],
    "P04_parpado_inf": ["--support-material", "--brim-width", "5"],
    "P01_globo": ["--brim-width", "4"],       # apoya en un aro de 1,6 mm
    "P05_cuna": ["--brim-width", "3"],        # 58 mm de alto sobre 376 mm²
    "P21_casquete_inf_der": ["--brim-width", "3"],   # saliente de 18 mm de alto
    "P23_casquillo_poste": ["--brim-width", "5"],    # 66 mm de alto sobre 305 mm² (PrusaSlicer: «Low bed adhesion»)
}


def laminar(stl, salida, extra):
    cmd = APP + ["--export-gcode", "--load", PERFIL, "--center", "100,100", *extra, "-o", salida, stl]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    avisos = [l.strip() for l in log.splitlines()
              if re.search(r"(?i)warn|error|support|overhang|stabil|empty|collaps|loose|anchor|adhesion|bridg", l)
              and not re.search(r"locale|xapp-gtk|^\d+ =>|LC_ALL", l)]
    if r.returncode != 0 or not os.path.exists(salida):
        raise RuntimeError(f"PrusaSlicer falló en {stl}:\n{log[-1500:]}")
    return avisos


def leer(gcode):
    """extrusión (mm de filamento) por tipo, tiempo y gramos"""
    tipo, e_ant, por_tipo = None, 0.0, {}
    tiempo = gramos = None
    rel = False
    with open(gcode) as f:
        for l in f:
            if l.startswith(";TYPE:"):
                tipo = l[6:].strip(); continue
            if l.startswith("M83"):
                rel = True
            elif l.startswith("M82"):
                rel = False
            if l.startswith("G92") and " E" in l:
                e_ant = float(re.search(r"E([-\d.]+)", l).group(1)); continue
            if l.startswith(("G1", "G0")) and " E" in l:
                m = re.search(r"E([-\d.]+)", l)
                if m:
                    e = float(m.group(1)); de = e if rel else e - e_ant
                    if not rel:
                        e_ant = e
                    if de > 0 and tipo and (" X" in l or " Y" in l):   # sin XY = recuperar retracción
                        por_tipo[tipo] = por_tipo.get(tipo, 0.0) + de
            if l.startswith("; estimated printing time (normal mode)"):
                tiempo = l.split("=")[1].strip()
            if l.startswith("; total filament used [g]"):
                gramos = float(l.split("=")[1])
    return por_tipo, tiempo, gramos


def estabilidad(avisos):
    """problemas de estabilidad que PrusaSlicer detecta (líneas tras 'Detected print stability issues')"""
    return [a for a in avisos if re.search(r"(?i)anchor|loose|bridging|adhesion|collaps|overhang", a)]


if __name__ == "__main__":
    os.makedirs(GC, exist_ok=True)
    nombres = sys.argv[1:] or [k for k in CFG if not k.startswith("_")]
    fallo, total_g = False, 0.0
    for n in nombres:
        stl = os.path.join(RAIZ, "imprimir", f"{n}.stl")
        c = CFG[n]
        previsto = not c.get("sin_soportes", True)
        final = os.path.join(GC, f"{n}.gcode")
        avisos = laminar(stl, final, AJUSTES.get(n, []))
        tipos, tiempo, g = leer(final)
        total_g += g or 0
        prob = estabilidad(avisos)
        if prob and n in AVISO_ESPERADO:
            est = "OK (tapón: aviso esperado)"
        elif prob:
            est = "AVISO DE ESTABILIDAD"; fallo |= not previsto
        else:
            est = "con soportes" if previsto else "OK sin soportes"
        # informativo: soporte automático
        prueba = os.path.join(GC, f"_auto_{n}.gcode")
        laminar(stl, prueba, ["--support-material"])
        auto = sum(v for k, v in leer(prueba)[0].items() if "upport" in k); os.remove(prueba)
        sop = sum(v for k, v in tipos.items() if "upport" in k)
        print(f"{n:22s} {est:28s} {tiempo:>12s} {g:6.1f} g   soporte {sop / 1000:5.1f} m   puentes {tipos.get('Bridge infill', 0) / 1000:4.1f} m"
              f"   (auto 45°: {auto / 1000:4.1f} m)")
        for a in prob:
            print(f"{'':24s}· {a}")
    print(f"\nTotal: {total_g:.0f} g de PLA")
    sys.exit(1 if fallo else 0)
