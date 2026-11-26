"""Centro de gravedad del ojo completo y estabilidad del trípode (vuelco estático y por los movimientos).

  .venv/bin/python herramientas/estabilidad.py

Masas: piezas impresas = gramos del G-code (imprimir/gcode) quitando soporte y borde (proporción de extrusión);
compra = valores nominales (MG90S 13,4 g…), tubo = volumen × 2,7 g/cm³. Centro de cada pieza = centroide del
sólido (densidad uniforme: aproximación). Apoyo = envolvente convexa de la cara inferior real de P15.
Vuelco estático: ángulo que se puede inclinar la mesa antes de volcar = atan(distancia al borde / altura del CDG).
Dinámico: momento sobre cada borde de apoyo en el arranque de un parpadeo y de una sacada (servo a velocidad máxima
en ~20 ms), comparado con el momento estabilizador del peso.
"""
import math, os, sys

import numpy as np, trimesh
from shapely.geometry import MultiPoint, Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verificar as V
from laminar import leer
from sc import RAIZ

STL = os.path.join(RAIZ, "cad", "stl"); GC = os.path.join(RAIZ, "imprimir", "gcode")
G = 9.81
T_ARRANQUE = 0.02           # s hasta la velocidad máxima del servo
W_SERVO = math.radians(600)  # MG90S ≈ 0,1 s/60° a 5 V

COMPRA_G = {"C_servo_yaw": 13.4, "C_servo_pitch": 13.4, "C_servo_parpadeo": 13.4,
            "C_horn_yaw": 1.0, "C_horn_pitch": 1.0, "C_horn_parpadeo": 1.0}
# (masa g, punto, grupo de movimiento) — tornillería y demás, estimados
EXTRA = [(4 * 1.1, (0, 0, 0), "fijo", "4 rodamientos 684ZZ (en el eje X)"),
         (1.6, (0, 29.5, 0), "cuna", "623ZZ de la cuna"), (1.6, (-14.5, 0, 0), "fijo", "623ZZ de la horquilla"),
         (2 * 3.2, (0, 0, 0), "fijo", "2 pasadores Ø4×32 (en el eje X)"),
         (19 * 0.4 + 25 * 0.7, (3.5, 0, -89), "fijo", "insertos y tornillería (en el travesaño)"),
         (25.0, None, "tubo", "cables de los servos (dentro del tubo)")]


def masa_impresa(n):
    tipos, _, g = leer(os.path.join(GC, f"{n}.gcode"))
    total = sum(tipos.values())
    util = sum(v for k, v in tipos.items() if "upport" not in k and k not in ("Skirt/Brim", "Custom"))
    return g * util / total


def cargar():
    piezas = {}
    for f in sorted(os.listdir(STL)):
        if not f.endswith(".stl") or f.startswith("P99"):
            continue
        n = f[:-4]; t = trimesh.load(os.path.join(STL, f), force="mesh")
        m = (COMPRA_G.get(n) if n in COMPRA_G else t.volume * 2.7e-3 if n == "C_tubo_alu" else masa_impresa(n)) / 1000
        k = m / t.volume                                   # kg/mm³ equivalente (uniforme)
        I = t.moment_inertia * k * 1e-6                    # kg·m² (mm² → m²)
        piezas[n] = {"m": m, "c": t.center_mass / 1000, "I": I, "t": t}
    return piezas


def cdg(piezas, T):
    M = 0.0; S = np.zeros(3)
    for n, p in piezas.items():
        Tn = T.get(n, np.eye(4)); c = Tn[:3, :3] @ (p["c"] * 1000) + Tn[:3, 3]
        M += p["m"]; S += p["m"] * c / 1000
    tubo = piezas["C_tubo_alu"]["c"]
    for g, pt, grupo, _ in EXTRA:
        c = tubo if pt is None else np.array(pt) / 1000
        if grupo == "cuna":
            Tc = T.get("P05_cuna", np.eye(4)); c = (Tc[:3, :3] @ (c * 1000) + Tc[:3, 3]) / 1000
        M += g / 1000; S += g / 1000 * c
    return M, S / M


def apoyo(piezas):
    v = piezas["P15_base"]["t"].vertices
    y0 = v[:, 1].min()
    pts = v[v[:, 1] < y0 + 0.01][:, [0, 2]]
    return MultiPoint([tuple(p) for p in pts]).convex_hull, y0


def bordes(hull):
    c = np.asarray(hull.exterior.coords)
    return [(c[i], c[i + 1]) for i in range(len(c) - 1) if np.linalg.norm(c[i + 1] - c[i]) > 1]


def margen(hull, p):
    return hull.exterior.distance(Point(p)) * (1 if hull.contains(Point(p)) else -1)


def momento_dinamico(piezas, grupos, eje_o, eje_u, alfa, E):
    """momento (N·m) sobre el punto E (m) de unas piezas que arrancan a girar con aceleración angular alfa (rad/s²)
    alrededor del eje (eje_o, eje_u) [mm, unitario]; parte del reposo (sin centrípeta)"""
    a_vec = np.asarray(eje_u, float) * alfa; Mtot = np.zeros(3)
    for n in grupos:
        p = piezas[n]; r = p["c"] - np.asarray(eje_o) / 1000
        a_cm = np.cross(a_vec, r)
        Mtot += np.cross(p["c"] - E, p["m"] * a_cm)
        # inercia propia respecto al CDG (tensor de trimesh ya es respecto al CDG)
        Mtot += p["I"] @ a_vec
    return Mtot


def estudiar(piezas, hull, y0, titulo, imprimir=True):
    mv = V.MOV
    peor = None
    for psi in (-mv["pitch_max"], 0, mv["pitch_max"]):
        for th in (-mv["yaw_max"], 0, mv["yaw_max"]):
            for Th in (0, 35, mv["parpado_max"]):
                T = V.poses_grupo(psi, th, Th)[0]
                M, c = cdg(piezas, T)
                d = margen(hull, (c[0] * 1000, c[2] * 1000)); h = c[1] * 1000 - y0
                if peor is None or d < peor[0]:
                    peor = (d, h, c, (psi, th, Th), M)
    d, h, c, pose, M = peor
    ang = math.degrees(math.atan2(d, h))
    # dinámico: arranque de parpadeo (párpados opuestos) y sacadas, sobre cada borde
    a_par = W_SERVO / T_ARRANQUE * 60 / 73.1          # rad/s² del párpado (servo → párpado)
    a_mir = math.radians(300) / T_ARRANQUE           # firmware: 300 °/s en sacadas
    sup = ["P03_parpado_sup", "P19_casquete_sup_der", "P20_casquete_sup_izq"]
    inf = ["P04_parpado_inf", "P21_casquete_inf_der", "P22_casquete_inf_izq"]
    globo = ["P01_globo", "P02_pupila", "P17_iris", "C_horn_yaw"]
    cuna = ["P05_cuna", "C_servo_yaw", "C_horn_pitch"] + globo
    res = []
    for E0, E1 in bordes(hull):
        u = np.array([E1[0] - E0[0], 0, E1[1] - E0[1]]); u /= np.linalg.norm(u)
        E = np.array([E0[0], y0, E0[1]]) / 1000
        # brazo del peso respecto a este borde (distancia horizontal del CDG al borde)
        n_out = np.cross(u, [0, 1, 0])                  # normal horizontal
        dist = abs(np.dot(c - E, n_out)) * 1000
        Mpeso = M * G * dist / 1000
        casos = {}
        for s in (1, -1):
            casos.setdefault("parpadeo", []).append(abs(np.dot(
                momento_dinamico(piezas, sup, (0, 0, 0), (-1, 0, 0), s * a_par, E)
                + momento_dinamico(piezas, inf, (0, 0, 0), (1, 0, 0), s * a_par, E), u)))
            casos.setdefault("sacada yaw", []).append(abs(np.dot(momento_dinamico(piezas, globo, (0, 0, 0), (0, 1, 0), s * a_mir, E), u)))
            casos.setdefault("sacada pitch", []).append(abs(np.dot(momento_dinamico(piezas, cuna, (0, 0, 0), (-1, 0, 0), s * a_mir, E), u)))
        res.append((dist, Mpeso, {k: max(v) for k, v in casos.items()}))
    if imprimir:
        print(f"\n== {titulo}")
        print(f"masa total {M * 1000:.0f} g · CDG peor caso (x {c[0] * 1000:.1f}, y {c[1] * 1000:.1f}, z {c[2] * 1000:.1f}) mm "
              f"en pose (pitch {pose[0]:+.0f}, yaw {pose[1]:+.0f}, Θ {pose[2]:.0f}) · altura sobre la mesa {h:.0f} mm")
        print(f"distancia del CDG al borde de apoyo más cercano: {d:.1f} mm → ángulo de vuelco {ang:.1f}°")
        for dist, Mp, cs in res:
            peor_din = max(cs.values())
            print(f"   borde a {dist:5.1f} mm: peso {Mp * 1000:6.1f} N·mm · " + " · ".join(f"{k} {v * 1000:5.1f}" for k, v in cs.items())
                  + f" N·mm → reserva ×{Mp / peor_din:.1f}")
    return {"M": M, "c": c, "d": d, "h": h, "ang": ang, "pose": pose, "dyn": res}


def resumen_masas(piezas):
    print("masas (g):")
    cab = sum(p["m"] for n, p in piezas.items() if n not in ("P15_base", "C_tubo_alu")) * 1000 + sum(e[0] for e in EXTRA[:-1])
    for n, p in sorted(piezas.items(), key=lambda kv: -kv[1]["m"]):
        print(f"  {n:24s} {p['m'] * 1000:6.1f}   CDG ({p['c'][0] * 1000:6.1f}, {p['c'][1] * 1000:7.1f}, {p['c'][2] * 1000:6.1f})")
    for g, pt, grupo, txt in EXTRA:
        print(f"  {txt:42s} {g:5.1f}")
    print(f"  cabeza (sin poste ni base): {cab:.0f} g")


def region_cdg(piezas, y0):
    """centros de gravedad (X, Z) en las 27 poses extremas y altura máxima sobre la mesa"""
    mv = V.MOV; C = []
    for psi in (-mv["pitch_max"], 0, mv["pitch_max"]):
        for th in (-mv["yaw_max"], 0, mv["yaw_max"]):
            for Th in (0, 35, mv["parpado_max"]):
                C.append(cdg(piezas, V.poses_grupo(psi, th, Th)[0])[1] * 1000)
    C = np.array(C)
    return C[:, [0, 2]], C[:, 1].max() - y0


def disenar(piezas, y0, vuelco):
    """Patas de la base en X a partir de la carga: cada borde del apoyo (delante, detrás y los dos laterales) es
    tangente a la región del CDG agrandada en m = h·tan(vuelco) (menos el radio de la punta); las puntas son las
    esquinas. El ángulo de los laterales se elige para que la suma de las 4 patas sea mínima.
    Devuelve {'delanteras': {ang, L}, 'traseras': {ang, L}} (ang desde +Z hacia +X, L hasta el centro de la punta)."""
    K = V.P["base"]; rt = K["ancho_pata_punta"] / 2
    H = np.array([V.P["marco"]["poste_x"], V.P["marco"]["poste_z"]])
    Pp, h = region_cdg(piezas, y0)
    m = h * math.tan(math.radians(vuelco))
    def recta(a):
        n = np.array([math.sin(math.radians(a)), math.cos(math.radians(a))])
        return n, (Pp @ n).max() + m - rt
    corte = lambda A, B: np.linalg.solve(np.array([A[0], B[0]]), [A[1], B[1]])
    mejor = None
    for g in np.arange(60, 179.9, 0.1):
        fd = corte(recta(0), recta(g)); bd = corte(recta(180), recta(g))
        vf, vb = fd - H, bd - H
        Lf, Lb = np.linalg.norm(vf), np.linalg.norm(vb)
        if Lb < K["ancho_pata_raiz"] + 10:
            continue
        if mejor is None or Lf + Lb < mejor[0]:
            mejor = (Lf + Lb, g, Lf, math.degrees(math.atan2(vf[0], vf[1])), Lb, math.degrees(math.atan2(vb[0], vb[1])))
    _, g, Lf, af, Lb, ab = mejor
    return {"vuelco_deg": vuelco, "margen_mm": round(m, 1), "altura_cdg_mm": round(h, 1),
            "delanteras": {"ang": round(af, 1), "L": round(Lf, 1)}, "traseras": {"ang": round(ab, 1), "L": round(Lb, 1)}}


if __name__ == "__main__":
    piezas = cargar()
    if "--disenar" in sys.argv:
        import json
        vuelco = float(sys.argv[sys.argv.index("--disenar") + 1])
        hull, y0 = apoyo(piezas)
        d = disenar(piezas, y0, vuelco)
        ruta = os.path.join(RAIZ, "parametros", "ojo.json"); J = json.load(open(ruta))
        J["base"]["patas"].update(d)
        open(ruta, "w").write(json.dumps(J, indent=2, ensure_ascii=False) + "\n")
        print("patas calculadas →", json.dumps(d, ensure_ascii=False))
        sys.exit(0)
    resumen_masas(piezas)
    hull, y0 = apoyo(piezas)
    print(f"apoyo: {hull.area / 100:.0f} cm², y = {y0:.1f}; eje del tubo en (x {V.P['marco']['poste_x']}, z {V.P['marco']['poste_z']})")
    estudiar(piezas, hull, y0, "BASE ACTUAL")
