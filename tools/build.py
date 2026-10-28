"""Gera os SVGs do perfil do GitHub com a identidade de nicolasfmelo.org.

Textos viram <path> (sem depender de fontes no navegador). Uso:
  uv run --with fonttools --with uharfbuzz build.py <fonts_dir> <out_dir>
"""

import base64
import json
import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).parent
FONTS = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# Tokens da página (app/globals.css).
BG = "#121417"
CARD = "#181b1f"
RAISED = "#1e2226"
FG = "#f2f2f2"
MUTED = "#a1a6ad"
SUBTLE = "#838990"
ACCENT = "#ff6a13"
BORDER = "#2a2e33"


# ---------------------------------------------------------------- texto em vetor

class Face:
    def __init__(self, file, wght):
        blob = hb.Blob.from_file_path(str(FONTS / file))
        self.face = hb.Face(blob)
        self.font = hb.Font(self.face)
        self.font.set_variations({"wght": wght})
        self.upem = self.face.upem

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions


FACES = {
    "display": Face("Outfit.ttf", 700),
    "heading": Face("Outfit.ttf", 600),
    "medium": Face("Outfit.ttf", 500),
    "body": Face("Inter.ttf", 400),
    "bodym": Face("Inter.ttf", 500),
    "interb": Face("Inter.ttf", 700),
    "mono": Face("JBMono.ttf", 400),
    "monob": Face("JBMono.ttf", 600),
}


def measure(text, face="body", size=16, track=0.0):
    f = FACES[face]
    infos, pos = f.shape(text)
    k = size / f.upem
    return sum(p.x_advance for p in pos) * k + track * size * max(0, len(infos) - 1)


def text(s, x, y, face="body", size=16, fill=FG, anchor="start", track=0.0, opacity=None, cls=None):
    """Texto como um único <path>. `track` em em (como letter-spacing)."""
    f = FACES[face]
    infos, pos = f.shape(s)
    k = size / f.upem
    w = measure(s, face, size, track)
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    pen = SVGPathPen(None, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
    cx = x
    for info, p in zip(infos, pos):
        tp = TransformPen(pen, (k, 0, 0, -k, cx + p.x_offset * k, y - p.y_offset * k))
        f.font.draw_glyph_with_pen(info.codepoint, tp)
        cx += p.x_advance * k + track * size
    d = pen.getCommands()
    attrs = f'fill="{fill}"'
    if opacity is not None:
        attrs += f' opacity="{opacity}"'
    if cls:
        attrs += f' class="{cls}"'
    return f'<path {attrs} d="{d}"/>'


def wrap(s, face, size, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if measure(trial, face, size) > max_w and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def svg(w, h, body, title, style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title>"
        + (f"<style>{style}</style>" if style else "")
        + body
        + "</svg>"
    )


def save(name, content):
    (OUT / name).write_text(content, encoding="utf-8")
    print(f"{name}: {len(content) / 1024:.0f} KB")


def frame(w, h, r=10):
    return f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="{r}" fill="{CARD}" stroke="{BORDER}"/>'


def monogram(x, y, s=1.0, stroke=FG, width=1.5):
    """Monograma NM da página: o último traço do N é o primeiro do M."""
    return (
        f'<g transform="translate({x} {y}) scale({s})" fill="none" stroke="{stroke}" stroke-width="{width / s}" '
        f'stroke-linecap="square" stroke-linejoin="miter"><path d="M2 26V2l14 24V2"/><path d="M16 2l11 15L38 2v24"/></g>'
    )


def pill(x, y, label, fill=ACCENT):
    """Pill laranja com texto escuro (como nos cards da página). `y` é o topo."""
    w = measure(label, "monob", 12, 0.02) + 20
    return (
        f'<rect x="{x}" y="{y}" width="{w:.1f}" height="24" rx="12" fill="{fill}" fill-opacity="0.12" stroke="{fill}" stroke-opacity="0.45"/>'
        + text(label, x + 10, y + 16.5, "monob", 12, ACCENT, track=0.02)
    ), w


# ---------------------------------------------------------------- banner

def banner():
    W, H = 1280, 460
    data = json.loads((HERE / "car.json").read_text())
    pts = data["points"]
    sensor = data["sensor"]

    yaw, pitch = -0.62, 0.22
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    cx_, sx_ = math.cos(pitch), math.sin(pitch)
    scale, ox, oy = 250, 935, 262

    def project(x, y, z):
        x1 = x * cy_ + z * sy_
        z1 = -x * sy_ + z * cy_
        y2 = y * cx_ - z1 * sx_
        z2 = y * sx_ + z1 * cx_
        f = 3 / (3 + z2)
        return ox + x1 * scale * f, oy + y2 * scale * f, z2, f

    BUCKETS = 28
    SCAN = 3.6  # segundos da primeira varredura
    groups = [[] for _ in range(BUCKETS)]
    beams = [[] for _ in range(BUCKETS)]
    sx, sy, _, _ = project(sensor["x"], sensor["y"], sensor["z"])

    # Pontos de trás para a frente, para os mais próximos ficarem por cima.
    projected = []
    for x, y, z, phase, tone in pts:
        px, py, depth, f = project(x, y, z)
        projected.append((depth, px, py, f, phase, tone))
    projected.sort(key=lambda p: -p[0])

    for depth, px, py, f, phase, tone in projected:
        b = min(BUCKETS - 1, int(phase * BUCKETS))
        near = max(0.0, min(1.0, 1 - (depth + 1) / 2.6))
        alpha = min(1.0, (0.22 + near * 0.62) * (0.55 + tone * 0.45))
        r = (0.6 + tone * 0.8) * f
        groups[b].append(f'<rect x="{px - r:.1f}" y="{py - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" fill-opacity="{alpha:.2f}"/>')
        if tone < 0.5 and len(beams[b]) < 5 and random.random() < 0.08:
            beams[b].append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{px:.1f}" y2="{py:.1f}"/>')

    random.seed(7)
    dust = []
    for _ in range(130):
        dx, dy = random.random() * W, random.random() * H
        s = 0.6 + random.random() * 1.0
        dust.append(f'<rect x="{dx:.0f}" y="{dy:.0f}" width="{s:.1f}" height="{s:.1f}" fill-opacity="{0.08 + random.random() * 0.16:.2f}"/>')

    CYCLE = 9
    style = f"""
.b{{fill:{FG};opacity:1}}
.beam{{stroke:{ACCENT};stroke-width:.7;opacity:0}}
.scan{{opacity:0}}
@media (prefers-reduced-motion:no-preference){{
.b{{animation:cap {CYCLE}s linear infinite backwards}}
.beam{{animation:beam {CYCLE}s linear infinite backwards}}
.spin{{animation:spin 1.1s linear infinite}}
.dust{{animation:drift 14s ease-in-out infinite alternate}}
}}
@keyframes cap{{0%{{opacity:0;fill:{ACCENT}}}1.5%{{opacity:1;fill:{ACCENT}}}6%{{fill:{FG}}}80%{{opacity:1;fill:{FG}}}92%,100%{{opacity:0;fill:{FG}}}}}
@keyframes beam{{0%{{opacity:0}}.5%{{opacity:.35}}2.5%,100%{{opacity:0}}}}
@keyframes spin{{0%{{transform:translateX(-9px)}}50%{{transform:translateX(9px)}}100%{{transform:translateX(-9px)}}}}
@keyframes drift{{from{{transform:translateY(0)}}to{{transform:translateY(-14px)}}}}
"""
    body = [f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>']
    # Brilho laranja bem suave atrás do carro.
    body.append(
        f'<defs><radialGradient id="glow" cx="0.73" cy="0.6" r="0.42"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.07"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient></defs><rect width="{W}" height="{H}" rx="14" fill="url(#glow)"/>'
    )
    body.append(f'<g class="dust" fill="{FG}">{"".join(dust)}</g>')

    for i in range(BUCKETS):
        delay = i / BUCKETS * SCAN
        body.append(f'<g class="beam" style="animation-delay:{delay:.2f}s">{"".join(beams[i])}</g>')
    for i in range(BUCKETS):
        delay = i / BUCKETS * SCAN
        body.append(f'<g class="b" style="animation-delay:{delay:.2f}s">{"".join(groups[i])}</g>')

    # Sensor LiDAR no pórtico.
    w, h = 12, 16
    body.append(
        f'<line x1="{sx:.1f}" y1="0" x2="{sx:.1f}" y2="{sy - h / 2:.1f}" stroke="{MUTED}" stroke-opacity="0.5"/>'
        f'<g stroke="{FG}" fill="{CARD}">'
        f'<ellipse cx="{sx:.1f}" cy="{sy + h / 2:.1f}" rx="{w}" ry="{w * 0.35:.1f}"/>'
        f'<rect x="{sx - w:.1f}" y="{sy - h / 2:.1f}" width="{2 * w}" height="{h}" stroke="none"/>'
        f'<path d="M{sx - w:.1f} {sy - h / 2:.1f}v{h}M{sx + w:.1f} {sy - h / 2:.1f}v{h}" fill="none"/>'
        f'<ellipse cx="{sx:.1f}" cy="{sy - h / 2:.1f}" rx="{w}" ry="{w * 0.35:.1f}"/></g>'
        f'<g transform="translate({sx:.1f} {sy:.1f})"><rect class="spin" x="-2.5" y="-2.5" width="5" height="5" fill="{ACCENT}"/></g>'
    )

    # Texto (mesma hierarquia do hero).
    L = 72
    body.append(monogram(L, 54, 0.9, FG, 1.5))
    body.append(text("NICOLASFMELO.ORG", W - 56, 72, "mono", 12, SUBTLE, "end", 0.22))
    body.append(text("Nicolas Melo", L - 4, 214, "display", 88, FG, track=-0.02))
    body.append(text("AI & Computer Vision Engineer", L, 262, "heading", 28, ACCENT))
    body.append(text("Computer vision, multi-agent systems and MLOps.", L, 306, "body", 18, MUTED))
    body.append(text("Development, architecture and technical leadership.", L, 334, "body", 18, MUTED))

    stats = ["30 CASES IN PRODUCTION", "SINCE 2018", "BRASÍLIA, BR"]
    x = L
    for i, s in enumerate(stats):
        if i:
            body.append(f'<rect x="{x + 10:.1f}" y="{392}" width="1" height="16" fill="{BORDER}"/>')
            x += 21
        body.append(text(s, x, 405, "mono", 12, SUBTLE, track=0.18))
        x += measure(s, "mono", 12, 0.18) + 10

    body.append(f'<rect x="{W - 268}" y="398" width="6" height="6" fill="{ACCENT}"/>')
    body.append(text("lidar capture · 2,600 pts", W - 56, 405, "mono", 12, SUBTLE, "end", 0.04))

    save("banner.svg", svg(W, H, "".join(body), "Nicolas Melo — AI & Computer Vision Engineer", style))


# ---------------------------------------------------------------- cabeçalhos de seção

def section(name, index, title, note=""):
    W, H = 1280, 40
    for suffix, fg, sub, line in (("", FG, SUBTLE, BORDER), ("-light", "#1f2328", "#59636e", "#d1d9e0")):
        body = [text(index, 2, 27, "monob", 14, ACCENT, track=0.1)]
        tx = 2 + measure(index, "monob", 14, 0.1) + 18
        body.append(text(title, tx, 29, "heading", 30, fg))
        lx = tx + measure(title, "heading", 30) + 24
        end = W - 2
        if note:
            nw = measure(note, "mono", 12, 0.16)
            body.append(text(note, W - 2, 27, "mono", 12, sub, "end", 0.16))
            end = W - 2 - nw - 24
        body.append(f'<rect x="{lx:.0f}" y="22" width="{max(0, end - lx):.0f}" height="1" fill="{line}"/>')
        save(f"section-{name}{suffix}.svg", svg(W, H, "".join(body), f"{index} {title}"))


# ---------------------------------------------------------------- ilustrações dos cards

def illo_industrial(x, y):
    random.seed(3)
    out = []
    for _ in range(170):
        a = random.random() * math.tau
        r = abs(random.gauss(0, 1)) ** 0.6 * 36
        px, py = x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 0.7
        o = 0.25 + random.random() * 0.6
        c = ACCENT if random.random() < 0.12 else FG
        out.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="1.6" height="1.6" fill="{c}" fill-opacity="{o:.2f}"/>')
    out.append(f'<g fill="none" stroke="{MUTED}" stroke-opacity=".6"><rect x="{x - 64}" y="{y - 52}" width="18" height="12" rx="2"/><rect x="{x + 46}" y="{y - 52}" width="18" height="12" rx="2"/></g>')
    out.append(f'<g stroke="{ACCENT}" stroke-opacity=".35"><line x1="{x - 55}" y1="{y - 40}" x2="{x - 20}" y2="{y}"/><line x1="{x + 55}" y1="{y - 40}" x2="{x + 18}" y2="{y + 4}"/></g>')
    return "".join(out)


def illo_agents(x, y):
    nodes = [(x - 54, y - 30), (x + 54, y - 30), (x - 54, y + 30), (x + 54, y + 30)]
    out = [f'<g stroke="{BORDER}" stroke-width="1.2">' + "".join(f'<line x1="{x}" y1="{y}" x2="{nx}" y2="{ny}"/>' for nx, ny in nodes) + "</g>"]
    out.append(f'<g stroke="{ACCENT}" stroke-opacity=".7" stroke-dasharray="2 4"><line x1="{x - 54}" y1="{y - 30}" x2="{x + 54}" y2="{y - 30}"/></g>')
    for nx, ny in nodes:
        out.append(f'<rect x="{nx - 13}" y="{ny - 10}" width="26" height="20" rx="4" fill="{RAISED}" stroke="{MUTED}" stroke-opacity=".7"/>')
    out.append(f'<rect x="{x - 20}" y="{y - 16}" width="40" height="32" rx="6" fill="{ACCENT}" fill-opacity=".14" stroke="{ACCENT}"/>')
    out.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{ACCENT}"/>')
    return "".join(out)


def illo_cameras(x, y):
    out = []
    for r in range(3):
        for c in range(4):
            cx, cy = x - 66 + c * 44, y - 36 + r * 28
            hot = (r, c) in {(0, 2), (2, 1)}
            stroke = ACCENT if hot else MUTED
            out.append(f'<rect x="{cx - 18}" y="{cy - 11}" width="36" height="22" rx="3" fill="{RAISED}" stroke="{stroke}" stroke-opacity="{1 if hot else .5}"/>')
            if hot:
                out.append(f'<rect x="{cx - 7}" y="{cy - 6}" width="12" height="13" fill="none" stroke="{ACCENT}" stroke-width="1"/>')
            else:
                out.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="{MUTED}" fill-opacity=".5"/>')
    return "".join(out)


def illo_pipeline(x, y):
    out = []
    xs = [x - 72, x - 24, x + 24, x + 72]
    out.append(f'<line x1="{xs[0]}" y1="{y}" x2="{xs[-1]}" y2="{y}" stroke="{BORDER}" stroke-width="1.2"/>')
    out.append(f'<path d="M{xs[-1]} {y + 14} C {xs[-1]} {y + 46}, {xs[0]} {y + 46}, {xs[0]} {y + 14}" fill="none" stroke="{ACCENT}" stroke-opacity=".55" stroke-dasharray="2 4"/>')
    for i, px in enumerate(xs):
        hot = i == 2
        out.append(f'<circle cx="{px}" cy="{y}" r="13" fill="{ACCENT if hot else RAISED}" fill-opacity="{.16 if hot else 1}" stroke="{ACCENT if hot else MUTED}" stroke-opacity="{1 if hot else .6}"/>')
        out.append(text(str(i + 1), px, y + 4.5, "monob", 12, ACCENT if hot else MUTED, "middle"))
    return "".join(out)


def illo_lambda(x, y):
    return text("λ", x, y + 30, "interb", 92, ACCENT, "middle")


def illo_masa(x, y):
    out = []
    labels = ["delivery", "services", "engines", "domain"]
    for i, lb in enumerate(labels):
        w = 150 - i * 22
        yy = y - 42 + i * 22
        hot = i == 3
        out.append(f'<rect x="{x - w / 2}" y="{yy}" width="{w}" height="16" rx="3" fill="{ACCENT if hot else RAISED}" fill-opacity="{.16 if hot else 1}" stroke="{ACCENT if hot else MUTED}" stroke-opacity="{1 if hot else .5}"/>')
        out.append(text(lb, x, yy + 11.5, "mono", 10, ACCENT if hot else MUTED, "middle", 0.06))
    return "".join(out)


def illo_ergit(x, y):
    raw = (HERE / "brand" / "ergit-mark.svg").read_text()
    inner = raw[raw.index(">") + 1 : raw.rindex("</svg>")]
    # viewBox original: 249 120 715 715 → escala para ~96px.
    s = 96 / 715
    return f'<g transform="translate({x - 48} {y - 48}) scale({s:.4f}) translate(-249 -120)">{inner}</g>'


def illo_enty(x, y):
    b64 = base64.b64encode((HERE / "brand" / "enty-mark.png").read_bytes()).decode()
    return f'<image x="{x - 48}" y="{y - 48}" width="96" height="96" href="data:image/png;base64,{b64}"/>'


# ---------------------------------------------------------------- cards

def card(name, kicker, title, desc, illo, pills=(), foot=""):
    W, H = 632, 236
    body = [frame(W, H)]
    body.append(f'<rect x="{W - 220}" y="16" width="204" height="{H - 32}" rx="8" fill="{BG}" stroke="{BORDER}"/>')
    body.append(illo(W - 118, H / 2))
    pad = 28
    body.append(text(kicker.upper(), pad, 44, "mono", 11, SUBTLE, track=0.2))
    body.append(text(title, pad, 82, "heading", 26, FG))
    y = 112
    for line in wrap(desc, "body", 15, W - 220 - pad - 24):
        body.append(text(line, pad, y, "body", 15, MUTED))
        y += 22
    px = pad
    for p in pills:
        el, w = pill(px, H - 64, p)
        body.append(el)
        px += w + 8
    if foot:
        body.append(text(foot, px + (8 if pills else 0), H - 47, "mono", 12, SUBTLE, track=0.04))
    save(f"card-{name}.svg", svg(W, H, "".join(body), f"{title} — {desc}"))


# ---------------------------------------------------------------- reconhecimentos

def recognition():
    W, H = 1280, 132
    body = [frame(W, H)]
    half = W / 2
    body.append(f'<rect x="{half}" y="24" width="1" height="{H - 48}" fill="{BORDER}"/>')

    # Databricks: camadas em traço (brand-icons.tsx).
    body.append(
        f'<g transform="translate(36 34) scale(1)" fill="none" stroke="{ACCENT}" stroke-width="1.75" stroke-linejoin="round">'
        '<path d="m8 20 24-12 24 12-24 12L8 20Z"/><path d="M8 28v8l24 12 24-12v-8L32 40 8 28Z"/>'
        '<path d="M8 40v8l24 12 24-12v-8L32 52 8 40Z"/></g>'
    )
    body.append(text("RECOGNIZED BY DATABRICKS", 120, 56, "mono", 11, SUBTLE, track=0.2))
    body.append(text("LLMOps architecture reference", 120, 84, "heading", 21, FG))
    body.append(text("Corporate LLMOps case on Databricks + MLflow.", 120, 106, "body", 14, MUTED))

    ax = half + 36
    body.append(text("aws", ax + 32, 70, "medium", 34, FG, "middle", -0.02))
    body.append(
        f'<g transform="translate({ax} 74)" fill="none" stroke="{ACCENT}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 4c14 11 33 12 50 1"/><path d="m48 3 9-1-2 9"/></g>'
    )
    body.append(text("RECOGNIZED BY AWS", ax + 84, 56, "mono", 11, SUBTLE, track=0.2))
    body.append(text("Agentic architecture case", ax + 84, 84, "heading", 21, FG))
    body.append(text("Multi-agent user profiling for video streaming.", ax + 84, 106, "body", 14, MUTED))
    save("recognition.svg", svg(W, H, "".join(body), "Recognized by Databricks (LLMOps) and AWS (agentic architecture)"))


# ---------------------------------------------------------------- stack

def stack():
    cols = [
        ("Computer vision", ["PyTorch · OpenCV", "YOLO · YOLACT · U-Net", "ONNX · TensorRT · Triton", "Jetson · LiDAR · re-ID"]),
        ("AI agents", ["LangGraph · CrewAI", "RAG · Haystack", "MCP · A2A · LiteLLM", "Eval · observability"]),
        ("MLOps & platforms", ["Databricks · MLflow", "Kubernetes · ArgoCD", "gRPC · RabbitMQ", "Grafana · Prometheus"]),
        ("Languages & cloud", ["Python · Rust", "TypeScript · C++ · Go", "AWS · GCP · Azure", "Docker · Postgres"]),
    ]
    W, H = 1280, 214
    body = [frame(W, H)]
    cw = W / 4
    for i, (title, items) in enumerate(cols):
        x = i * cw + 30
        if i:
            body.append(f'<rect x="{i * cw:.0f}" y="24" width="1" height="{H - 48}" fill="{BORDER}"/>')
        body.append(text(f"0{i + 1}", x, 46, "monob", 11, ACCENT, track=0.1))
        body.append(text(title, x + 28, 47, "heading", 18, FG))
        for j, it in enumerate(items):
            body.append(text(it, x, 88 + j * 30, "mono", 13, MUTED))
    save("stack.svg", svg(W, H, "".join(body), "Stack: computer vision, AI agents, MLOps, languages and cloud"))


# ---------------------------------------------------------------- trajetória

def path():
    rows = [
        ("2026 —", "Code Boost", "Founder · AI consulting", True),
        ("2023 – 25", "NTT DATA Europe & Latam", "Lead Engineer · multi-agent platforms, LLMOps", False),
        ("2022 – 23", "CodeLeap", "Computer Vision Engineer · London, UK", False),
        ("2021 – 23", "Engineering Brasil", "Computer Vision Tech Lead", False),
        ("2020 – 21", "GETTER · Amplified Industry", "CV Engineer → Tech Lead", False),
        ("2020 – 21", "Combate à Fraude", "Computer Vision Engineer · document forensics", False),
        ("2020", "Deeper Systems", "Jr. CV Engineer · Las Vegas, US", False),
        ("2019 – 21", "Pega Placa", "Computer Vision Engineer · ALPR", False),
        ("2013 – 17", "Brazilian Army", "2nd Lieutenant", False),
    ]
    W = 1280
    RH = 46
    H = 40 + RH * (len(rows) - 1) + 40
    body = [frame(W, H)]
    lx = 190
    body.append(f'<rect x="{lx}" y="40" width="1" height="{RH * (len(rows) - 1)}" fill="{BORDER}"/>')
    for i, (when, org, role, now) in enumerate(rows):
        y = 40 + i * RH
        body.append(text(when, lx - 28, y + 5, "mono", 13, ACCENT if now else SUBTLE, "end", 0.04))
        if now:
            body.append(f'<circle cx="{lx + 0.5}" cy="{y}" r="9" fill="{ACCENT}" fill-opacity=".18"/>')
        body.append(f'<circle cx="{lx + 0.5}" cy="{y}" r="4" fill="{ACCENT if now else BG}" stroke="{ACCENT if now else MUTED}"/>')
        body.append(text(org, lx + 30, y + 6, "heading", 18, FG))
        body.append(text(role, lx + 30 + measure(org, "heading", 18) + 16, y + 5, "body", 14, MUTED))
    save("path.svg", svg(W, H, "".join(body), "Career path from the Brazilian Army to AI engineering"))


# ---------------------------------------------------------------- contato

def contact():
    W, H = 1280, 190
    body = [frame(W, H, 14)]
    body.append(monogram(W - 112, 60, 1.6, ACCENT, 1.5))
    body.append(text("CONTACT", 40, 54, "mono", 11, SUBTLE, track=0.22))
    body.append(text("Let’s talk", 38, 104, "display", 46, FG, track=-0.01))
    body.append(text("AI projects, computer vision or agent architecture: get in touch.", 40, 140, "body", 17, MUTED))
    body.append(text("nicolasfmelo@gmail.com", 40, 168, "mono", 13, ACCENT, track=0.02))
    save("contact.svg", svg(W, H, "".join(body), "Let's talk — nicolasfmelo@gmail.com"))


banner()
for args in [
    ("about", "01", "About", "BRASÍLIA · UTC−3"),
    ("work", "02", "Selected work", "NICOLASFMELO.ORG/PROJETOS"),
    ("building", "03", "What I’m building", "OPEN SOURCE + SIDE PROJECTS"),
    ("recognition", "04", "Recognition", ""),
    ("stack", "05", "Stack", ""),
    ("path", "06", "Path", "ARMY OFFICER → AI ENGINEER"),
]:
    section(*args)

card("industrial3d", "Industry · technical lead", "3D vision in industry", "Real-time poultry counting and mass estimation with cameras and LiDAR point clouds.", illo_industrial, ["18 cameras + 2 LiDARs"])
card("agents", "Architecture · leadership", "Multi-agent platform", "Cloud-agnostic AI runtime with agent memory, catalog, SDK, A2A/MCP and full observability.", illo_agents, ["international team"])
card("retail", "Systems engineering", "Computer vision at scale", "Theft-detection video pipeline: YOLO tracking, multimodal agents, Triton and Kubernetes.", illo_cameras, ["55+ concurrent cameras"])
card("llmops", "Architecture · leadership", "LLMOps on Databricks", "From experiment to evaluation and agent deploy: MLflow registry, champion/challenger, CI/CD.", illo_pipeline, ["Databricks reference"])

card("lambda", "Rust · MCP · open source", "Lambda Memory", "Local, source-bound memory for coding agents — Claude Code, OMP or any MCP client.", illo_lambda, ["local-first"], "keep the evidence")
card("masa", "Research · open source", "MASA framework", "An architecture that maximizes cognizability: how well AI agents read and safely change code.", illo_masa, ["+30–35% cognizability"], "0 violations")
card("ergit", "Rust · product", "Ergit", "Code versioning and review built around ergonomics.", illo_ergit, ["ergit.app"])
card("enty", "Compiler · experimental", "ENTY", "Compiled, strongly typed language for domain modeling. Self-hosted, emits LLVM IR.", illo_enty, ["coming soon"])

recognition()
stack()
path()
contact()
