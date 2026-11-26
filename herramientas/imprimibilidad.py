"""Imprimibilidad FDM de cada pieza en su orientación real en la cama (laminado como un slicer).

Para cada pieza: la gira a su orientación de impresión (parametros/ojo.json → "impresion"; "arriba" es un eje
"+X"… o un vector), la apoya en z=0, la lamina en capas de 0,2 mm y, capa a capa, compara con la de debajo:

  - voladizo: lo que sobresale de la capa inferior más de h·tan(ángulo) (45° por defecto). Se suma como área
    proyectada (mm²) y se mide su alcance d (distancia al apoyo).
  - lo que sobresale más de 1 mm se clasifica con un rayo desde el punto alejándose del apoyo:
      · puente: el rayo vuelve a encontrar apoyo → luz = distancia entre apoyos (≤ luz_puente_max)
      · ménsula / isla: el rayo sale por un borde libre → necesita soporte si d > 2 mm
  - paredes finas: partes de la capa más estrechas que 2 líneas (0,8 mm) y que 1 línea (0,4 mm).
  - primera capa: área, si cabe en la cama, centro de masas sobre la huella y esbeltez (alto / ancho de huella).
  - agujeros de precisión (B-rep del STEP): los horizontales salen ovalados; los que nacen en la cama sufren
    pata de elefante (conviene chaflán de 0,4 mm o compensación en el slicer).

Sale con error (1) si alguna pieza marcada sin soportes los necesita.

  .venv/bin/python herramientas/imprimibilidad.py [pieza ...] [--png carpeta]
"""
import json, math, os, sys
from functools import reduce
import numpy as np, trimesh, shapely
from shapely.geometry import MultiLineString, Polygon, Point, LineString

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(RAIZ, "parametros", "ojo.json")))
CFG = P.get("impresion", {})
ANG = CFG.get("_angulo_max", 45.0)
LUZ = CFG.get("_luz_puente_max", 30.0)
CAMA = CFG.get("_cama", [220, 220, 250])
H = CFG.get("_capa", 0.2)
LINEA = CFG.get("_linea", 0.4)
D_OK, D_MENSULA = 1.0, 2.0        # alcance sin problema / máximo de ménsula sin soporte (mm)
EJES = {"+X": [1, 0, 0], "-X": [-1, 0, 0], "+Y": [0, 1, 0], "-Y": [0, -1, 0], "+Z": [0, 0, 1], "-Z": [0, 0, -1]}


def vector_arriba(arriba):
    v = np.array(EJES[arriba] if isinstance(arriba, str) else arriba, float)
    return v / np.linalg.norm(v)


def matriz_impresion(t, arriba, giro=0.0):
    """Transformación pieza → cama (arriba → +Z, girada `giro`° sobre la vertical, apoyada en z=0, centrada en XY)."""
    R = trimesh.geometry.align_vectors(vector_arriba(arriba), [0, 0, 1])
    if giro:
        R = trimesh.transformations.rotation_matrix(math.radians(giro), [0, 0, 1]) @ R
    b = trimesh.transform_points(t.vertices, R)
    lo, hi = b.min(0), b.max(0)
    T = np.eye(4); T[:3, 3] = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]]
    return T @ R


def cargar(nombre, arriba, giro=0.0):
    t = trimesh.load(os.path.join(RAIZ, "cad", "stl", f"{nombre}.stl"), force="mesh")
    t.merge_vertices()
    M = matriz_impresion(t, arriba, giro)
    t.apply_transform(M)
    return t, M


def laminar(t, h=H):
    zs = np.arange(h / 2, t.bounds[1][2], h)
    segs, _, _ = trimesh.intersections.mesh_multiplane(t, [0, 0, 0], [0, 0, 1], zs)
    return zs, [_capa(sg) for sg in segs]


def _capa(sg):
    if len(sg) == 0:
        return Polygon()
    ml = shapely.line_merge(MultiLineString(list(np.round(sg, 5))))
    gs = getattr(ml, "geoms", [ml])
    anillos = [shapely.make_valid(Polygon(g.coords)) for g in gs if g.is_closed and len(g.coords) > 3]   # mallas finas: autointersecciones µm
    capa = reduce(lambda a, b: a.symmetric_difference(b), anillos, Polygon())
    return shapely.make_valid(capa).buffer(0)


def puntos_dentro(g, paso):
    x0, y0, x1, y1 = g.bounds
    xs, ys = np.meshgrid(np.arange(x0 + paso / 2, x1, paso), np.arange(y0 + paso / 2, y1, paso))
    pts = shapely.points(xs.ravel(), ys.ravel())
    dentro = pts[shapely.contains(g, pts)]
    if len(dentro) == 0:
        dentro = np.array([g.representative_point()])
    return dentro


def _tramo(p, u, region):
    """Segmento de la recta por p con dirección u que queda dentro de la región y contiene p."""
    L = LUZ + 5
    recta = LineString([(p.x - u[0] * L, p.y - u[1] * L), (p.x + u[0] * L, p.y + u[1] * L)])
    dentro = recta.intersection(region.buffer(0.01))
    for g in getattr(dentro, "geoms", [dentro]):
        if g.geom_type == "LineString" and g.distance(p) < 0.05:
            c = list(g.coords)
            return Point(c[0]), Point(c[-1])
    return None


def puentes(pts, apoyo, region, delta):
    """Como un slicer: busca la dirección de puente en la que más puntos tienen apoyo en los dos extremos.
    Devuelve (luz máxima de los puntos puenteados, puntos sin puentear)."""
    mejor = (-1, 0.0, pts)
    for ang in range(0, 180, 10):
        u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
        ok, luz, malos = 0, 0.0, []
        for p in pts:
            tr = _tramo(p, u, region)
            if tr and all(e.distance(apoyo) <= delta + 0.15 for e in tr):
                ok += 1; luz = max(luz, tr[0].distance(tr[1]))
            else:
                malos.append(p)
        if ok > mejor[0] or (ok == mejor[0] and luz < mejor[1]):
            mejor = (ok, luz, malos)
    return mejor[1], mejor[2]


def analizar(nombre, c):
    ang = c.get("angulo_max", ANG)
    t, M = cargar(nombre, c["arriba"], c.get("giro", 0.0))
    zs, capas = laminar(t)
    # soportes integrados (bandejas.py): sostienen la capa que queda 1 hueco por encima, como un soporte del slicer
    try:
        from bandejas import soporte
        sp = soporte(nombre)
    except ImportError:
        sp = None
    sop = [Polygon()] * len(capas)
    if sp is not None:
        sp.apply_transform(M)
        segs, _, _ = trimesh.intersections.mesh_multiplane(sp, [0, 0, 0], [0, 0, 1], zs)
        sop = [_capa(sg) for sg in segs]
    delta = H * math.tan(math.radians(ang))
    r = dict(pieza=nombre, alto=float(t.bounds[1][2]), voladizo=0.0, mensula=0.0, puente=0.0, islas=0,
             fino04=0.0, fino08=0.0, problemas=[])
    for k in range(1, len(capas)):
        L, S = capas[k], capas[k - 1]
        if k >= 2 and not sop[k - 2].is_empty:
            S = S.union(sop[k - 2])
        if L.is_empty:
            continue
        U = L.difference(S.buffer(delta, 8))
        for g in getattr(U, "geoms", [U]):
            if g.area < 0.02:
                continue
            r["voladizo"] += g.area
            gi = g.buffer(-0.25)   # los bordes del propio voladizo no cuentan (el slicer prolonga las líneas)
            pts = puntos_dentro(gi if gi.area > 0.05 else g, max(0.2, math.sqrt(g.area) / 25))
            if S.is_empty:
                r["islas"] += 1; r["problemas"].append(("isla", zs[k], g.centroid.x, g.centroid.y, 0.0)); continue
            d = shapely.distance(pts, S)
            lejos = pts[d > D_OK]
            if len(lejos) == 0:
                continue
            if len(lejos) > 60:
                lejos = lejos[np.linspace(0, len(lejos) - 1, 60).astype(int)]
            luz, malos = puentes(lejos, S, g, delta)
            if luz > r["puente"]:
                r["puente"] = luz
            if luz > LUZ:
                r["problemas"].append(("puente largo", zs[k], g.centroid.x, g.centroid.y, luz))
            if malos:
                dm = shapely.distance(np.array(malos), S); i = int(np.argmax(dm))
                if dm[i] > r["mensula"]:
                    r["mensula"] = float(dm[i])
                if dm[i] > D_MENSULA:
                    r["problemas"].append(("ménsula", zs[k], malos[i].x, malos[i].y, float(dm[i])))
        # paredes finas
        for w, clave in ((LINEA / 2, "fino04"), (LINEA, "fino08")):
            resto = L.difference(L.buffer(-w, 8).buffer(w, 8))
            a = sum(g.area for g in getattr(resto, "geoms", [resto]) if g.area > 1.0) if k < len(capas) - 1 else 0.0
            r[clave] += a * H
    # primera capa y estabilidad
    base = capas[0]
    r["huella"] = base.area
    rect = base.minimum_rotated_rectangle if not base.is_empty else Polygon()
    if not rect.is_empty:
        xy = np.array(rect.exterior.coords)[:4]
        lados = sorted({round(float(np.linalg.norm(xy[i] - xy[(i + 1) % 4])), 1) for i in range(4)})
        r["huella_ancho"] = lados[0]
    else:
        r["huella_ancho"] = 0.0
    todo = shapely.union_all([g for g in capas if not g.is_empty]).convex_hull.minimum_rotated_rectangle
    xy = np.array(todo.exterior.coords)[:4]
    lados = sorted(float(np.linalg.norm(xy[i] - xy[(i + 1) % 4])) for i in range(2))
    r["cama"] = (round(lados[1]), round(lados[0]), round(r["alto"]))
    r["cabe"] = lados[1] <= max(CAMA[:2]) and lados[0] <= min(CAMA[:2]) and r["alto"] <= CAMA[2]
    cm = t.center_mass
    r["cdm_dentro"] = bool(base.convex_hull.buffer(0.01).contains(Point(cm[0], cm[1])))
    r["esbeltez"] = r["alto"] / max(r["huella_ancho"], 1e-3)
    r["M"] = M
    return r


# ---------- agujeros de precisión (B-rep) ----------
PRECISION = {9.1: "rodamiento 684", 4.0: "inserto M3", 3.95: "pasador Ø4 a presión", 2.95: "pasador Ø3 a presión",
             10.1: "rodamiento 623", 5.2: "paso de eje Ø4", 5.4: "paso de eje Ø4"}


def agujeros(nombre, M):
    """Agujeros cilíndricos de diámetros de ajuste: eje respecto a la vertical de impresión y si nacen en la cama."""
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    path = os.path.join(RAIZ, "cad", "step", f"{nombre}.step")
    if not os.path.exists(path):
        return []
    rd = STEPControl_Reader(); rd.ReadFile(path); rd.TransferRoots(); sh = rd.OneShape()
    R = M[:3, :3]; res = {}
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current()); ex.Next()
        s = BRepAdaptor_Surface(f)
        if s.GetType() != GeomAbs_Cylinder or f.Orientation() != TopAbs_REVERSED:
            continue
        cyl = s.Cylinder(); dmt = round(2 * cyl.Radius(), 2)
        if s.LastUParameter() - s.FirstUParameter() < 2 * math.pi - 0.2:
            continue      # arco parcial: lágrima o agujero ya abierto (no sale ovalado)
        tipo = next((v for k, v in PRECISION.items() if abs(k - dmt) < 0.03), None)
        if tipo is None:
            continue
        ax = cyl.Axis().Direction(); a = R @ np.array([ax.X(), ax.Y(), ax.Z()])
        horiz = abs(a[2]) < math.cos(math.radians(45))
        bb = Bnd_Box(); BRepBndLib.Add_s(f, bb); x0, y0, z0 = bb.CornerMin().Coord(); x1, y1, z1 = bb.CornerMax().Coord()
        zmin = min((M @ np.array([x, y, z, 1.0]))[2] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1))
        o = cyl.Location(); clave = (tipo, dmt, horiz, round(float(a[0] * o.X() + a[1] * o.Y() + a[2] * o.Z()) if horiz else 0))
        res.setdefault(clave, []).append(zmin)
    out = []
    for (tipo, dmt, horiz, _), zz in res.items():
        out.append(dict(tipo=tipo, D=dmt, horizontal=horiz, en_cama=(not horiz) and min(zz) < 0.15))
    # agrupa por tipo/orientación
    g = {}
    for a in out:
        k = (a["tipo"], a["D"], a["horizontal"], a["en_cama"]); g[k] = g.get(k, 0) + 1
    return [dict(tipo=k[0], D=k[1], horizontal=k[2], en_cama=k[3], n=n) for k, n in g.items()]


def informe(r, c, ags):
    sin_sop = c.get("sin_soportes", True)
    necesita = r["mensula"] > D_MENSULA or r["islas"] > 0 or r["puente"] > LUZ
    avisos = []
    if not r["cabe"]:
        avisos.append(f"NO CABE en {CAMA[0]}×{CAMA[1]}×{CAMA[2]}")
    if r["huella"] < 150:
        avisos.append(f"primera capa pequeña ({r['huella']:.0f} mm²): borde (brim) 5 mm")
    if r["esbeltez"] > 3 and not c.get("esbelta_ok"):
        avisos.append(f"esbelta (alto/ancho de huella {r['esbeltez']:.1f})")
    if not r["cdm_dentro"]:
        avisos.append("centro de masas fuera de la huella")
    if r["fino04"] > 0.5:
        avisos.append(f"zonas < 1 línea ({r['fino04']:.1f} mm³ se pierden)")
    for a in ags:
        if a["horizontal"]:
            avisos.append(f"{a['n']}× Ø{a['D']} {a['tipo']} horizontal (sale ovalado: repasar)")
        elif a["en_cama"]:
            avisos.append(f"{a['n']}× Ø{a['D']} {a['tipo']} nace en la cama (pata de elefante: chaflán 0,4 o compensación)")
    if necesita:
        est = "SOPORTES (previsto)" if not sin_sop else "REVISAR: necesita soportes"
    else:
        est = "OK sin soportes"
    return est, necesita and sin_sop, avisos


if __name__ == "__main__":
    args = sys.argv[1:]; png = None
    if "--png" in args:
        i = args.index("--png"); png = args[i + 1]; del args[i:i + 2]
    nombres = args or [k for k in CFG if not k.startswith("_")]
    fallo = False
    print(f"capa {H} · voladizo > {ANG}° · ménsula sin soporte ≤ {D_MENSULA} mm · puente ≤ {LUZ} mm · cama {CAMA}\n")
    for nm in nombres:
        c = CFG[nm]
        r = analizar(nm, c)
        ags = agujeros(nm, r["M"])
        est, mal, avisos = informe(r, c, ags)
        fallo |= mal
        print(f"{nm:22s} {str(r['cama']):16s} huella {r['huella']:6.0f} mm²  voladizo {r['voladizo']:7.0f} mm²  "
              f"ménsula máx {r['mensula']:4.1f}  puente máx {r['puente']:5.1f}  islas {r['islas']}  → {est}")
        for a in avisos:
            print(f"{'':24s}· {a}")
        for pr in r["problemas"][:6]:
            print(f"{'':24s}! {pr[0]} en z={pr[1]:.1f} ({pr[2]:.1f}, {pr[3]:.1f}) {pr[4]:.1f} mm")
        if png:
            os.makedirs(png, exist_ok=True)
            from render_cama import render
            render(nm, r, os.path.join(png, f"{nm}.png"))
    sys.exit(1 if fallo else 0)
