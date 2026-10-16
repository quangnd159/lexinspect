"""Deterministic vector artwork. All surface highlights are rendered by Icon Composer."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "LexInspect.icon"
ASSETS = BUNDLE / "Assets"
ASSETS.mkdir(parents=True, exist_ok=True)


def svg(body):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">'
        + '<g transform="translate(512 547) scale(1.13) translate(-512 -512)">'
        + body
        + "</g></svg>\n"
    )


def solid(hex):
    return {
        "solid": "srgb:"
        + ",".join(f"{int(hex[i : i + 2], 16) / 255:.6f}" for i in (1, 3, 5))
        + ",1"
    }


def grad(a, b):
    return {"linear-gradient": [solid(a)["solid"], solid(b)["solid"]]}


def circle(cx, cy, r):
    return f"M{cx + r} {cy}a{r} {r} 0 1 1 {-2 * r} 0a{r} {r} 0 1 1 {2 * r} 0Z"


# One continuous contour joins head and handle. No overlapping strokes or seams.
cx, cy, R, half = 609, 539, 166, 32
angle = math.pi / 4
alpha = math.asin(half / R)
p1 = (cx + R * math.cos(angle + alpha), cy + R * math.sin(angle + alpha))
p2 = (cx + R * math.cos(angle - alpha), cy + R * math.sin(angle - alpha))
ex, ey = 817, 747
q1 = (ex + half / math.sqrt(2), ey - half / math.sqrt(2))
q2 = (ex - half / math.sqrt(2), ey + half / math.sqrt(2))
frame = f"M{p1[0]:.5f} {p1[1]:.5f}A{R} {R} 0 1 1 {p2[0]:.5f} {p2[1]:.5f}L{q1[0]:.5f} {q1[1]:.5f}A{half} {half} 0 0 1 {q2[0]:.5f} {q2[1]:.5f}Z"
FRAME = f'<path fill="#252C33" fill-rule="evenodd" d="{frame}{circle(cx, cy, 124)}"/>'
SURROUND = (
    f'<path fill="#E0F0F6" fill-rule="evenodd" d="{circle(cx, cy, 190)}{circle(cx, cy, 166)}"/>'
)
LENS = f'<circle cx="{cx}" cy="{cy}" r="124" fill="#D9EEEF"/>'
# An outlined Times script l supplies a crisp, balanced calligraphic silhouette.
letter = "M30 477 258 633 352 961Q415 1178 500 1282.5Q585 1387 714 1387Q790 1387 837.5 1341Q885 1295 885 1228Q885 1134 817 1044Q703 893 424 706L305 299Q284 228 284 189Q284 124 318.5 87.5Q353 51 405 51Q464 51 536 106Q608 161 678 292L715 279Q633 117 537 46.5Q441-24 351-24Q261-24 203 35Q145 94 145 196Q145 254 167 325L239 567L52 442ZM444 768Q673 935 750 1036Q827 1137 827 1217Q827 1260 801.5 1285Q776 1310 730 1310Q676 1310 632 1267Q573 1209 532 1070Z"
LETTER = f'<g transform="rotate(-7 609 539)"><path fill="#173C50" fill-rule="evenodd" transform="translate(544.95 634.41) scale(.14 -.14)" d="{letter}"/></g>'

PAPER = '<g transform="rotate(-8 459 465)"><rect x="234" y="178" width="450" height="584" rx="48" fill="#CDE7F5"/></g>'


# Editorial rhythm: a heading, two short paragraphs, and one inline selected word.
def bar(x, y, w, h=16, color="#668CA7"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{min(4, h / 2)}" fill="{color}"/>'


rows = [
    (306, 330, 82),
    (402, 330, 124),
    (540, 330, 62),
    (306, 368, 124),
    (444, 368, 82),
    (540, 368, 62),
    (306, 406, 64),
    (496, 406, 106),
    (306, 482, 100),
    (420, 482, 182),
    (306, 520, 154),
    (474, 520, 128),
    (306, 558, 88),
    (408, 558, 126),
]
TEXT = (
    '<g transform="rotate(-8 459 465)">'
    + bar(306, 264, 156, 24, "#315A77")
    + "".join(bar(x, y, w) for x, y, w in rows)
    + "</g>"
)
FOCUS = (
    '<g transform="rotate(-8 459 465)"><rect x="378" y="397" width="108" height="34" rx="7" fill="#9DDECF"/>'
    + bar(390, 406, 84, 16, "#337D73")
    + "</g>"
)
# Deliberately modeled bevels: an outer rounded face and a recessed inner lip.
FRAME = (
    '<defs><linearGradient id="outerGraphite" x1="0" y1="0" x2=".72" y2="1"><stop stop-color="#77818B"/><stop offset=".24" stop-color="#434D57"/><stop offset=".62" stop-color="#1B232C"/><stop offset="1" stop-color="#303B46"/></linearGradient><linearGradient id="graphiteFace" x1="0" y1="0" x2=".7" y2="1"><stop stop-color="#3E4852"/><stop offset=".5" stop-color="#252E37"/><stop offset="1" stop-color="#161F29"/></linearGradient><linearGradient id="innerLip" x1="0" y1="0" x2=".7" y2="1"><stop stop-color="#111A23"/><stop offset=".52" stop-color="#26323E"/><stop offset="1" stop-color="#697D8B"/></linearGradient></defs>'
    + f'<path fill="url(#outerGraphite)" fill-rule="evenodd" d="{frame}{circle(cx, cy, 124)}"/><path fill="url(#graphiteFace)" fill-rule="evenodd" d="{circle(cx, cy, 156)}{circle(cx, cy, 134)}"/><path fill="url(#innerLip)" fill-rule="evenodd" d="{circle(cx, cy, 134)}{circle(cx, cy, 124)}"/>'
)


def layer(name, file, art, color, glass=True, tint=None):
    (ASSETS / file).write_text(svg(art))
    item = {"name": name, "image-name": file, "glass": glass}
    if color:
        item["fill-specializations"] = [
            {"value": solid(color)},
            {"appearance": "dark", "value": solid(color)},
            {"appearance": "tinted", "value": solid(tint or color)},
        ]
    return item


def group(name, layers, transmission, shadow, depth=0, specular=True):
    d = {
        "name": name,
        "layers": layers,
        "lighting": "individual",
        "blur-material": 0,
        "specular": specular,
        "translucency": {"enabled": transmission > 0, "value": transmission},
        "shadow": {"kind": "neutral", "opacity": shadow},
    }
    if depth:
        d["refractivity"] = {"enabled": True, "depth": depth, "strength": 0.3}
    return d


source = {
    "features": ["refractivity"],
    "fill-specializations": [
        {"value": grad("#FCFDFE", "#EDF0F4")},
        {"appearance": "dark", "value": grad("#2C333D", "#111923")},
        {"appearance": "tinted", "value": "automatic"},
    ],
    "groups": [
        group(
            "01 · Graphite bezel and handle",
            [layer("Continuous graphite contour", "frame.svg", FRAME, "#252C33", tint="#45494E")],
            0.02,
            0.16,
            0.24,
        ),
        group(
            "02 · Optical aperture",
            [
                layer("Outlined script l", "letter.svg", LETTER, "#173C50", False, tint="#32373D"),
                layer("Clear lens", "lens.svg", LENS, "#D9EEEF", tint="#F0F0F0"),
            ],
            0.66,
            0.04,
            0.10,
        ),
        group(
            "03 · Crystal edge",
            [layer("Clear crystal surround", "crystal.svg", SURROUND, "#E0F0F6", tint="#FFFFFF")],
            0.90,
            0.07,
            0.06,
        ),
        group(
            "04 · Frosted reading sheet",
            [
                layer("Selected word", "focus.svg", FOCUS, None, False),
                layer("Text", "text.svg", TEXT, None, False),
                layer("Frosted sheet", "paper.svg", PAPER, "#CDE7F5", tint="#E3E5E8"),
            ],
            0.08,
            0.12,
            0.07,
        ),
    ],
    "supported-platforms": {"squares": "shared"},
}
# Lettering is a separate opaque plane so native glass never washes out its ink.
g0, g1, g2, g3 = source["groups"]
# Traditional magnifiers contain the glass strictly inside the rim.
g0["name"] = "01 · Sculpted graphite frame"
g0["refractivity"]["depth"] = 0.10
g0["shadow"]["opacity"] = 0.24
g0["refractivity"]["enabled"] = False
g0["blur-material"] = None
g0["translucency"]["enabled"] = False
ink = group("02 · Calligraphic ink", [g1["layers"][0]], 0, 0, specular=False)
g1["layers"] = g1["layers"][1:]
g1["name"] = "03 · Clear optical lens"
source["groups"] = [g0, ink, g1, g3]
for g in source["groups"]:
    for l in g["layers"]:
        if l["name"] == "Continuous graphite contour":
            l["fill-specializations"] = [
                f for f in l["fill-specializations"] if f.get("appearance") == "tinted"
            ]
        if l["name"] == "Frosted sheet":
            for f in l["fill-specializations"]:
                if f.get("appearance") != "tinted":
                    f["value"] = grad("#DDEFF8", "#BBDCEB")
# Remove superseded generated artboards after a design revision.
referenced = {l["image-name"] for g in source["groups"] for l in g["layers"]}
for asset in ASSETS.glob("*.svg"):
    if asset.name not in referenced:
        asset.unlink()
(BUNDLE / "icon.json").write_text(json.dumps(source, indent=2) + "\n")
(ROOT / "mark.svg").write_text(svg(PAPER + TEXT + FOCUS + FRAME + LENS + LETTER))
print(BUNDLE)
