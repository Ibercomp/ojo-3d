"""Piezas del ojo v2 (párpados con rodamientos, cuna, horquillas, marco, parpadeo trasero con
balancín y bielas, base) y envolventes de compra para la comprobación de interferencias."""
import json, math, os
from sc import Pieza, RAIZ, f

P = json.load(open(os.path.join(RAIZ, "parametros", "ojo.json")))
G, L, B, S, C, H, M, I = (P[k] for k in ("globo", "parpados", "parpadeo_v2", "servo", "cuna", "horquilla", "marco", "insertos"))
HOLG = S["holgura"]


def yz(r, a):
    """punto (Y,Z) a radio r y ángulo α (desde +Z hacia +Y)"""
    a = math.radians(a)
    return r * math.sin(a), r * math.cos(a)


# ------------------------------------------------------------------ cinemática parpadeo v2
def parpadeo_puntos():
    """Posición cerrada (Y,Z): pin palanca sup, pin palanca inf, pin balancín sup, pin balancín inf, eje servo."""
    Hc = tuple(B["H"])
    Pu = yz(*B["palanca_sup"]); Pd = yz(*B["palanca_inf"])
    cu = yz(*B["horn_sup"]); cd = yz(*B["horn_inf"])
    Cu = (Hc[0] + cu[0], Hc[1] + cu[1]); Cd = (Hc[0] + cd[0], Hc[1] + cd[1])
    return Pu, Pd, Cu, Cd, Hc


def inserto(p, x0, x1, y, z):
    """agujero para inserto térmico M3 a lo largo de X, desde la cara x0 hacia x1"""
    d = I["prof"] if x1 > x0 else -I["prof"]
    p.cil_x(x0 - (0.3 if d > 0 else -0.3), x0 + d, y, z, I["agujero_D"], op="cut")


# ------------------------------------------------------------------ servo genérico
class ServoPos:
    """Colocación de un servo con ejes alineados. o: punto del eje en la cara superior del cuerpo;
    hv: hacia donde sale el eje; lv: dirección del largo (l crece). Ancho = el eje restante."""
    def __init__(self, o, hv, lv):
        self.o, self.hv, self.lv = o, hv, lv
        self.wv = tuple(int(abs(hv[i]) + abs(lv[i]) == 0) for i in range(3))

    def rangos(self, lr, wr, hr, holg=0.0):
        out = [None, None, None]
        for vec, (a, b) in ((self.lv, lr), (self.wv, wr), (self.hv, hr)):
            i = next(k for k in range(3) if vec[k] != 0)
            v1, v2 = self.o[i] + vec[i] * a, self.o[i] + vec[i] * b
            out[i] = (min(v1, v2) - holg, max(v1, v2) + holg)
        return out

    def cuerpo(self, holg=0.0):
        return self.rangos((S["l_min"], S["l_max"]), (-S["w"] / 2, S["w"] / 2), (-S["h_cuerpo"], 0), holg)

    def pestanas(self, holg=0.0):
        return self.rangos(tuple(S["pestana_l"]), (-S["w"] / 2, S["w"] / 2), tuple(S["pestana_h"]), holg)

    def punto(self, l, w, h):
        return tuple(self.o[i] + self.lv[i] * l + self.wv[i] * w + self.hv[i] * h for i in range(3))

    def eje(self):
        return "XYZ"[next(k for k in range(3) if self.hv[k] != 0)]


SERVO_YAW = ServoPos((0.0, C["servo_yaw_y_top"], 0.0), (0, -1, 0), (0, 0, -1))
SERVO_PITCH = ServoPos((C["servo_pitch_x_top"], 0.0, 0.0), (-1, 0, 0), (0, 0, -1))
X_TOP_PARP = B["x_horn"][0] - S["horn_h"][0]            # servo trasero: eje +X, cuerpo hacia dentro
SERVO_PARP = ServoPos((X_TOP_PARP, B["H"][0], B["H"][1]), (1, 0, 0), (0, 1, 0))


def taladros_pestana(p, sv, d, largo=12.0):
    """pilotos de los tornillos de las pestañas del servo, a lo largo de su eje h"""
    for l in S["agujeros_pestana_l"]:
        a = sv.punto(l, 0, S["pestana_h"][1] + largo / 2)
        b = sv.punto(l, 0, S["pestana_h"][1] - largo)
        i = next(k for k in range(3) if sv.hv[k] != 0)
        base = list(a); base[i] = min(a[i], b[i])
        p.cilindro(base, "XYZ"[i], d, abs(a[i] - b[i]), op="cut")


def envolvente_servo(nombre, sv):
    p = Pieza(nombre)
    p.caja(*sv.cuerpo(), op="base")
    p.caja(*sv.pestanas(), op="join")
    i = next(k for k in range(3) if sv.hv[k] != 0)
    a = sv.punto(0, 0, 0); b = sv.punto(0, 0, S["cupula_h"])
    base = list(a); base[i] = min(a[i], b[i])
    p.cilindro(base, sv.eje(), S["cupula_D"], S["cupula_h"])
    a = sv.punto(0, 0, S["cupula_h"]); b = sv.punto(0, 0, S["horn_h"][0])
    base = list(a); base[i] = min(a[i], b[i])
    p.cilindro(base, sv.eje(), 7.0, abs(b[i] - a[i]))
    return p


def horn(nombre, sv, R=None):
    """disco del horn (pieza de compra) — envolvente r=horn_R"""
    R = R or S["horn_R"]
    p = Pieza(nombre)
    i = next(k for k in range(3) if sv.hv[k] != 0)
    a = sv.punto(0, 0, S["horn_h"][0]); b = sv.punto(0, 0, S["horn_h"][1])
    base = list(a); base[i] = min(a[i], b[i])
    p.cilindro(base, sv.eje(), 2 * R, S["horn_h"][1] - S["horn_h"][0], op="base")
    return p


# ------------------------------------------------------------------ 03/04 párpados (cáscara 1,2 mm hasta el casquete)
CQ = L["casquete"]


def _parpado(nombre, sup):
    """Cáscara de 1,2 mm (3 perímetros). Termina en un corte RADIAL sobre el asiento del casquete polar (canto con
    todo el espesor, sin filo) y se pega encima del asiento. Una sola revolución, sin booleanas."""
    p = Pieza(nombre)
    k = "sup" if sup else "inf"
    Ri, Ro = L[f"{k}_Ri"], L[f"{k}_Ro"]
    th = CQ[k]["th_costura"] + math.degrees(CQ["holgura_canto"] / Ro)
    p.luna_radial(Ri, Ro, *L[f"{k}_sector"], th, op="base")
    return p


def parpado_sup():
    return _parpado("P03_parpado_sup", True)


def parpado_inf():
    return _parpado("P04_parpado_inf", False)


# ------------------------------------------------------------------ 19-22 casquetes polares (opción A)
def _casquete(nombre, sup, s, palanca):
    """Porción polar de la MISMA esfera que el párpado (exterior enrasado) hasta la junta radial th_costura, con
    asiento rebajado bajo el párpado hasta la cara plana x_base, buje con rodamiento 684 y, en el lado de la
    transmisión, saliente de palanca con inserto M3 y chaflán a 45° por debajo.
    Se imprime con la cara plana (X = x_base) en la cama: la junta radial sale casi vertical (sin ménsula)."""
    p = Pieza(nombre)
    xb, hg = CQ["x_base"], CQ["holgura_asiento"]
    r = lambda R, x: math.sqrt(R * R - x * x)
    pol = lambda R, t: (R * math.cos(math.radians(t)), R * math.sin(math.radians(t)))
    ar = L["rodamiento_684"][2]
    X = lambda a_, b_: (s * a_, s * b_)
    K = CQ["sup" if sup else "inf"]; th = K["th_costura"]
    if sup:
        Rs, Ro = L["sup_Ri"] - hg, L["sup_Ro"]
        xt, rh = K["x_tope_buje_inf"], K["R_hueco_buje_inf"]
        re = L["rodamiento_alojamiento_D"] / 2 + 0.05   # el perfil deja libre el alojamiento del rodamiento (sin cortes coaxiales)
        p.casquete_polar([((xb, r(Rs, xb)), pol(Rs, th)), (pol(Ro, th), (r(Ro, re), re))],
                         [["a2.end", (xt, re), (xt, rh), (xb, rh), "a1.start"], ["a1.end", "a2.start"]],
                         *K["sector"], s, op="base")
    else:
        Rs, Ro = L["inf_Ri"] - hg, L["inf_Ro"]; xm = K["x_max"]
        p.casquete_polar([((xb, r(Rs, xb)), pol(Rs, th)), (pol(Ro, th), (xm, r(Ro, xm)))],
                         [["a2.end", (xm, 6.0), (xb, 6.0), "a1.start"], ["a1.end", "a2.start"]],   # hueco R6: lo rellena el anillo del buje
                         *K["sector"], s, op="base")
    # buje: anillo por revolución con el alojamiento del 684 ya hueco (el pasador Ø4 gira en el rodamiento)
    bx0, bx1 = K["buje_x"]; rr = L["rodamiento_alojamiento_D"] / 2
    if sup:   # escalón de tope para el rodamiento: tramo interior Ø5,2 + alojamiento Ø9,1 de 4 mm
        tramos = [(bx0, bx1 - ar - 0.05, L["eje_paso_D"] / 2 + 0.1), (bx1 - ar - 0.05, bx1, rr)]
    else:     # el alojamiento nace en la cama: alivio de pata de elefante en las 2 primeras capas
        e, dr = K["alivio_pata_elefante"]
        tramos = [(bx0, xb + e, rr + dr), (xb + e, bx1, rr)]
    p.oreja_revolucion(tramos, L["buje_R"], 0.0, 360.0, s)
    if palanca:
        rl, al = B["palanca_sup" if sup else "palanca_inf"]; y, z = yz(rl, al)
        x0 = K["palanca_x0"]; x1 = CQ["cara_palanca_sup"] if sup else B["x_biela_inf"][0]
        sal = p.cil_x(*X(x0, x1), y, z, L["saliente_palanca_D"], op="keep")
        # chaflán a 45° por debajo: al imprimir no vuela sobre la zona del párpado (que no está en esta pieza)
        xc, rc = pol(Ro, th); xc += CQ["chaflan_palanca"]["holgura"]
        xa, xz = x0 - 1.0, x1 + 1.0
        cono = p.casquete_polar([], [[(xa, 0.5), (xa, rc + (xa - xc)), (xz, rc + (xz - xc)), (xz, 0.5), (xa, 0.5)]],
                                al - 25.0, al + 25.0, s, op="keep")
        p.c("solid.combine", target=sal, tools=[cono], operation="intersect")
        p.c("solid.combine", target=p.cuerpo, tools=[sal], operation="join")
        p.cil_x(*X(x1 + 0.3, x1 - I["prof"]), y, z, I["agujero_D"], op="cut")
    return p


def casquete_sup_der():
    return _casquete("P19_casquete_sup_der", True, 1, True)


def casquete_sup_izq():
    return _casquete("P20_casquete_sup_izq", True, -1, False)


def casquete_inf_der():
    return _casquete("P21_casquete_inf_der", False, 1, True)


def casquete_inf_izq():
    return _casquete("P22_casquete_inf_izq", False, -1, False)


# ------------------------------------------------------------------ 05 cuna (igual que v1.0 + paso de cable)
def cuna():
    p = Pieza("P05_cuna")
    px0, px1 = C["placa_x"]
    p.caja((-px1, px1), tuple(C["bandeja_y"]), tuple(C["bandeja_z"]), op="base")
    for s in (1, -1):
        p.caja(tuple(sorted((s * px0, s * px1))), (C["y_min"], C["y_max"]), tuple(C["placa_z"]))
    p.caja((-px1, px1), tuple(C["barra_sup_y"]), tuple(C["barra_sup_z"]))
    xr, yr, zr = SERVO_YAW.cuerpo(HOLG)
    p.caja(xr, (C["bandeja_y"][0] - 1, C["bandeja_y"][1] + 1), zr, op="cut")
    taladros_pestana(p, SERVO_YAW, 1.7)
    d_rod, a_rod = C["rodamiento_623"][1], C["rodamiento_623"][2]
    p.cil_y(C["barra_sup_y"][1] - a_rod, C["barra_sup_y"][1] + 1, 0, 0, d_rod + 0.05, op="cut")
    # bajo el 623: Ø8 para que la cabeza del tornillo M3 apriete SOLO el aro interior (gira con el globo); el aro
    # exterior apoya en un escalón de 1 mm. Está en mitad del puente de la barra (imprime +Y arriba): puente
    # escalonado (capa 1 ranura a lo largo del puente, capa 2 cuadrado, luego redondo), ninguna línea acaba en el aire
    b0 = C["barra_sup_y"][0]; r8 = C["paso_cabeza_D"] / 2
    p.cil_y(b0 + 0.35, C["barra_sup_y"][1] - a_rod + 0.05, 0, 0, 2 * r8, op="cut")
    p.caja((-px0 + 0.1, px0 - 0.1), (b0 - 0.5, b0 + 0.2), (-r8, r8), op="cut")
    p.caja((-r8 - 0.05, r8 + 0.05), (b0 - 0.5, b0 + 0.4), (-r8 - 0.05, r8 + 0.05), op="cut")
    p.cil_x(px0 - 1, px1 + 1, 0, 0, 6.0, op="cut")
    for y, z in ((0, 8), (0, -8), (8, 0), (-8, 0)):
        p.cil_x(px0 - 1, px1 + 1, y, z, 1.7, op="cut")
    p.cil_x(-px1 - 1, -px0 + 1, 0, 0, 3.2, op="cut")
    # paso del cable del servo de yaw junto al eje de pitch (placa izquierda, encima del eje)
    p.caja((-px1 - 1, -px0 + 1), (4.0, 9.0), (-4.0, 4.0), op="cut")
    return p


# ------------------------------------------------------------------ 06/07 horquillas (v4: perfil curvo, ventana de aligerado)
def _pie_horquilla(p, xr, x_agujero, x_cara, medio_ancho, r_ext, r_lat):
    """pie atornillado al travesaño: placa de esquinas redondeadas. La pala llega al pie a TODO su ancho (lados
    rectos, sin cuello) y las esquinas interiores de la unión llevan redondeos cóncavos continuos en lugar de una
    cartela: al imprimir crecen capa a capa sin cambios bruscos de sección (más robusto que el triángulo).
    x_cara: cara exterior de la pala (donde arranca la placa); medio_ancho: semiancho de la pala en la raíz."""
    zr = H["z_raiz"]; zc = zr + 6
    # esquinas rectas en el lado de la pala: el redondeo interior apoya en placa a todo su largo
    p.rect_redondeado("XY", xr[0], xr[1], -12, 12, 4.0, zr, zc, recto=("u1" if x_agujero < 0 else "u0"))
    for y in (-M["pie_tornillos_y"], M["pie_tornillos_y"]):
        p.cil_z(zr - 1, zr + 7, x_agujero, y, I["tornillo_paso_D"], op="cut")
    x_med = x_cara + (3.0 if x_agujero < 0 else -3.0)   # mitad del espesor de la pala (6 mm)
    p.c("solid.fillet", edges=[[x_cara, 0, zc]], radius=f"{r_ext} mm")
    p.c("solid.fillet", edges=[[x_med, medio_ancho, zc], [x_med, -medio_ancho, zc]], radius=f"{r_lat} mm")


def perfil_marco():
    """Sección del travesaño en (Y, Z) como círculos para envolvente_circulos: 24×12, aristas traseras R3 y
    delanteras casi vivas (R0,5). Los brazos terminan exactamente en este perfil y los pies de horquillas y
    soporte enrasan con su cara delantera (±12): nada sobresale del marco."""
    yr, zr = M["travesano_y"], M["travesano_z"]
    rt, rd = 3.0, 0.5
    return [(yr[0] + rt, zr[0] + rt, rt), (yr[1] - rt, zr[0] + rt, rt), (yr[1] - rd, zr[1] - rd, rd), (yr[0] + rd, zr[1] - rd, rd)]


X_BRIDA_IZQ = H["izq_x"][0] - 7.0
X_BRIDA_DER = H["der_x"][1] + 7.0
Z_RAIZ_C = H["z_raiz"] + 9.0          # centro del círculo de raíz de la placa (apoya sobre el pie)


def horquilla_izq():
    p = Pieza("P06_horquilla_izq")
    xr = tuple(H["izq_x"])
    # raíz a todo el ancho: dos círculos pequeños DENTRO del pie (lados rectos hasta la placa, sin cuello)
    zr = H["z_raiz"]
    p.envolvente_circulos("YZ", [(0.0, 0.0, 9.5), (-8.0, zr + 4.0, 1.0), (8.0, zr + 4.0, 1.0)], *xr, op="base")
    _pie_horquilla(p, (xr[0] - 14, xr[1]), X_BRIDA_IZQ, xr[0], 9.0, 4.0, 2.5)
    d_rod, a_rod = C["rodamiento_623"][1], C["rodamiento_623"][2]
    sk = p._sketch("YZ", xr[0] - 1)                                     # ventana de aligerado
    p.c("sketch.slot.center_to_center", p0=[0, -18.0], p1=[0, -58.0], width=7.0)
    p.c("sketch.finish")
    v = p._tmp("Ventana")
    p.c("solid.extrude", sketch=sk, distance=f"{xr[1] - xr[0] + 2} mm", operation="new", body_name=v, name=v)
    # tras el 623, Ø8: la cabeza del tornillo M3 (desde fuera) aprieta SOLO el aro interior, que gira con la cuna;
    # el aro exterior apoya en un escalón de 1 mm (al imprimir, ménsula de 1 mm: no necesita puente escalonado)
    xt = xr[1] - a_rod
    h = [v, p.cil_x(xt, xr[1] + 1, 0, 0, d_rod + 0.05, op="keep"), p.cil_x(xr[0] - 1, xt + 0.05, 0, 0, C["paso_cabeza_D"], op="keep")]
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    return p


def horquilla_der():
    p = Pieza("P07_horquilla_der")
    xr = tuple(H["der_x"])
    zr = H["z_raiz"]   # estrecha (±9) donde cruza la boca del globo; raíz a todo el ancho dentro del pie
    p.envolvente_circulos("YZ", [(0.0, -5.4, 15.5), (-6.0, zr + 18.0, 1.0), (-6.0, zr + 4.0, 1.0), (6.0, zr + 4.0, 1.0),
                                 (6.0, zr + 18.0, 1.0)], *xr, op="base")   # últimos 14 mm de raíz con lados paralelos
    _pie_horquilla(p, (xr[0], xr[1] + 14), X_BRIDA_DER, xr[1], 7.0, 4.0, 3.0)
    _, yr, zr = SERVO_PITCH.cuerpo(HOLG)
    h = [p.caja((xr[0] - 1, xr[1] + 1), yr, zr, op="keep")]
    sk = p._sketch("YZ", xr[0] - 1)
    p.c("sketch.slot.center_to_center", p0=[0, -31.0], p1=[0, -58.0], width=6.0)
    p.c("sketch.finish")
    v = p._tmp("Ventana")
    p.c("solid.extrude", sketch=sk, distance=f"{xr[1] - xr[0] + 2} mm", operation="new", body_name=v, name=v)
    h.append(v)
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    taladros_pestana(p, SERVO_PITCH, 1.7)
    return p


# ------------------------------------------------------------------ 08 travesaño (v4: sección redondeada, vaciados, casquillo de tubo)
def travesano():
    p = Pieza("P08_travesano")
    X = M["travesano_x"]; zr = tuple(M["travesano_z"]); yr = tuple(M["travesano_y"])
    # perfil común del marco (24×12): delante a escuadra (apoya en la cama y en ella enrasan los pies), detrás R3
    p.envolvente_circulos("YZ", perfil_marco(), -X, X, op="base")
    # canal de cables por la cara delantera (cama al imprimir: techo en puente de 9 mm), junto a la fibra neutra
    cc = M["canal_cables"]
    p.caja(tuple(cc["x"]), tuple(cc["y"]), (zr[1] - cc["prof"], zr[1] + 0.5), op="cut")
    # el casquillo del tubo (P23) abraza el travesaño por forma; 2 insertos traseros para sus tornillos de refuerzo
    # (en impresión la cara trasera queda ARRIBA: insertos verticales)
    dx = P["poste"]["nudo_tornillos_dx"]
    h = [p.cil_z(zr[0] - 0.5, zr[0] + I["prof"], M["poste_x"] + sx * dx, 0, I["agujero_D"], op="keep") for sx in (-1, 1)]
    # vaciados por detrás entre anclajes (dejan nervios donde hay insertos)
    for xa, xb in ((-84.0, -32.0), (17.0, 33.0), (70.0, 86.0)):
        sk = p._sketch("XY", zr[0] - 0.5)
        p.c("sketch.slot.center_to_center", p0=[xa + 6, 0], p1=[xb - 6, 0], width=12.0)
        p.c("sketch.finish")
        v = p._tmp("Vaciado")
        p.c("solid.extrude", sketch=sk, distance="6.5 mm", operation="new", body_name=v, name=v)
        h.append(v)
    # insertos M3 delanteros (horquillas, soporte) y en los extremos (brazos)
    for x in (X_BRIDA_IZQ, X_BRIDA_DER, X_SOPORTE):
        for y in (-M["pie_tornillos_y"], M["pie_tornillos_y"]):
            h.append(p.cil_z(zr[1] - I["prof"], zr[1] + 0.5, x, y, I["agujero_D"], op="keep"))
    for sx in (1, -1):
        for y in (-6, 6):
            # horizontales al imprimir (arriba es -Z): lágrima con el vértice hacia -Z
            h.append(p.lagrima("YZ", y, (zr[0] + zr[1]) / 2, I["agujero_D"], sx * (X + 0.5), sx * (X - I["prof"]), -1, op="keep"))
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    # los insertos delanteros nacen en la cama: alivio Ø4,6 × 0,4 contra la pata de elefante (y guía el inserto)
    al = [p.cil_z(zr[1] - 0.4, zr[1] + 0.5, x, y, I["agujero_D"] + 0.6, op="keep") for x in (X_BRIDA_IZQ, X_BRIDA_DER, X_SOPORTE) for y in (-M["pie_tornillos_y"], M["pie_tornillos_y"])]
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(al)], operation="cut")
    return p


# ------------------------------------------------------------------ 09/10 brazos laterales (v4: perfil que se afina + ventana)
def _brazo(nombre, s):
    p = Pieza(nombre)
    K = P["brazo"]; px = K["placa_x"]; zr = M["travesano_z"]; zc = (zr[0] + zr[1]) / 2
    X = lambda a_, b_: (s * a_, s * b_)
    p.envolvente_circulos("YZ", [(0.0, 0.0, K["R_pivote"])] + perfil_marco(), *X(*px), op="base")   # raíz = perfil del travesaño
    # espiga del eje: Ø7 en los planos de bielas, collar Ø14 junto al brazo (refuerzo donde trabaja el pasador)
    x_tope = L["x_cara_orejas"] + 0.5
    p.cil_x(*X(x_tope, px[0]), 0, 0, 7.0)
    p.cil_x(*X(B["x_biela_inf"][1] + 0.4, px[0]), 0, 0, 14.0)
    w0, w1, ww = K["ventana"]
    sk = p._sketch("YZ", min(X(*px)) - 0.5)
    p.c("sketch.slot.center_to_center", p0=[0, w0], p1=[0, w1], width=ww)
    p.c("sketch.finish")
    v = p._tmp("Ventana")
    p.c("solid.extrude", sketch=sk, distance=f"{px[1] - px[0] + 1} mm", operation="new", body_name=v, name=v)
    h = [v, p.cil_x(*X(x_tope - 0.5, px[1] + 1), 0, 0, L["eje_D"] - 0.05, op="keep")]
    for y in (-6, 6):
        h.append(p.cil_x(*X(px[0] - 0.5, px[1] + 0.5), y, zc, I["tornillo_paso_D"], op="keep"))
        h.append(p.cil_x(*X(px[1] - 2.5, px[1] + 0.5), y, zc, 6.5, op="keep"))
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    # el agujero del pasador a presión nace en la cama (cara exterior): alivio contra la pata de elefante
    p.cil_x(*X(px[1] - 0.4, px[1] + 0.5), 0, 0, L["eje_D"] + 0.55, op="cut")
    return p


def brazo_der():
    return _brazo("P09_brazo_der", 1)


def brazo_izq():
    return _brazo("P10_brazo_izq", -1)


# ------------------------------------------------------------------ 11 balancín (doble brazo, sobre el horn redondo)
def balancin():
    p = Pieza("P11_balancin")
    Pu, Pd, Cu, Cd, Hc = parpadeo_puntos()
    xb = B["x_balancin"]
    # contorno con ARCOS verdaderos: disco central + dos brazos en ranura (sin polígonos facetados)
    p.cil_x(xb[0], xb[1], Hc[0], Hc[1], 16.0, op="base")
    for c in (Cu, Cd):
        sk = p._sketch("YZ", xb[0])
        p.c("sketch.slot.center_to_center", p0=[round(Hc[0], 4), round(Hc[1], 4)], p1=[round(c[0], 4), round(c[1], 4)], width=10.0)
        p.c("sketch.finish")
        b = p._tmp("Brazo")
        p.c("solid.extrude", sketch=sk, distance=f"{round(xb[1] - xb[0], 4)} mm", operation="new", body_name=b, name=b)
        p.c("solid.combine", target=p.cuerpo, tools=[b], operation="join")
    # saliente hacia dentro hasta la biela superior, con inserto (tornillo desde el plano A)
    p.cil_x(B["x_biela_sup"][1], xb[0], Cu[0], Cu[1], B["saliente_balancin_D"])
    p.cil_x(B["x_biela_sup"][1] - 0.5, xb[1] + 0.5, Cu[0], Cu[1], I["agujero_D"], op="cut")
    p.cil_x(xb[1] - 0.4, xb[1] + 0.5, Cu[0], Cu[1], I["agujero_D"] + 0.6, op="cut")   # alivio en la cama
    # pasador inferior: M3 pasante (cabeza en el plano del horn, fuera del disco), tuerca nyloc fuera de la biela
    p.cil_x(xb[0] - 0.5, xb[1] + 0.5, Cd[0], Cd[1], 3.2, op="cut")
    # acceso al tornillo central del horn y 4 pilotos M2 de fijación al horn redondo
    p.cil_x(xb[0] - 0.5, xb[1] + 0.5, Hc[0], Hc[1], 6.0, op="cut")
    for k in range(4):
        y, z = yz(B["horn_agujeros_r"], 45 + 90 * k)
        p.cil_x(xb[0] - 0.5, xb[1] + 0.5, Hc[0] + y, Hc[1] + z, 1.7, op="cut")
    return p


# ------------------------------------------------------------------ 13/14 bielas
def _biela(nombre, a, b, xr):
    p = Pieza(nombre)
    w = B["biela_ancho"]
    sk = p._sketch("YZ", xr[0])
    p.c("sketch.slot.center_to_center", p0=[round(a[0], 4), round(a[1], 4)], p1=[round(b[0], 4), round(b[1], 4)], width=w)
    for q in (a, b):
        p.c("sketch.circle.center", center=[round(q[0], 4), round(q[1], 4)], radius=B["pasador_agujero_D"] / 2)
    p.c("sketch.finish")
    p.c("solid.extrude", sketch=sk, distance=f"{round(xr[1] - xr[0], 4)} mm", operation="new", body_name=nombre, name=nombre)
    p.cuerpo = nombre
    return p


def biela_sup():
    Pu, Pd, Cu, Cd, Hc = parpadeo_puntos()
    return _biela("P13_biela_sup", Pu, Cu, B["x_biela_sup"])


def biela_inf():
    Pu, Pd, Cu, Cd, Hc = parpadeo_puntos()
    return _biela("P14_biela_inf", Pd, Cd, B["x_biela_inf"])


# ------------------------------------------------------------------ 16 soporte del servo de parpadeo (v4: contorno envolvente)
X_SOPORTE = B["soporte_servo_x"][0] - 6.0


def soporte_servo():
    p = Pieza("P16_soporte_servo")
    xs = B["soporte_servo_x"]; zt = M["travesano_z"][1]
    Hy, Hz = B["H"]
    l0, l1 = S["agujeros_pestana_l"]
    # raíz DENTRO del pie (y ±8, lados rectos) para no sobresalir del travesaño; redondeos interiores, sin cartela
    p.envolvente_circulos("YZ", [(Hy + l0, Hz, 7.5), (Hy + l1, Hz, 7.5), (7.0, zt + 4.0, 1.0), (-7.0, zt + 4.0, 1.0)],
                          *xs, op="base")
    p.rect_redondeado("XY", X_SOPORTE - 5, xs[1], -12, 12, 4.0, zt, zt + 6, recto="u1")
    p.c("solid.fillet", edges=[[xs[0], 0, zt + 6]], radius="4 mm")
    _, yb, zb = SERVO_PARP.cuerpo(HOLG)
    h = [p.caja((xs[0] - 1, xs[1] + 1), yb, zb, op="keep")]
    for y in (-M["pie_tornillos_y"], M["pie_tornillos_y"]):
        h.append(p.cil_z(zt - 1, zt + 7, X_SOPORTE, y, I["tornillo_paso_D"], op="keep"))
    p.c("solid.combine", target=p.cuerpo, tools=[p.unir_herramientas(h)], operation="cut")
    taladros_pestana(p, SERVO_PARP, 1.7)
    return p


# ------------------------------------------------------------------ 15 base (v4: trípode que abraza un tubo de aluminio)
T_ = P["poste"]
Y_TUBO_SUP = M["travesano_y"][0] - T_["tope_sobre_tubo"]
Y_TUBO_INF = Y_TUBO_SUP - T_["L"]
Y_BASE = Y_TUBO_INF - (P["base"]["camara_cables"]["suelo"] + P["base"]["camara_cables"]["alto"])   # cámara de cables bajo el tubo


def base():
    """Base en X, toda en SolidCraft. Buje que abraza el tubo y 4 patas por SOLEVADO (solid.loft) entre dos secciones
    perpendiculares a la pata: cuña de alto_pata_raiz → alto_pata_punta y de ancho_pata_raiz → ancho_pata_punta, con
    las aristas superiores redondeadas EN LA SECCIÓN (el núcleo 0.30 solo redondea aristas rectas). Puntas rectas: el
    redondeo de sus esquinas verticales deja una malla con grietas en las traseras. La unión con el buje queda viva.
    Ángulos y longitudes CALCULADOS por herramientas/estabilidad.py --disenar <vuelco>: cada borde del apoyo es tangente
    a la región del centro de gravedad (todas las poses) agrandada en altura·tan(vuelco). El peso cae por delante del
    tubo: delanteras largas, traseras cortas y casi laterales. Cada pata se construye en su sitio (planos de boceto
    orientados), sin mover cuerpos. El tubo apoya en un escalón; debajo, cámara de cables con salida por la PARED DEL
    CILINDRO, por detrás (lágrima)."""
    p = Pieza("P15_base")
    K = P["base"]; pz = M["poste_z"]; xp = M["poste_x"]; yb = Y_BASE; CC = K["camara_cables"]; PT = K["patas"]
    D = T_["D"] + T_["holgura"]; Rb = D / 2 + T_["casquillo_pared"]
    yt = yb + CC["suelo"] + CC["alto"]                 # el tubo apoya aquí
    h0, h1, w0, w1 = K["alto_pata_raiz"], K["alto_pata_punta"], K["ancho_pata_raiz"], K["ancho_pata_punta"]
    ra = K["redondeo_aristas"]
    p.cil_y(yb, yt + K["alto_buje"], xp, pz, 2 * Rb, op="base")
    for k in ("delanteras", "traseras"):
        for sg in (1, -1):
            a = math.radians(sg * PT[k]["ang"]); d = (math.sin(a), 0.0, math.cos(a)); lat = (-math.cos(a), 0.0, math.sin(a))
            s_r, s_t = Rb - 4.0, PT[k]["L"] + w1 / 2       # raíz dentro del buje; punta donde acababa la punta redonda
            lin = lambda s, v0, v1: v0 + (v1 - v0) * (s - Rb) / (s_t - Rb)      # alto/ancho: v0 en la pared, v1 en la punta
            P0 = lambda s: (xp + s * d[0], yb, pz + s * d[2])
            sec = [p.seccion_redondeada(P0(s), (0, 1, 0), lat, lin(s, h0, h1), lin(s, w0, w1), ra) for s in (s_r, s_t)]
            b = p._tmp("Pata")
            p.c("solid.loft", sections=[{"sketch": sec[0]}, {"sketch": sec[1]}], operation="new", body_name=b, name=b)
            p.c("solid.combine", target=p.cuerpo, tools=[b], operation="join")
    yc = yb + CC["suelo"] + CC["alto"] / 2 - 0.25        # centro de la salida
    h = [p.cil_y(yt, yt + K["alto_buje"] + 1, xp, pz, D, op="keep"),                      # alojamiento del tubo
         p.cil_y(yb + CC["suelo"], yt + 0.05, xp, pz, CC["D"], op="keep"),               # cámara (escalón = apoyo del tubo)
         p.lagrima("XY", xp, yc, CC["salida_D"], pz - Rb - 1.0, pz - CC["D"] / 2 + 1.0, +1, op="keep"),   # salida hacia atrás (-Z)
         p.lagrima("YZ", yt + K["alto_buje"] * 0.6, pz, I["agujero_D"], xp + Rb - I["prof"] + 0.5, xp + Rb + 0.5, (1.0, 0.0), op="keep")]   # prisionero M3 (+X)
    for q in h:   # uno a uno: unir cilindros coaxiales como herramienta falla en el núcleo 0.30
        p.c("solid.combine", target=p.cuerpo, tools=[q], operation="cut")
    return p


def tubo():
    p = Pieza("C_tubo_alu")
    pz = M["poste_z"]; D = T_["D"]
    xp = M["poste_x"]
    p.cil_y(Y_TUBO_INF, Y_TUBO_SUP, xp, pz, D, op="base")
    p.cil_y(Y_TUBO_INF - 1, Y_TUBO_SUP + 1, xp, pz, D - 2 * T_["pared"], op="cut")
    return p


# ------------------------------------------------------------------ 23 casquillo del poste (pieza aparte)
def casquillo_poste():
    """Casquillo del tubo = NUDO del travesaño. Cilindro que sube hasta la cara superior del travesaño con una
    ranura transversal del MISMO perfil del travesaño (+0,1 de juego): el travesaño pasa a través, apoya en el
    fondo y queda abrazado delante y detrás (encaje por forma; peso y momentos los toma el nudo). Arriba enrasa.
    2 tornillos M3 de refuerzo por la pared trasera (asiento plano) a insertos de la cara trasera del travesaño.
    Abajo: alojamiento del tubo, tope cónico a 45°, paso de cables y costilla de prisioneros. Los cables llegan por
    el canal delantero del travesaño y bajan por un canal en la pared delantera del nudo (sin ventanas).
    Construido en su sitio (revolución sobre el eje real del tubo). Se imprime de pie, boca inferior en la cama."""
    p = Pieza("P23_casquillo_poste")
    T = P["poste"]; pz = M["poste_z"]; xp = M["poste_x"]; zr = M["travesano_z"]; yr = M["travesano_y"]
    D = T["D"] + T["holgura"]; R = D / 2; Rc = R + T["casquillo_pared"]; Lc = T["casquillo_prof"]; jg = T["nudo_juego"]
    yb, ytop = yr[0] - Lc, yr[1]                    # boca inferior / arriba enrasado con el travesaño
    ytubo = yr[0] - T["tope_sobre_tubo"]           # fin del tubo
    rt = T["tope_D"] / 2
    yf = yr[0] - 2.0                                # techo del paso de cables (2 mm bajo el fondo de la ranura)
    # revolución: exterior Rc; dentro alojamiento del tubo, tope cónico y paso Ø14 hasta yf; por encima macizo
    sk = p._sketch("YZ", xp)
    pts = [(yb, pz + R), (yb, pz + Rc), (ytop, pz + Rc), (ytop, pz + 0.5), (yf, pz + 0.5), (yf, pz + rt),
           (ytubo + (R - rt), pz + rt), (ytubo, pz + R), (yb, pz + R)]
    p.c("sketch.line", points=[[f(a), f(b)] for a, b in pts], infer=False)
    p.c("sketch.finish")
    b = p._tmp("Casquillo")
    p.c("solid.revolve", sketch=sk, axis={"origin": [f(xp), 0, f(pz)], "dir": [0, 1, 0]}, angle="360 deg",
        operation="new", body_name=b, name=b)
    p.cuerpo = b
    p.cil_y(yf + 0.05, yf + 1.0, xp, pz, 2.0)       # cierra el agujerito del eje en el techo del paso de cables
    # costilla de los prisioneros (detrás), arranque a 45° desde la pared
    p.poligono("YZ", [(yb + 3.0, pz - (Rc - 1.0)), (ytubo - 3.0, pz - (Rc - 1.0)), (ytubo - 3.0, pz - (Rc + 3.0)),
                      (yb + 7.0, pz - (Rc + 3.0))], xp - 5.0, xp + 5.0)
    # ranura del travesaño: su perfil con 0,1 de juego, pasante en X
    perfil = [(u, v, r + jg) for u, v, r in perfil_marco()]
    ran = p.envolvente_circulos("YZ", perfil, xp - Rc - 2.0, xp + Rc + 2.0, op="keep")
    p.c("solid.combine", target=p.cuerpo, tools=[ran], operation="cut")
    h = []
    for k in (0.35, 0.75):                                                # prisioneros del tubo
        y = yb + (ytubo - yb) * k
        h.append(p.lagrima("XY", xp, y, I["agujero_D"], pz - (Rc + 3.5), pz - (R - 0.5), +1, op="keep"))
    dx = T["nudo_tornillos_dx"]; zt = pz - math.sqrt(Rc ** 2 - dx ** 2)   # tornillos de refuerzo por la pared trasera
    zl = zt + 1.8                                   # rebaje plano para las cabezas (techo a 45°: sin voladizo)
    zo = pz - Rc - 1.0
    h.append(p.poligono("YZ", [(-5.0, zo), (-5.0, zl), (5.0, zl), (5.0 + (zl - zo), zo)], xp - dx - 4.5, xp + dx + 4.5, op="keep"))
    for sx in (-1, 1):
        h.append(p.lagrima("XY", xp + sx * dx, 0.0, I["tornillo_paso_D"], zl - 0.5, zr[0] + 0.5, +1, op="keep"))
    # canal de cables: continúa el del travesaño por dentro de la pared delantera y baja al paso del tubo
    # (techo a 45°; atraviesa el fondo de la ranura y el techo del paso). Sin ventana: el nudo queda macizo
    cc = M["canal_cables"]; zf = zr[1] + jg; prof = cc["prof"]
    h.append(p.poligono("YZ", [(cc["y"][1], zf - 0.3), (cc["y"][1] - prof - 0.3, zf + prof), (yf - 3.0, zf + prof),
                               (yf - 3.0, pz + 3.0), (cc["y"][1], pz + 3.0)], xp + cc["y"][0], xp + cc["y"][1], op="keep"))
    for q in h:
        p.c("solid.combine", target=p.cuerpo, tools=[q], operation="cut")
    return p


# ------------------------------------------------------------------ 99 probeta de tolerancias
def probeta():
    """Placa de 82×34×7 (se imprime tal cual, cara inferior en la cama) con los ajustes reales del ojo en variantes:
    fila de arriba: alojamientos del 684 (Ø9,0 / 9,1 / 9,2), del 623 (Ø10,05 / 10,15) y 684 pasante que nace
    en la cama con alivio de pata de elefante (como P21/P22). Fila de abajo: insertos M3 (Ø3,9 / 4,0 / 4,1),
    pasador Ø4 a presión (Ø3,90 / 3,95 / 4,00), agujero de biela Ø3,2 y paso de tornillo Ø3,4.
    Junto a cada agujero, 1-3 puntos marcan la variante (1 = la más pequeña). El valor de diseño es siempre el 2.º."""
    p = Pieza("P99_probeta")
    T = 7.0
    p.caja((-41, 41), (-17, 17), (0, T), op="base")
    def puntos(x, y, n):
        for k in range(n):
            p.cil_z(T - 0.6, T + 0.5, x + (k - (n - 1) / 2) * 2.2, y, 1.2, op="cut")
    ya, yb = 6.5, -7.5
    for k, d in enumerate((9.0, 9.1, 9.2)):           # 684: alojamiento de 4 mm desde arriba + paso Ø5,4
        x = -32 + 12 * k
        p.cil_z(T - 4.0, T + 0.5, x, ya, d, op="cut"); p.cil_z(-0.5, T - 3.95, x, ya, 5.4, op="cut"); puntos(x, ya + 8.0, k + 1)
    for k, d in enumerate((10.05, 10.15)):             # 623
        x = 5 + 13 * k
        p.cil_z(T - 4.0, T + 0.5, x, ya, d, op="cut"); p.cil_z(-0.5, T - 3.95, x, ya, 4.0, op="cut"); puntos(x, ya + 8.5, k + 2)
    x = 32                                              # 684 pasante desde la cama con alivio (P21/P22)
    p.cil_z(-0.5, T + 0.5, x, ya, 9.1, op="cut"); p.cil_z(-0.5, 0.4, x, ya, 9.7, op="cut"); puntos(x, ya + 8.5, 1)
    for k, d in enumerate((3.9, 4.0, 4.1)):            # insertos M3, ciegos 6,5
        x = -34 + 8 * k
        p.cil_z(T - 6.5, T + 0.5, x, yb, d, op="cut"); puntos(x, yb - 6.0, k + 1)
    for k, d in enumerate((3.90, 3.95, 4.00)):         # pasador Ø4 a presión, pasante
        x = -6 + 8 * k
        p.cil_z(-0.5, T + 0.5, x, yb, d, op="cut"); puntos(x, yb - 6.0, k + 1)
    for k, d in enumerate((3.2, 3.4)):                 # biela / paso de tornillo M3
        x = 22 + 9 * k
        p.cil_z(-0.5, T + 0.5, x, yb, d, op="cut"); puntos(x, yb - 6.0, k + 1)
    return p


def registrar(PIEZAS):
    PIEZAS.update({
        "P03_parpado_sup": parpado_sup, "P04_parpado_inf": parpado_inf, "P05_cuna": cuna,
        "P06_horquilla_izq": horquilla_izq, "P07_horquilla_der": horquilla_der, "P08_travesano": travesano,
        "P09_brazo_der": brazo_der, "P10_brazo_izq": brazo_izq,
        "P19_casquete_sup_der": casquete_sup_der, "P20_casquete_sup_izq": casquete_sup_izq,
        "P21_casquete_inf_der": casquete_inf_der, "P22_casquete_inf_izq": casquete_inf_izq,
        "P11_balancin": balancin, "P13_biela_sup": biela_sup, "P14_biela_inf": biela_inf,
        "P15_base": base, "P16_soporte_servo": soporte_servo, "P99_probeta": probeta,
        "P23_casquillo_poste": casquillo_poste,
        "C_servo_yaw": lambda: envolvente_servo("C_servo_yaw", SERVO_YAW),
        "C_servo_pitch": lambda: envolvente_servo("C_servo_pitch", SERVO_PITCH),
        "C_servo_parpadeo": lambda: envolvente_servo("C_servo_parpadeo", SERVO_PARP),
        "C_horn_yaw": lambda: horn("C_horn_yaw", SERVO_YAW),
        "C_horn_pitch": lambda: horn("C_horn_pitch", SERVO_PITCH),
        "C_horn_parpadeo": lambda: horn("C_horn_parpadeo", SERVO_PARP, B["horn_disco_R"]),
        "C_tubo_alu": tubo,
    })
