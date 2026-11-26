"""Barrido de interferencias con los STL reales de cad/stl (coordenadas de montaje).

Grupos móviles:
  cuna   (pitch ψ alrededor de X por O):           P05, C_servo_yaw, C_horn_pitch
  globo  (pitch ψ y luego yaw θ sobre Y de la cuna): P01, P02, C_horn_yaw
  párpado sup  Rx(-Θ)   párpado inf  Rx(+Θ)
  engranajes y bielas según la cinemática del cuadrilátero (resuelta con opt_parpadeo_v2.py)

Uso: .venv/bin/python herramientas/verificar.py [--rapido]
"""
import itertools, json, math, os, sys
import numpy as np, trimesh, manifold3d as mf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piezas2 import P, L, B, parpadeo_puntos
import opt_parpadeo_v2 as OPT
from sc import RAIZ

STL = os.path.join(RAIZ, "cad", "stl")
MOV = P["movimiento"]
UMBRAL = 0.01  # mm³: cualquier solape real cuenta

# pares que se tocan por diseño (uniones fijas o pasadores)
CONTACTO = {frozenset(p) for p in [
    ("P01_globo", "P02_pupila"), ("P01_globo", "C_horn_yaw"), ("P05_cuna", "C_servo_yaw"),
    ("P05_cuna", "C_horn_pitch"), ("P07_horquilla_der", "C_servo_pitch"), ("P09_brazo_der", "C_servo_parpadeo"),
    ("P11_balancin", "C_horn_parpadeo"), ("P08_travesano", "C_perfil_2020"), ("P15_base", "C_perfil_2020"),
    ("P08_travesano", "P16_soporte_servo"), ("P16_soporte_servo", "C_servo_parpadeo"),
    ("P02_pupila", "P17_iris"), ("P01_globo", "P17_iris"),
    ("P03_parpado_sup", "P19_casquete_sup_der"), ("P03_parpado_sup", "P20_casquete_sup_izq"),
    ("P04_parpado_inf", "P21_casquete_inf_der"), ("P04_parpado_inf", "P22_casquete_inf_izq"),
    ("P08_travesano", "C_tubo_alu"), ("P15_base", "C_tubo_alu"),
    ("P08_travesano", "P06_horquilla_izq"), ("P08_travesano", "P07_horquilla_der"),
    ("P08_travesano", "P09_brazo_der"), ("P08_travesano", "P10_brazo_izq"),
    ("C_servo_yaw", "C_horn_yaw"), ("C_servo_pitch", "C_horn_pitch"), ("C_servo_parpadeo", "C_horn_parpadeo"),
]}


def cargar():
    m = {}
    for f in sorted(os.listdir(STL)):
        if f.endswith(".stl") and not f.startswith("P99"):   # la probeta no es del montaje
            t = trimesh.load(os.path.join(STL, f), force="mesh")
            t.merge_vertices(digits_vertex=4)
            M = mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, np.float32), tri_verts=np.asarray(t.faces, np.uint32)))
            if M.status() != mf.Error.NoError or M.volume() <= 0:
                print(f"AVISO: {f} no es un sólido cerrado ({M.status()}); se omite")
                continue
            m[f[:-4]] = t
    return m


def a_manifold(t, T):
    v = (np.c_[t.vertices, np.ones(len(t.vertices))] @ T.T)[:, :3]
    mesh = mf.Mesh(vert_properties=np.asarray(v, dtype=np.float32), tri_verts=np.asarray(t.faces, dtype=np.uint32))
    return mf.Manifold(mesh)


def rot(eje, ang_deg, centro=(0, 0, 0)):
    a = math.radians(ang_deg); c, s = math.cos(a), math.sin(a)
    if eje == "X":
        R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    elif eje == "Y":
        R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    else:
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    T = np.eye(4); T[:3, :3] = R
    ctr = np.array(centro, float); T[:3, 3] = ctr - R @ ctr
    return T


def alfa(deg):  # giro que AUMENTA α (desde +Z hacia +Y) = giro negativo sobre +X
    return -deg


_X_OPT = None


def parpadeo_v2(Theta):
    """Párpado sup abierto Θ → (γ servo en grados [α], Θ párpado inf real, T biela sup, T biela inf)."""
    global _X_OPT
    r = math.radians
    if _X_OPT is None:
        _X_OPT = [*B["H"], B["horn_sup"][0], r(B["horn_sup"][1]), B["horn_inf"][0], r(B["horn_inf"][1]),
                  B["palanca_sup"][0], r(B["palanca_sup"][1]), B["palanca_inf"][0], r(B["palanca_inf"][1])]
    yh, zh, ru, bu, rd, bd, rl, a0, rl2, a2 = _X_OPT
    sim = OPT.simular(_X_OPT)
    k = Theta / MOV["parpado_max"] * (OPT.N - 1)
    i0 = int(math.floor(k)); i1 = min(i0 + 1, OPT.N - 1); f = k - i0
    g = sim["gam"][i0] * (1 - f) + sim["gam"][i1] * f
    ti = sim["thi"][i0] * (1 - f) + sim["thi"][i1] * f
    H = np.array([yh, zh])
    Pu0, Pd0, Cu0, Cd0, _ = [np.array(v) for v in parpadeo_puntos()]
    Pu = OPT.P(rl, a0 + math.radians(Theta)); Cu = H + OPT.P(ru, bu + g)
    Pd = OPT.P(rl2, a2 - ti); Cd = H + OPT.P(rd, bd + g)

    def rigido(p0, c0, p1, c1):
        v0 = c0 - p0; v1 = c1 - p1
        ang = math.atan2(v1[0], v1[1]) - math.atan2(v0[0], v0[1])
        T = rot("X", alfa(math.degrees(ang)))
        T[1:3, 3] = p1 - T[1:3, 1:3] @ p0
        return T
    return math.degrees(g), math.degrees(ti), rigido(Pu0, Cu0, Pu, Cu), rigido(Pd0, Cd0, Pd, Cd)


def poses_grupo(psi, theta, Theta):
    Tc = rot("X", alfa(psi))
    Tg = Tc @ rot("Y", theta)
    g, ti, Tbs, Tbi = parpadeo_v2(Theta)
    Tbal = rot("X", alfa(g), (0, B["H"][0], B["H"][1]))
    return {
        "P05_cuna": Tc, "C_servo_yaw": Tc, "C_horn_pitch": Tc,
        "P01_globo": Tg, "P02_pupila": Tg, "P17_iris": Tg, "C_horn_yaw": Tg,
        "P03_parpado_sup": rot("X", alfa(Theta)), "P04_parpado_inf": rot("X", alfa(-ti)),
        "P19_casquete_sup_der": rot("X", alfa(Theta)), "P20_casquete_sup_izq": rot("X", alfa(Theta)),
        "P21_casquete_inf_der": rot("X", alfa(-ti)), "P22_casquete_inf_izq": rot("X", alfa(-ti)),
        "P11_balancin": Tbal, "C_horn_parpadeo": Tbal,
        "P13_biela_sup": Tbs, "P14_biela_inf": Tbi,
    }, g


def main():
    rapido = "--rapido" in sys.argv
    mallas = cargar()
    nombres = list(mallas)
    print("piezas cargadas:", ", ".join(nombres))
    Y, Pm, A = MOV["yaw_max"], MOV["pitch_max"], MOV["parpado_max"]
    yaws = [-Y, -Y / 2, 0, Y / 2, Y] if not rapido else [-Y, 0, Y]
    pits = [-Pm, -Pm / 2, 0, Pm / 2, Pm] if not rapido else [-Pm, 0, Pm]
    lids = [0, 15, 30, 45, A] if not rapido else [0, A]
    fijos_cache = {}
    choques = {}
    n = 0
    for psi, th, Th in itertools.product(pits, yaws, lids):
        Ts, dphi = poses_grupo(psi, th, Th)
        man = {}
        for k in nombres:
            T = Ts.get(k, np.eye(4))
            if k not in Ts:
                if k not in fijos_cache:
                    fijos_cache[k] = a_manifold(mallas[k], T)
                man[k] = fijos_cache[k]
            else:
                man[k] = a_manifold(mallas[k], T)
        for a, b in itertools.combinations(nombres, 2):
            if frozenset((a, b)) in CONTACTO:
                continue
            if a not in Ts and b not in Ts:
                if n > 0:
                    continue  # fijo-fijo: solo una vez
            ba, bb = man[a].bounding_box(), man[b].bounding_box()
            if any(ba[i + 3] < bb[i] or bb[i + 3] < ba[i] for i in range(3)):
                continue
            vol = (man[a] ^ man[b]).volume()
            if vol > UMBRAL:
                key = (a, b)
                c = choques.setdefault(key, {"vol_max": 0, "poses": []})
                c["vol_max"] = max(c["vol_max"], vol)
                c["poses"].append((psi, th, Th))
        n += 1
    print(f"\n{n} poses comprobadas (pitch×yaw×párpado). Servo de parpadeo: γ a {A}° = {poses_grupo(0,0,A)[1]:.1f}°, párpado inf real = {parpadeo_v2(A)[1]:.2f}°")
    if not choques:
        print("SIN INTERFERENCIAS")
    for (a, b), c in sorted(choques.items(), key=lambda kv: -kv[1]["vol_max"]):
        ej = c["poses"][:4]
        print(f"CHOQUE {a} × {b}: vol máx {c['vol_max']:.1f} mm³ en {len(c['poses'])} poses, p.ej. (ψ,θ,Θ)={ej}")
    json.dump({f"{a}|{b}": c for (a, b), c in choques.items()},
              open(os.path.join(RAIZ, "cad", "interferencias.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
