"""v1.1 — Parpadeo con servo TRASERO y palancas simples (sin engranajes).

Plano lateral derecho (Y,Z) en X≈80. Ángulo α desde +Z hacia +Y; punto = (r·sinα, r·cosα).
Servo con eje X en H=(yh,zh) detrás del ojo, cuerpo hacia dentro (oculto tras el globo).
Horn de doble brazo: brazo sup (ru, bu) y brazo inf (rd, bd), giran juntos γ.
Párpado sup: pin a (rl, a0+Θ).  Párpado inf: pin a (rl2, a2-Θi).  Dos bielas (en planos X distintos).
Objetivo: Θi(γ) = Θs(γ) (espejo) en 0..60°, buen ángulo de transmisión, recorrido de servo razonable.
"""
import json, math, sys
import numpy as np

TH = math.radians(60.0); N = 61
rng = np.random.default_rng(7)
LIM_ZH = (-78.0, -58.0); LIM_YH = (-14.0, 14.0)


def P(r, a):
    return np.array([r * math.sin(a), r * math.cos(a)])


def circ(c0, r0, c1, r1, prev):
    d = np.linalg.norm(c1 - c0)
    if d > r0 + r1 or d < abs(r0 - r1) or d == 0:
        return None
    a = (r0**2 - r1**2 + d**2) / (2 * d); h = math.sqrt(max(r0**2 - a**2, 0))
    u = (c1 - c0) / d; v = np.array([-u[1], u[0]])
    cands = [c0 + a * u + h * v, c0 + a * u - h * v]
    return min(cands, key=lambda c: np.linalg.norm(c - prev))


def transm(link_dir, tang):
    c = abs(float(np.dot(link_dir, tang)))
    return 90 - math.degrees(math.acos(min(1, c)))   # 90 ideal


def simular(x):
    yh, zh, ru, bu, rd, bd, rl, a0, rl2, a2 = x
    H = np.array([yh, zh])
    Cu0 = H + P(ru, bu); Cd0 = H + P(rd, bd)
    Pu0 = P(rl, a0); Pd0 = P(rl2, a2)
    Lu = np.linalg.norm(Pu0 - Cu0); Ld = np.linalg.norm(Pd0 - Cd0)
    # 1) Θs → γ (barrido del párpado superior)
    gam = [0.0]; Cu = Cu0; tr = []
    for k in range(1, N):
        th = TH * k / (N - 1)
        Pu = P(rl, a0 + th)
        c = circ(H, ru, Pu, Lu, Cu)
        if c is None or np.linalg.norm(c - Cu) > 4: return None
        Cu = c
        g = math.atan2(c[0] - H[0], c[1] - H[1]) - bu
        gam.append(g)
        ld = (Pu - Cu) / Lu
        tr.append(transm(ld, np.array([math.cos(a0 + th), -math.sin(a0 + th)])))
        tr.append(transm(ld, np.array([math.cos(bu + g), -math.sin(bu + g)])))
    gam = np.unwrap(np.array(gam))
    # 2) γ → Θi
    Pd = Pd0; thi = [0.0]; err = [0.0]
    for k in range(1, N):
        Cd = H + P(rd, bd + gam[k])
        p = circ(np.zeros(2), rl2, Cd, Ld, Pd)
        if p is None or np.linalg.norm(p - Pd) > 4: return None
        Pd = p
        ai = math.atan2(p[0], p[1])
        t = a2 - ai
        t = (t + math.pi) % (2 * math.pi) - math.pi
        thi.append(t)
        ld = (p - Cd) / Ld
        tr.append(transm(ld, np.array([math.cos(ai), -math.sin(ai)])))
        tr.append(transm(ld, np.array([math.cos(bd + gam[k]), -math.sin(bd + gam[k])])))
        err.append(math.degrees(t - TH * k / (N - 1)))
    # holguras entre planos: el pasador del horn inferior y el saliente de la palanca inferior atraviesan
    # el plano de la biela superior → la biela superior debe esquivarlos en todo el recorrido
    def dseg(a, b, q):
        t = np.clip(np.dot(q - a, b - a) / np.dot(b - a, b - a), 0, 1); return float(np.linalg.norm(a + t * (b - a) - q))
    hol = []
    Pd = Pd0
    for k in range(N):
        Pu = P(rl, a0 + TH * k / (N - 1)); Cu = H + P(ru, bu + gam[k]); Cd = H + P(rd, bd + gam[k])
        Pdk = P(rl2, a2 - thi[k])
        hol.append(dseg(Pu, Cu, H) - (3.5 + 6.5 + 0.6))      # horn entre bielas: la sup. esquiva el eje/cúpula del servo
        hol.append(dseg(Pu, Cu, Pdk) - (3.5 + 3.5 + 0.6))    # saliente Ø7 de la palanca inferior
        hol.append(dseg(Pu, Cu, np.zeros(2)) - (3.5 + 4.5 + 0.6))  # espiga del eje Ø9
        hol.append(dseg(Pdk, Cd, np.zeros(2)) - (3.5 + 4.5 + 0.6))
    hol.append(np.linalg.norm(Cu0 - Cd0) - 7.5)
    return dict(gam=gam, thi=np.array(thi), err=np.array(err), tr=np.array(tr), Lu=Lu, Ld=Ld, hol=min(hol))


def coste(x, info=False):
    s = simular(x)
    if s is None: return 1e9, None
    g = s["gam"]
    if not (np.all(np.diff(g) > 0) or np.all(np.diff(g) < 0)): return 1e9, None
    dg = abs(math.degrees(g[-1] - g[0]))
    e = np.abs(s["err"]).max(); trm = s["tr"].min()
    c = e * 4 + max(0, 40 - trm) * 3 + max(0, 90 - dg) + max(0, dg - 150) + max(0, -s["hol"]) * 30
    if info:
        yh, zh, ru, bu, rd, bd, rl, a0, rl2, a2 = x
        return c, dict(H=[round(yh, 2), round(zh, 2)], horn_sup=[round(ru, 2), round(math.degrees(bu), 2)],
                       horn_inf=[round(rd, 2), round(math.degrees(bd), 2)],
                       palanca_sup=[round(rl, 2), round(math.degrees(a0), 2)],
                       palanca_inf=[round(rl2, 2), round(math.degrees(a2), 2)],
                       biela_sup=round(s["Lu"], 2), biela_inf=round(s["Ld"], 2),
                       recorrido_servo=round(dg, 1), error_espejo_max=round(float(e), 3),
                       transmision_min=round(float(trm), 1), holgura_min_mm=round(s["hol"], 2))
    return c, None


lo = np.array([LIM_YH[0], LIM_ZH[0], 14, -math.pi, 14, -math.pi, 11, math.radians(8), 11, math.radians(-170)])
hi = np.array([LIM_YH[1], LIM_ZH[1], 18, math.pi, 18, math.pi, 17, math.radians(170), 17, math.radians(-12)])
if __name__ == "__main__":
    mejor = (1e9, None)
    for _ in range(40000):
        x = lo + rng.random(10) * (hi - lo)
        c, _ = coste(x)
        if c < mejor[0]: mejor = (c, x)
    x, c0 = mejor[1], mejor[0]
    for sc in (0.05, 0.02, 0.005):
        for _ in range(8000):
            y = np.clip(x + rng.normal(0, 1, 10) * (hi - lo) * sc, lo, hi)
            c, _ = coste(y)
            if c < c0: x, c0 = y, c
    c, info = coste(x, True)
    print(json.dumps(info, indent=1, ensure_ascii=False))
    json.dump({"x": list(map(float, x)), **info}, open(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", "w"), indent=1)
