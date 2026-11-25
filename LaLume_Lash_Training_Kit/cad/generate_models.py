"""
Parametric FreeCAD Generator for LaLume HeadSpa Lash Lift Training Kit (v2 - Lash Oasis Curved-Arch Anatomy)
Generates:
  Part A - Enlarged Lash Models (C-Curl + L/M-Curl for side-by-side demonstration):
    - Lash_Flexible_TPU.step (C-curl with internal 2.4 mm wire channel, >= 1.2 mm min wall)
    - Lash_Solid_Half_A.step & Lash_Solid_Half_B.step (C-curl split Matte PLA, flat face on Z=0)
    - Lash_LM_Curl_Half_A.step & Lash_LM_Curl_Half_B.step (L/M-curl split Matte PLA, flat face on Z=0)
  Part B - 5 Giant 5.5x Curved-Arch Lash Lift Shields (Lash Oasis 2-zone anatomy, standing on flat Z=0 base):
    - Shield_Round.step (semicircular D-barrel + thin curved semicircular upper flap)
    - Shield_Teardrop.step (full lower teardrop belly + thin curved upper flap)
    - Shield_Hybrid.step (flat-faced angled L/M wedge ramp + thin curved upper flap)
    - Shield_Flat_Korean.step (low subtle bottom lip + wide tall thin curved flap)
    - Shield_Compensator.step (arch-matched curved compensator strip with end grip tabs)
  Part C - 2-Part PLA Silicone Casting Mold (for Curved-Arch Hybrid Shield, zero undercuts):
    - Shield_Mold_PartA.step (top cavity block + 4 corner key recesses + pour funnel + 2 air vents)
    - Shield_Mold_PartB.step (flat bottom lid + 4 hemispherical alignment keys + matching channels)
"""

import math
import os
import re
import xml.etree.ElementTree as ET
import FreeCAD as App
import Part
import MeshPart

# ==============================================================================
# 1. PARAMETERS
# ==============================================================================
PARAMS = {
    # Lash parameters
    "Lash_Length": 150.0,         # Enlarged teaching lash length (easy to hold against giant shields)
    "Base_Diameter": 12.0,
    "Tip_Diameter": 1.8,
    "Wire_Diameter": 2.0,
    "Channel_Clearance": 0.4,
    "Tip_Safe_Margin": 8.0,
    "Min_Wall_Thickness": 1.2,
    "Pin_Diameter": 1.85,
    "Pin_Depth": 4.0,
    # Curved-Arch Shield parameters (5.5x Lash Oasis scale)
    "Scale_Factor": 5.5,
    "Arch_Radius": 135.0,         # Horizontal eyelid bend radius (~28-30 mm bend depth over ~175 mm chord)
    "Upper_Flap_Thickness": 6.0,  # Crisp thin upper flap matching reference diagram
    # Mold parameters
    "Mold_Wall_Thickness": 6.0,
    "Mold_Key_Diameter": 6.0,
    "Mold_Key_Clearance": 0.2,
    "Pour_Spout_Diameter": 8.0,
    "Air_Vent_Diameter": 2.5,
}

REPO_DIR = "/home/vyzirac/git/3D-printing/LaLume_Lash_Training_Kit"
STEP_DIR = os.path.join(REPO_DIR, "step")
STL_DIR = os.path.join(REPO_DIR, "stl")
CAD_DIR = os.path.join(REPO_DIR, "cad")
for d in (STEP_DIR, STL_DIR, CAD_DIR):
    os.makedirs(d, exist_ok=True)


def validate_solid(name, shape):
    """Validate that a shape is a clean single solid and print true tessellated metrics."""
    solids = shape.Solids
    valid = shape.isValid()
    vol = shape.Volume
    verts, _ = shape.tessellate(0.2)
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
    status = "OK" if (valid and len(solids) == 1 and vol > 0) else "WARN"
    print(
        f"[{status}] {name:24s}: valid={valid}, solids={len(solids)}, "
        f"vol={vol:8.1f} mm3, true=({dx:5.1f} x {dy:5.1f} x {dz:5.1f}) mm, z_min={min(zs):.2f}"
    )
    return valid and len(solids) >= 1 and vol > 0


# ==============================================================================
# 2. LASH GEOMETRY HELPERS (C-CURL & L/M-CURL)
# ==============================================================================
def build_lash_spine(length=150.0, curl_type="C", n_pts=45):
    """
    Generate a smooth lash spine in the XZ plane (Y=0 is symmetry plane)
    with exact arc length == `length`.
      - "C": Classic smooth round C-curl (~110 deg sweep matching the Round shield barrel)
      - "LM": Flat root base (~25% length), crisp smooth bend (~75 deg), then straight upright shaft
              (matching the pale yellow Hybrid L/M shield in the Lash Oasis reel!)
    """
    raw_pts = []
    ds = 1.0 / (n_pts - 1)
    x, z = 0.0, 0.0
    raw_pts.append(App.Vector(x, 0.0, z))
    for i in range(1, n_pts):
        t = i * ds
        if curl_type == "C":
            # Smooth continuous round curl from 0 deg to ~115 deg
            theta = math.radians(115.0) * (t ** 1.15)
        elif curl_type == "LM":
            # Smooth sigmoid bend concentrated around t in [0.18, 0.42], then straight upward at ~78 deg
            # Sigmoid transition from 0 to 1
            s = 1.0 / (1.0 + math.exp(-16.0 * (t - 0.28)))
            s0 = 1.0 / (1.0 + math.exp(-16.0 * (0.0 - 0.28)))
            s_norm = (s - s0) / (1.0 - s0)
            theta = math.radians(78.0) * s_norm
        else:
            raise ValueError(f"Unknown curl_type: {curl_type}")
        x += math.cos(theta) * ds
        z += math.sin(theta) * ds
        raw_pts.append(App.Vector(x, 0.0, z))

    total_len = sum((raw_pts[i] - raw_pts[i - 1]).Length for i in range(1, len(raw_pts)))
    scale = length / total_len
    pts = [App.Vector(p.x * scale, 0.0, p.z * scale) for p in raw_pts]

    bs = Part.BSplineCurve()
    bs.interpolate(pts)
    return bs


def lash_radius_at(u):
    r_base = PARAMS["Base_Diameter"] / 2.0
    r_tip = PARAMS["Tip_Diameter"] / 2.0
    return r_base + (r_tip - r_base) * u


def make_normal_circle_wire(center, tangent, radius):
    t_dir = App.Vector(tangent).normalize()
    edge = Part.makeCircle(radius, center, t_dir)
    return Part.Wire([edge])


def build_solid_lash(spine):
    u0, u1 = spine.FirstParameter, spine.LastParameter
    n_sec = 25
    wires = []
    for i in range(n_sec):
        frac = i / (n_sec - 1)
        u = u0 + (u1 - u0) * frac
        pt = spine.value(u)
        tan = spine.tangent(u)[0]
        r = lash_radius_at(frac)
        wires.append(make_normal_circle_wire(pt, tan, r))

    loft = Part.makeLoft(wires, True, False)
    tip_pt = spine.value(u1)
    tip_r = PARAMS["Tip_Diameter"] / 2.0
    tip_sphere = Part.makeSphere(tip_r, tip_pt)
    return loft.fuse(tip_sphere).removeSplitter()


def build_flexible_tpu_lash(solid_lash, spine):
    chan_r = (PARAMS["Wire_Diameter"] + PARAMS["Channel_Clearance"]) / 2.0
    min_wall = PARAMS["Min_Wall_Thickness"]
    min_outer_r = chan_r + min_wall

    r_base = PARAMS["Base_Diameter"] / 2.0
    r_tip = PARAMS["Tip_Diameter"] / 2.0
    u_wall_limit = (r_base - min_outer_r) / (r_base - r_tip)
    u_margin_limit = 1.0 - (PARAMS["Tip_Safe_Margin"] / PARAMS["Lash_Length"])
    u_end_frac = min(u_wall_limit, u_margin_limit)

    u0, u1 = spine.FirstParameter, spine.LastParameter
    u_end = u0 + (u1 - u0) * u_end_frac

    start_pt = spine.value(u0)
    start_tan = spine.tangent(u0)[0].normalize()
    ext_start = start_pt - start_tan * 2.0

    n_sec = 20
    chan_wires = [make_normal_circle_wire(ext_start, start_tan, chan_r)]
    for i in range(n_sec):
        u = u0 + (u_end - u0) * (i / (n_sec - 1))
        pt = spine.value(u)
        tan = spine.tangent(u)[0]
        chan_wires.append(make_normal_circle_wire(pt, tan, chan_r))

    chan_solid = Part.makeLoft(chan_wires, True, False)
    end_sphere = Part.makeSphere(chan_r, spine.value(u_end))
    chan_tool = chan_solid.fuse(end_sphere)

    tpu = solid_lash.cut(chan_tool)
    # Shift so lowest Z is at 0
    verts, _ = tpu.tessellate(0.2)
    zmin = min(v.z for v in verts)
    tpu.translate(App.Vector(0, 0, -zmin))
    return tpu


def build_split_pla_lashes(solid_lash, spine):
    """
    Split lash on Y=0 into Half A (Y>=0) and Half B (Y<=0), add 3 blind 1.85 mm pin holes,
    and orient BOTH halves so the flat cut face rests directly on Z=0 with curved body in +Z!
    """
    bb = solid_lash.BoundBox
    pad = 20.0
    box_neg = Part.makeBox(
        bb.XLength + 2 * pad, bb.YLength + 2 * pad, bb.ZLength + 2 * pad,
        App.Vector(bb.XMin - pad, -(bb.YLength + 2 * pad), bb.ZMin - pad),
    )
    box_pos = Part.makeBox(
        bb.XLength + 2 * pad, bb.YLength + 2 * pad, bb.ZLength + 2 * pad,
        App.Vector(bb.XMin - pad, 0.0, bb.ZMin - pad),
    )

    half_a = solid_lash.cut(box_neg)  # Y >= 0
    half_b = solid_lash.cut(box_pos)  # Y <= 0

    pin_r = PARAMS["Pin_Diameter"] / 2.0
    target_depth = PARAMS["Pin_Depth"]
    u0, u1 = spine.FirstParameter, spine.LastParameter

    for frac in (0.25, 0.50, 0.75):
        u = u0 + (u1 - u0) * frac
        pt = spine.value(u)
        local_r = lash_radius_at(frac)
        safe_depth = max(0.9, min(target_depth, local_r - 1.1))
        pin_a = Part.makeCylinder(
            pin_r, safe_depth + 0.5, App.Vector(pt.x, -0.5, pt.z), App.Vector(0, 1, 0)
        )
        half_a = half_a.cut(pin_a)

        pin_b = Part.makeCylinder(
            pin_r, safe_depth + 0.5, App.Vector(pt.x, 0.5, pt.z), App.Vector(0, -1, 0)
        )
        half_b = half_b.cut(pin_b)

    # Rotate so flat cut face sits on Z=0 and curved body extends UP into +Z!
    # Half A has solid in +Y -> rotate +90 deg around X sends +Y to +Z!
    half_a_flat = half_a.copy()
    half_a_flat.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
    # Half B has solid in -Y -> rotate -90 deg around X sends -Y to +Z!
    half_b_flat = half_b.copy()
    half_b_flat.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)

    return half_a_flat, half_b_flat


# ==============================================================================
# 3. CURVED-ARCH 2-ZONE GIANT LASH LIFT SHIELDS (EXACT REFERENCE PROFILES)
# ==============================================================================
def make_arch_section_wire(theta, arch_r, local_h, barrel_depth, barrel_h, flap_t, profile_type):
    """
    Build an exact geometric closed cross-section wire in the radial vertical plane at angle `theta`,
    matching the 4 exact technical profiles from IMG_20261124_070159_103.jpg:
      - Round (Profile 1):      Exact semicircle from (0,0) out to barrel_depth, stepping into thin vertical flap
      - Teardrop (Profile 2):   Taller, slimmer semi-ellipse from (0,0) up into thin vertical flap
      - Flat (Profile 3):       Flat horizontal base + rounded corner + vertical front face + rounded top shoulder + flap
      - Hybrid (Profile 4):     Wide flat base + rounded corner + straight slanted inward ramp + rounded top shoulder + flap
    """
    origin = App.Vector(arch_r * math.sin(theta), arch_r * (math.cos(theta) - 1.0), 0.0)
    n_dir = App.Vector(math.sin(theta), math.cos(theta), 0.0)
    z_dir = App.Vector(0.0, 0.0, 1.0)

    def pt(n_val, z_val):
        return origin + n_dir * n_val + z_dir * z_val

    # Keep flap height strictly > barrel_h so vertical flap edge never degenerates at end tabs
    h_top = max(local_h, barrel_h + 2.5)

    if profile_type == "Round":
        # Diagram Profile 1: Full exact semicircle from (0, 0) through (barrel_depth, bh/2) to (flap_t, bh)
        # Sample exact elliptical/circular bulge with horizontal tangents at z=0 and z=bh
        pts = []
        n_seg = 24
        for i in range(n_seg + 1):
            ang = -math.pi / 2.0 + math.pi * (i / n_seg)  # -pi/2 (bottom) to +pi/2 (top)
            z = barrel_h * 0.5 * (1.0 + math.sin(ang))
            # Smooth baseline from n=0 at bottom to n=flap_t at top + pure semicircular protrusion
            base_n = flap_t * (0.5 * (1.0 + math.sin(ang)))
            bulge = (barrel_depth - 0.5 * flap_t) * math.cos(ang)
            pts.append(pt(base_n + bulge, z))
        bs = Part.BSplineCurve()
        bs.interpolate(pts)
        e1 = bs.toShape()
        e2 = Part.makeLine(pt(flap_t, barrel_h), pt(flap_t, h_top))
        e3 = Part.makeLine(pt(flap_t, h_top), pt(0.0, h_top))
        e4 = Part.makeLine(pt(0.0, h_top), pt(0.0, 0.0))
        return Part.Wire([e1, e2, e3, e4])

    elif profile_type == "Teardrop":
        # Diagram Profile 2: Taller, slimmer semi-ellipse curving smoothly from (0,0) to (flap_t, bh)
        pts = []
        n_seg = 24
        for i in range(n_seg + 1):
            ang = -math.pi / 2.0 + math.pi * (i / n_seg)
            z = barrel_h * 0.5 * (1.0 + math.sin(ang))
            base_n = flap_t * (0.5 * (1.0 + math.sin(ang)))
            bulge = (barrel_depth - 0.5 * flap_t) * math.cos(ang)
            pts.append(pt(base_n + bulge, z))
        bs = Part.BSplineCurve()
        bs.interpolate(pts)
        e1 = bs.toShape()
        e2 = Part.makeLine(pt(flap_t, barrel_h), pt(flap_t, h_top))
        e3 = Part.makeLine(pt(flap_t, h_top), pt(0.0, h_top))
        e4 = Part.makeLine(pt(0.0, h_top), pt(0.0, 0.0))
        return Part.Wire([e1, e2, e3, e4])

    elif profile_type == "Flat":
        # Diagram Profile 3: Flat base + rounded bottom corner + straight vertical front + rounded top shoulder + flap
        d = max(barrel_depth, flap_t + 8.0)
        r_b = min(6.0, (d - flap_t) * 0.45, barrel_h * 0.25)
        r_t = min(6.0, (d - flap_t) * 0.45, barrel_h * 0.25)
        k = 1.0 - math.sqrt(0.5)

        e1 = Part.makeLine(pt(0.0, 0.0), pt(d - r_b, 0.0))
        e2 = Part.Arc(pt(d - r_b, 0.0), pt(d - r_b * k, r_b * k), pt(d, r_b)).toShape()
        e3 = Part.makeLine(pt(d, r_b), pt(d, barrel_h - r_t))
        e4 = Part.Arc(pt(d, barrel_h - r_t), pt(d - r_t * k, barrel_h - r_t * k), pt(d - r_t, barrel_h)).toShape()
        e5 = Part.makeLine(pt(d - r_t, barrel_h), pt(flap_t, barrel_h))
        e6 = Part.makeLine(pt(flap_t, barrel_h), pt(flap_t, h_top))
        e7 = Part.makeLine(pt(flap_t, h_top), pt(0.0, h_top))
        e8 = Part.makeLine(pt(0.0, h_top), pt(0.0, 0.0))
        return Part.Wire([e1, e2, e3, e4, e5, e6, e7, e8])

    elif profile_type == "Hybrid":
        # Diagram Profile 4: Wide flat base + rounded bottom corner + straight slanted inward ramp + rounded top shoulder + flap
        d_bot = max(barrel_depth, flap_t + 12.0)
        d_top = max(flap_t + 7.0, d_bot * 0.72)
        r_b = min(7.0, (d_bot - flap_t) * 0.40, barrel_h * 0.22)
        r_t = min(6.0, (d_top - flap_t) * 0.45, barrel_h * 0.22)

        # Slanted ramp direction from (d_bot, r_b) to (d_top, barrel_h - r_t)
        dn = d_top - d_bot  # negative (slopes inward as z increases)
        dz = (barrel_h - r_t) - r_b
        seg_len = math.hypot(dn, dz)
        # Tangent unit vector along slanted ramp
        tn, tz = dn / seg_len, dz / seg_len

        # Smooth tangent-ish arc midpoints for bottom & top rounded corners
        p_b0 = pt(d_bot - r_b, 0.0)
        p_b1 = pt(d_bot, r_b)
        p_bm = pt(d_bot - r_b * 0.26, r_b * 0.30)

        p_t0 = pt(d_top, barrel_h - r_t)
        p_t1 = pt(d_top - r_t, barrel_h)
        p_tm = pt(d_top - r_t * 0.30, barrel_h - r_t * 0.26)

        e1 = Part.makeLine(pt(0.0, 0.0), p_b0)
        e2 = Part.Arc(p_b0, p_bm, p_b1).toShape()
        e3 = Part.makeLine(p_b1, p_t0)
        e4 = Part.Arc(p_t0, p_tm, p_t1).toShape()
        e5 = Part.makeLine(p_t1, pt(flap_t, barrel_h))
        e6 = Part.makeLine(pt(flap_t, barrel_h), pt(flap_t, h_top))
        e7 = Part.makeLine(pt(flap_t, h_top), pt(0.0, h_top))
        e8 = Part.makeLine(pt(0.0, h_top), pt(0.0, 0.0))
        return Part.Wire([e1, e2, e3, e4, e5, e6, e7, e8])

    else:
        raise ValueError(f"Unknown shield profile_type: {profile_type}")


def build_curved_shield(profile_type, chord_len, max_height, barrel_depth, barrel_h):
    """
    Build a curved-arch 2-zone giant shield standing upright on Z=0.
    Uses 11 radial cross-sections lofted cleanly along the concave eyelid arch!
    """
    arch_r = PARAMS["Arch_Radius"]
    flap_t = PARAMS["Upper_Flap_Thickness"]
    theta_max = math.asin(min(0.95, (chord_len / 2.0) / arch_r))

    u_stations = [-1.0, -0.88, -0.72, -0.52, -0.28, 0.0, 0.28, 0.52, 0.72, 0.88, 1.0]
    wires = []

    for u in u_stations:
        theta = u * theta_max
        # Semicircular upper flap dome (full height in center, sweeping down near left/right ends)
        dome_env = math.sqrt(max(0.0, 1.0 - (min(1.0, abs(u) / 0.90)) ** 2))
        local_h = barrel_h + 2.5 + (max_height - barrel_h - 2.5) * (dome_env ** 0.75)

        # Gentle anatomical depth taper toward corners while keeping crisp readable side profile at ends
        corner_scale = 0.85 + 0.15 * math.cos(0.5 * math.pi * u)
        local_barrel_d = barrel_depth * corner_scale

        w = make_arch_section_wire(
            theta, arch_r, local_h, local_barrel_d, barrel_h, flap_t, profile_type
        )
        wires.append(w)

    return Part.makeLoft(wires, True, False)


def build_arch_compensator(chord_len=165.0, height=24.0, thickness=5.0):
    """
    Build Profile 5: Arch-matched Compensator Strip that nests snugly over the front
    of the curved giant shields during class demonstrations, standing on Z=0.
    """
    arch_r = PARAMS["Arch_Radius"] + 16.0  # nests smoothly outside the shield front surface
    theta_max = math.asin(min(0.95, (chord_len / 2.0) / arch_r))

    u_stations = [-1.0, -0.86, -0.70, -0.40, 0.0, 0.40, 0.70, 0.86, 1.0]
    wires = []

    for u in u_stations:
        theta = u * theta_max
        origin = App.Vector(arch_r * math.sin(theta), arch_r * (math.cos(theta) - 1.0), 0.0)
        n_dir = App.Vector(math.sin(theta), math.cos(theta), 0.0)
        z_dir = App.Vector(0.0, 0.0, 1.0)

        # Subtle wider grip tabs at both ends (|u| >= 0.86)
        local_h = height * (1.20 if abs(u) >= 0.86 else 1.0)
        r = thickness / 2.0

        def pt(n_val, z_val):
            return origin + n_dir * n_val + z_dir * z_val

        # Flat bottom on Z=0, rounded top cap, uniform thickness
        p_b0 = pt(0.0, 0.0)
        p_b1 = pt(thickness, 0.0)
        p_t1 = pt(thickness, local_h - r)
        p_tm = pt(r, local_h)
        p_t0 = pt(0.0, local_h - r)

        e1 = Part.makeLine(p_b0, p_b1)
        e2 = Part.makeLine(p_b1, p_t1)
        e3 = Part.Arc(p_t1, p_tm, p_t0).toShape()
        e4 = Part.makeLine(p_t0, p_b0)
        wires.append(Part.Wire([e1, e2, e3, e4]))

    return Part.makeLoft(wires, True, False)


# ==============================================================================
# 3B. CURVED-SURFACE SVG LOGO EMBOSSER ("KLASH BEAUTYCARE" BOLD, PRINTABLE)
# ==============================================================================
def parse_svg_path_to_wires(d_str, scale):
    """Parse an SVG path d string (M, L, C, Z) into closed 2D FreeCAD Wires in the XZ plane (viewer-facing +Y)."""
    tokens = re.findall(r"[MLCZmlcz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", d_str)
    wires = []
    edges = []
    cur = None
    start = None
    i = 0
    cmd = None

    def v2(x_s, y_s):
        # Looking at front (+Y -> -Y): viewer's RIGHT is -X, viewer's UP is +Z
        return App.Vector(-x_s * scale, 0.0, -y_s * scale)

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            cmd = tok
            i += 1
            if cmd in ("Z", "z"):
                if cur is not None and start is not None and (cur - start).Length > 1e-4:
                    edges.append(Part.LineSegment(cur, start).toShape())
                if edges:
                    try:
                        w = Part.Wire(edges)
                        if w.isClosed():
                            wires.append(w)
                    except Exception:
                        pass
                edges = []
                cur = start
            continue

        if cmd == "M":
            if edges:
                try:
                    w = Part.Wire(edges)
                    if w.isClosed():
                        wires.append(w)
                except Exception:
                    pass
                edges = []
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            cur = v2(x, y)
            start = cur
            cmd = "L"
        elif cmd == "L":
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            nxt = v2(x, y)
            if (nxt - cur).Length > 1e-4:
                edges.append(Part.LineSegment(cur, nxt).toShape())
            cur = nxt
        elif cmd == "C":
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x3, y3 = float(tokens[i + 4]), float(tokens[i + 5])
            i += 6
            p1, p2, p3 = v2(x1, y1), v2(x2, y2), v2(x3, y3)
            if (p3 - cur).Length > 1e-4:
                bez = Part.BezierCurve()
                bez.setPoles([cur, p1, p2, p3])
                edges.append(bez.toShape())
            cur = p3
        else:
            i += 1

    if edges:
        try:
            w = Part.Wire(edges)
            if w.isClosed():
                wires.append(w)
        except Exception:
            pass
    return wires


def build_curved_logo_solids(svg_path, target_arc_width=126.0, z_base=64.0, relief=0.8, embed=0.8):
    """
    Build 3D solid letters from `klash_logo_bold.svg`, wrapped radially onto the front
    cylindrical surface of the curved shield upper flap (R = Arch_Radius + Upper_Flap_Thickness).
    Returns a list of valid 3D letter solids ready to fuse onto a shield.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}

    # Collect glyph path strings by id
    glyph_paths = {}
    for g in root.findall(".//svg:defs//svg:g", ns):
        gid = g.attrib.get("id")
        if gid:
            p = g.find("svg:path", ns)
            if p is not None and "d" in p.attrib:
                glyph_paths[gid] = p.attrib["d"]

    # Collect <use> placements
    uses = []
    for u in root.findall(".//svg:use", ns):
        href = u.attrib.get("{http://www.w3.org/1999/xlink}href", "").lstrip("#")
        if href in glyph_paths:
            uses.append((href, float(u.attrib["x"]), float(u.attrib["y"])))

    # Measure total SVG width from glyph placements
    # Approximate each glyph width ~16 units for centering
    min_x = min(x for _, x, _ in uses)
    max_x = max(x for _, x, _ in uses) + 15.0
    svg_w = max_x - min_x
    svg_cx = 0.5 * (min_x + max_x)
    scale = target_arc_width / svg_w

    arch_r = PARAMS["Arch_Radius"]
    r_front = arch_r + PARAMS["Upper_Flap_Thickness"]

    # Cache parsed faces per glyph id (in local XZ plane, centered around glyph's local origin)
    glyph_face_cache = {}
    for gid, d_str in glyph_paths.items():
        wires = parse_svg_path_to_wires(d_str, scale)
        if not wires:
            continue
        faces = []
        for w in wires:
            try:
                f = Part.Face(w)
                if f.Area > 1e-4:
                    faces.append(f)
            except Exception:
                pass
        if not faces:
            continue
        faces.sort(key=lambda f: f.Area, reverse=True)
        main_face = faces[0]
        for hole_f in faces[1:]:
            main_face = main_face.cut(hole_f)
        glyph_face_cache[gid] = main_face

    letter_solids = []
    for gid, ux, uy in uses:
        if gid not in glyph_face_cache:
            continue
        f_local = glyph_face_cache[gid].copy()
        # Shift local glyph so its horizontal center is at X=0 in local frame
        bb = f_local.BoundBox
        local_cx = 0.5 * (bb.XMin + bb.XMax)
        f_local.translate(App.Vector(-local_cx, 0.0, 0.0))

        # Extrude along +Y from y = -embed (inside shield) to y = +relief (proud of shield)
        solid = f_local.extrude(App.Vector(0.0, embed + relief, 0.0))
        solid.translate(App.Vector(0.0, -embed, 0.0))

        # Arc position along cylinder: viewer's LEFT is +theta, viewer's RIGHT is -theta
        # ux increases to the viewer's RIGHT -> arc_s decreases (goes from +width/2 to -width/2)
        glyph_svg_x = ux + (-local_cx / scale)
        arc_s = -(glyph_svg_x - svg_cx) * scale
        theta = arc_s / r_front

        # Rotate around Z so local +Y aligns with radial outward normal (sin(theta), cos(theta), 0)
        # Rotation by -theta (in degrees) sends (0, 1, 0) -> (sin(theta), cos(theta), 0)
        solid.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), -math.degrees(theta))
        solid.translate(
            App.Vector(
                r_front * math.sin(theta),
                r_front * math.cos(theta) - arch_r,
                z_base,
            )
        )
        letter_solids.append(solid)

    return letter_solids


def apply_logo_to_shield(shield_shape, z_base=64.0):
    """Engrave/deboss (cut) the curved 'KLASH BEAUTYCARE' bold logo 0.8 mm deep into the shield's upper flap."""
    svg_path = os.path.join(CAD_DIR, "klash_logo_bold.svg")
    if not os.path.exists(svg_path):
        print("  [WARN] Logo SVG not found, skipping deboss.")
        return shield_shape
    # Cut 0.8 mm deep into the 6.0 mm upper flap (leaving 5.2 mm solid wall), extending 1.0 mm proud for clean boolean cut
    letters = build_curved_logo_solids(svg_path, target_arc_width=126.0, z_base=z_base, relief=1.0, embed=0.8)
    result = shield_shape.cut(letters)
    return result


# ==============================================================================
# 4. 2-PART PLA SILICONE CASTING MOLD (FOR CURVED-ARCH HYBRID SHIELD)
# ==============================================================================
def build_curved_silicone_mold(shield_solid):
    """
    Build a zero-undercut 2-part PLA silicone casting mold for the curved-arch Hybrid shield:
      - Part A (Top Cavity Block, Z >= 0): Enclosing block with shield subtracted.
        Since Hybrid tapers inward as Z increases, Part A lifts straight UP off the silicone!
        Flipped upside-down for export so the flat outer top rests on Z=0 and cavity opens UP!
      - Part B (Flat Bottom Lid, Z <= 0): Seals the flat Z=0 base of the shield with 4 corner
        hemispherical alignment keys, 8 mm pour funnel, and 2 x 2.5 mm air vents at the top of Part A.
    """
    verts, _ = shield_solid.tessellate(0.2)
    xmin, xmax = min(v.x for v in verts), max(v.x for v in verts)
    ymin, ymax = min(v.y for v in verts), max(v.y for v in verts)
    zmax = max(v.z for v in verts)

    wall = max(PARAMS["Mold_Wall_Thickness"], 6.0)
    xy_margin = 16.0  # room for wall + 6 mm alignment keys in the 4 corners
    lid_thick = 8.0

    bx0, bx1 = xmin - xy_margin, xmax + xy_margin
    by0, by1 = ymin - xy_margin, ymax + xy_margin
    bw = bx1 - bx0
    bh = by1 - by0
    bz = zmax + wall

    # Part A: Cavity block (Z from 0 to bz)
    block_a = Part.makeBox(bw, bh, bz, App.Vector(bx0, by0, 0.0))
    part_a = block_a.cut(shield_solid)

    # Part B: Flat bottom lid (Z from -lid_thick to 0)
    part_b = Part.makeBox(bw, bh, lid_thick, App.Vector(bx0, by0, -lid_thick))

    # 4 Corner Alignment Keys on Z = 0 parting plane
    key_r = PARAMS["Mold_Key_Diameter"] / 2.0
    recess_r = (PARAMS["Mold_Key_Diameter"] + PARAMS["Mold_Key_Clearance"]) / 2.0
    inset = 8.0
    key_pts = [
        App.Vector(bx0 + inset, by0 + inset, 0.0),
        App.Vector(bx1 - inset, by0 + inset, 0.0),
        App.Vector(bx0 + inset, by1 - inset, 0.0),
        App.Vector(bx1 - inset, by1 - inset, 0.0),
    ]
    for kp in key_pts:
        part_b = part_b.fuse(Part.makeSphere(key_r, kp))
        part_a = part_a.cut(Part.makeSphere(recess_r, kp))

    # Pour Spout (8.0 mm + funnel) through the TOP of Part A at X=0, Y=2.5 mm (right into top flap apex!)
    spout_r = PARAMS["Pour_Spout_Diameter"] / 2.0
    spout_y = 2.5
    spout_z0 = zmax - 12.0
    spout_cyl = Part.makeCylinder(
        spout_r, (bz + 2.0) - spout_z0, App.Vector(0.0, spout_y, spout_z0), App.Vector(0, 0, 1)
    )
    funnel = Part.makeCone(
        spout_r, spout_r + 3.5, 5.0, App.Vector(0.0, spout_y, bz - 4.5), App.Vector(0, 0, 1)
    )
    part_a = part_a.cut(spout_cyl.fuse(funnel))

    # 2 Air Vents (2.5 mm) at left & right upper arch shoulders leading straight up through top of Part A
    vent_r = PARAMS["Air_Vent_Diameter"] / 2.0
    arch_r = PARAMS["Arch_Radius"]
    for sign in (-1.0, 1.0):
        th = sign * math.radians(24.0)
        vx = (arch_r + 3.0) * math.sin(th)
        vy = (arch_r + 3.0) * math.cos(th) - arch_r
        vent_cyl = Part.makeCylinder(
            vent_r, bz + 2.0 - 20.0, App.Vector(vx, vy, 20.0), App.Vector(0, 0, 1)
        )
        part_a = part_a.cut(vent_cyl)

    # Orient Part A upside-down (cavity opening UP, flat outer top on Z=0) for clean printing & inspection
    part_a_print = part_a.copy()
    part_a_print.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    va, _ = part_a_print.tessellate(0.2)
    part_a_print.translate(App.Vector(0, -min(v.y for v in va), -min(v.z for v in va)))

    # Orient Part B with flat outer bottom on Z=0 and alignment keys pointing UP (+Z)
    part_b_print = part_b.copy()
    vb, _ = part_b_print.tessellate(0.2)
    part_b_print.translate(App.Vector(0, -min(v.y for v in vb), -min(v.z for v in vb)))

    return part_a_print, part_b_print


# ==============================================================================
# 5. MAIN GENERATION + STEP & STL EXPORT
# ==============================================================================
def run():
    doc_name = "LaLume_Lash_Training_Kit"
    if doc_name in App.listDocuments():
        App.closeDocument(doc_name)
    doc = App.newDocument(doc_name)

    # Parametric Spreadsheet
    sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
    sheet.set("A1", "Parameter")
    sheet.set("B1", "Value")
    for idx, (k, v) in enumerate(PARAMS.items(), start=2):
        sheet.set(f"A{idx}", k)
        sheet.set(f"B{idx}", str(v))
    doc.recompute()

    def add_and_export(name, shape, base_filename, pos=(0, 0, 0), color=(0.25, 0.25, 0.28)):
        validate_solid(name, shape)
        step_path = os.path.join(STEP_DIR, base_filename + ".step")
        stl_path = os.path.join(STL_DIR, base_filename + ".stl")
        shape.exportStep(step_path)
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1, AngularDeflection=0.2, Relative=False)
        mesh.write(stl_path)

        obj = doc.addObject("Part::Feature", name)
        disp = shape.copy()
        disp.translate(App.Vector(*pos))
        obj.Shape = disp
        if App.GuiUp and obj.ViewObject:
            obj.ViewObject.ShapeColor = color
        return obj

    print("=== Part A: Enlarged Teaching Lashes (C-Curl + L/M-Curl) ===")
    c_spine = build_lash_spine(PARAMS["Lash_Length"], "C")
    c_solid = build_solid_lash(c_spine)
    tpu_lash = build_flexible_tpu_lash(c_solid, c_spine)
    add_and_export("Lash_Flexible_TPU", tpu_lash, "Lash_Flexible_TPU", pos=(-60, -180, 0), color=(0.18, 0.20, 0.24))

    c_half_a, c_half_b = build_split_pla_lashes(c_solid, c_spine)
    add_and_export("Lash_Solid_Half_A", c_half_a, "Lash_Solid_Half_A", pos=(90, -180, 0), color=(0.12, 0.12, 0.14))
    add_and_export("Lash_Solid_Half_B", c_half_b, "Lash_Solid_Half_B", pos=(240, -180, 0), color=(0.16, 0.16, 0.18))

    lm_spine = build_lash_spine(PARAMS["Lash_Length"], "LM")
    lm_solid = build_solid_lash(lm_spine)
    lm_half_a, lm_half_b = build_split_pla_lashes(lm_solid, lm_spine)
    add_and_export("Lash_LM_Curl_Half_A", lm_half_a, "Lash_LM_Curl_Half_A", pos=(390, -180, 0), color=(0.12, 0.12, 0.14))
    add_and_export("Lash_LM_Curl_Half_B", lm_half_b, "Lash_LM_Curl_Half_B", pos=(540, -180, 0), color=(0.16, 0.16, 0.18))

    print("\n=== Part B: 5 Giant Curved-Arch Lash Lift Shields (Exact Reference Profiles) ===")
    shield_specs = [
        # Ordered left-to-right matching IMG_20261124_070159_103.jpg:
        # 1. Round (semicircle), 2. Teardrop (slim tall semi-ellipse), 3. Flat (vertical flat), 4. Hybrid (slanted ramp)
        ("Shield_Round",       "Round",    172.0, 85.0, 30.0, 52.0, (0,   0, 0), (0.98, 0.80, 0.10)),
        ("Shield_Teardrop",    "Teardrop", 172.0, 85.0, 22.0, 58.0, (210, 0, 0), (0.86, 0.52, 0.65)),
        ("Shield_Flat_Korean", "Flat",     175.0, 85.0, 23.0, 54.0, (420, 0, 0), (0.52, 0.72, 0.82)),
        ("Shield_Hybrid",      "Hybrid",   175.0, 85.0, 29.0, 53.0, (630, 0, 0), (0.96, 0.94, 0.62)),
    ]

    hybrid_shape = None
    for name, ptype, clen, mh, bd, bh, pos, col in shield_specs:
        s = build_curved_shield(ptype, clen, mh, bd, bh)
        logo_z = bh + 7.5  # Centered nicely on the upper flap with >= 7.5 mm clearance above barrel shoulder
        s = apply_logo_to_shield(s, z_base=logo_z)
        if ptype == "Hybrid":
            hybrid_shape = s
        add_and_export(name, s, name, pos=pos, color=col)

    comp = build_arch_compensator(165.0, 24.0, 5.0)
    add_and_export("Shield_Compensator", comp, "Shield_Compensator", pos=(840, 0, 0), color=(0.88, 0.72, 0.55))

    print("\n=== Part C: 2-Part PLA Silicone Casting Mold (Curved-Arch Hybrid Shield) ===")
    mold_a, mold_b = build_curved_silicone_mold(hybrid_shape)
    add_and_export("Shield_Mold_PartA", mold_a, "Shield_Mold_PartA", pos=(120, 120, 0), color=(0.35, 0.55, 0.75))
    add_and_export("Shield_Mold_PartB", mold_b, "Shield_Mold_PartB", pos=(380, 120, 0), color=(0.45, 0.65, 0.85))

    doc.recompute()
    fcstd_path = os.path.join(CAD_DIR, "LaLume_Lash_Training_Kit.FCStd")
    doc.saveAs(fcstd_path)
    print(f"\nSaved FreeCAD document: {fcstd_path}")


if __name__ == "__main__" or True:
    run()
