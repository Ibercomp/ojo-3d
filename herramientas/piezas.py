"""Geometría de todas las piezas del ojo v1.0, en coordenadas de montaje (posición neutra:
mirada al frente, párpados CERRADOS). Lee parametros/ojo.json.

Uso:  .venv/bin/python herramientas/piezas.py [pieza ...]     (sin argumentos: todas)
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sc import Pieza, RAIZ

P = json.load(open(os.path.join(RAIZ, "parametros", "ojo.json")))
G, L, S, C, H, M = (P[k] for k in ("globo", "parpados", "servo", "cuna", "horquilla", "marco"))


def sph_x(R, z):
    return math.sqrt(R * R - z * z)


# ---------------------------------------------------------------- 01 globo
def globo():
    p = Pieza("P01_globo")
    R, t, zc = G["R"], G["espesor"], G["z_corte"]
    Ri = R - t
    p.casquete_z(Ri, R, zc, op="base")
    # nervios superior e inferior (planos YZ, imprimibles con la boca sobre la cama)
    a = G["nervio_ancho_x"] / 2
    hz = G["nervio_ancho_z_cara"] / 2
    for ys, s in ((G["nervio_sup_y"], 1), (G["nervio_inf_y"], -1)):
        y0 = abs(ys)
        cham = zc + hz  # bajada a 45° desde (y0,-hz) hasta la cama z=zc
        zb = zc + 0.4  # 2 capas sobre el borde: evita caras coplanarias (el recorte común rompía el B-rep)
        pts = [(s * y0, hz), (s * y0, -hz), (s * (y0 - (cham + 0.4)), zb), (s * (R + 2), zb), (s * (R + 2), hz)]
        n = p.poligono("YZ", pts, -a, a, op="keep")
        e = p.esfera(Ri + 0.6, op="keep")
        p.c("solid.combine", target=n, tools=[e], operation="intersect")
        p.c("solid.combine", target=p.cuerpo, tools=[n], operation="join")
        # pie bajo el nervio hasta la cama (sin él, el nervio empezaba 0,4 mm en el aire: ménsula de 10-15 mm).
        # Más estrecho que el nervio y separado 0,6 mm de la cáscara: sin caras coplanarias con el canto.
        y_ini = y0 - (cham + 0.4) + 0.2
        y_fin = math.sqrt(Ri ** 2 - zc ** 2 - (a - 0.2) ** 2) - 0.6
        p.caja((-(a - 0.2), a - 0.2), tuple(sorted((s * y_ini, s * y_fin))), (zc, zb + 0.05))
    # todos los vaciados en UNA herramienta (cada booleana sobre la cáscara es un riesgo en 0.30):
    # agujero frontal Ø58 (borde a 65°: cúpula sin soportes), inserto M3 del nervio sup,
    # acceso al tornillo del horn y 2 pilotos M2 en el nervio inf
    ins = P["insertos"]
    h = [p.cil_z(0, R + 2, 0, 0, G["frente_D"] + 2 * G["holgura_pupila"], op="keep"),
         # inserto del nervio sup: horizontal al imprimir → lágrima con el vértice hacia +Z (arriba en la cama)
         p.lagrima("XZ", 0, 0, ins["agujero_D"], G["nervio_sup_y"] - 0.3, G["nervio_sup_y"] + ins["prof"], +1, op="keep"),
         p.rombo("Y", 0, 0, G["acceso_horn_D"] + 1.0, -R - 1, G["nervio_inf_y"] + 0.3, op="keep")]
    for z in (-8.0, 8.0):
        h.append(p.cil_y(G["nervio_inf_y"] + 0.3, G["nervio_inf_y"] - 8, 0, z, G["piloto_M2"], op="keep"))
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    return p


# ---------------------------------------------------------------- 02 pupila / 17 iris (insertos de trasera plana)
def _inserto_frontal(nombre, d_frente, d_pestana, agujero=None, rebaje=None):
    """Casquete R del globo recortado por un cilindro, con trasera plana en z=iris_trasera_z y pestaña
    interior (bajo la cáscara) que lo retiene. Se imprime con la trasera sobre la cama, sin soportes."""
    p = Pieza(nombre)
    R, t = G["R"], G["espesor"]
    zb = G["iris_trasera_z"]
    p.esfera(R, op="base")
    p.caja((-R, R), (-R, R), (zb, R + 1), op="intersect")
    cil = p.cil_z(zb - 1, R + 1, 0, 0, d_frente, op="keep")
    pest = p.cil_z(zb - 1, R + 1, 0, 0, d_pestana, op="keep")
    p.c("solid.combine", target=pest, tools=[p.esfera(R - t, op="keep")], operation="intersect")
    p.c("solid.combine", target=cil, tools=[pest], operation="join")
    p.c("solid.combine", target=p.cuerpo, tools=[cil], operation="intersect")
    if agujero:
        p.cil_z(zb - 1, R + 1, 0, 0, agujero, op="cut")
    if rebaje:
        p.cil_z(zb - 1, zb + rebaje[1], 0, 0, rebaje[0], op="cut")
    return p


def pupila():
    """pupila negra Ø42 que atraviesa el iris, con pestaña Ø46 DETRÁS del iris (sin rebajes ni techos)"""
    p = Pieza("P02_pupila")
    R = G["R"]; zb = G["iris_trasera_z"]
    p.esfera(R, op="base")
    p.caja((-R, R), (-R, R), (zb - 2, R + 1), op="intersect")
    c = p.cil_z(zb - 2.5, R + 1, 0, 0, G["pupila_D"], op="keep")
    f = p.cil_z(zb - 2.5, zb, 0, 0, G["pupila_pestana_D"], op="keep")
    p.c("solid.combine", target=c, tools=[f], operation="join")
    p.c("solid.combine", target=p.cuerpo, tools=[c], operation="intersect")
    return p


def iris():
    """aro blanco Ø58 alrededor de la pupila, con pestaña Ø64 bajo la cáscara del globo"""
    h = G["holgura_pupila"]
    return _inserto_frontal("P17_iris", G["frente_D"], G["iris_pestana_D"], agujero=G["pupila_D"] + 2 * h)


from piezas2 import registrar
PIEZAS = {"P01_globo": globo, "P02_pupila": pupila, "P17_iris": iris}
registrar(PIEZAS)

if __name__ == "__main__":
    nombres = sys.argv[1:] or list(PIEZAS)
    for n in nombres:
        r = PIEZAS[n]().construir()
        print(json.dumps(r, ensure_ascii=False))
