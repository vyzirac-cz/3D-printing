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
    "Arch_Radius": 135.0,         # Horizontal eyelid bend radius (gives ~28-30 mm bend depth over ~175 mm chord)
    "Upper_Flap_Thickness": 5.0,  # Thin curved upper shell thickness
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
# 3. CURVED-ARCH 2-ZONE GIANT LASH LIFT SHIELDS (LASH OASIS STYLE)
# ==============================================================================
def profile_front_n(z_frac, barrel_depth, barrel_frac, flap_t, profile_type):
    """
    Return radial front protrusion `n` (in mm from the concave back shell n=0)
    as a function of normalized height `z_frac` in [0, 1].
    Creates the unmistakable 2-zone Lash Oasis side silhouette:
      - Distinct lower barrel/wedge (z_frac in [0, barrel_frac])
      - Thin curved upper flap (n = flap_t) for z_frac > barrel_frac
    """
    if profile_type == "Round":
        # Bright yellow Lash Oasis Round shield:
        # Full semicircular D-barrel from z_frac=0 to barrel_frac, then thin flap!
        if z_frac < barrel_frac:
            s = z_frac / barrel_frac  # 0..1 across barrel height
            # Semicircle peaking at s=0.5
            barrel = barrel_depth * math.sqrt(max(0.0, 1.0 - (2.0 * s - 1.0) ** 2))
            # Smoothly blend with flap_t
            return max(flap_t, flap_t + (barrel - flap_t) * 1.0)
        else:
            return flap_t

    elif profile_type == "Hybrid":
        # Pale yellow Lash Oasis Hybrid (L/M lift) shield:
        # Flat-faced angled wedge ramp at bottom (zero undercut in +Z!), transitioning
        # smoothly via a concave sweep into the thin vertical upper flap!
        if z_frac <= barrel_frac:
            s = z_frac / barrel_frac  # 0..1
            # Slight inward slope from bottom (100% depth) to top of ramp (~82% depth)
            # then smooth S-curve fillet down to flap_t in the top 30% of the barrel zone
            if s < 0.68:
                # Gently angled flat ramp face (100% -> 84%)
                ramp = barrel_depth * (1.0 - 0.16 * (s / 0.68))
                return max(flap_t, ramp)
            else:
                # Smooth concave transition into upper flap
                u = (s - 0.68) / 0.32
                smooth = 0.5 * (1.0 + math.cos(math.pi * u))
                return flap_t + (barrel_depth * 0.84 - flap_t) * smooth
        else:
            return flap_t

    elif profile_type == "Teardrop":
        # Full lower-to-mid asymmetrical teardrop belly tapering smoothly into thin flap
        a, b = 1.25, 3.4
        peak = a / (a + b)
        raw = (z_frac ** a) * ((1.0 - z_frac) ** b)
        raw_max = (peak ** a) * ((1.0 - peak) ** b)
        belly = barrel_depth * (raw / raw_max)
        # Keep a fuller base so it sits solidly on Z=0
        base_fill = barrel_depth * 0.55 * max(0.0, 1.0 - z_frac / 0.28)
        return max(flap_t, belly, base_fill)

    elif profile_type == "Flat":
        # Korean Step 1 / Flat-Curl: low gentle wedge rim at very bottom + wide thin upper flap
        if z_frac <= barrel_frac:
            s = z_frac / barrel_frac
            smooth = 0.5 * (1.0 + math.cos(math.pi * s))
            return flap_t + (barrel_depth - flap_t) * (smooth ** 1.2)
        else:
            return flap_t

    else:
        raise ValueError(f"Unknown shield profile_type: {profile_type}")


def make_arch_section_wire(theta, arch_r, local_h, barrel_depth, barrel_frac, flap_t, profile_type):
    """
    Build a closed cross-section wire in the radial vertical plane at arch angle `theta`.
    - Back edge: straight vertical line at radial offset n = 0 from z = 0 to z = local_h
    - Bottom edge: straight horizontal line on z = 0 from n = 0 to n_front(0)
    - Front curve: smooth 2-zone profile from z = 0 up to z = local_h
    - Top edge: smooth rounded cap closing front (n=flap_t) to back (n=0) at z = local_h
    """
    origin = App.Vector(arch_r * math.sin(theta), arch_r * (math.cos(theta) - 1.0), 0.0)
    n_dir = App.Vector(math.sin(theta), math.cos(theta), 0.0)
    z_dir = App.Vector(0.0, 0.0, 1.0)

    def pt(n_val, z_val):
        return origin + n_dir * n_val + z_dir * z_val

    # Sample front profile from z=0 up to z = local_h - flap_t/2
    n_samples = 30
    z_top_cap = max(local_h * 0.85, local_h - flap_t * 0.5)
    front_pts = []
    for i in range(n_samples + 1):
        zf = i / n_samples
        z = zf * z_top_cap
        n = profile_front_n(zf, barrel_depth, barrel_frac, flap_t, profile_type)
        front_pts.append(pt(n, z))

    # Top semicircular cap from front top (flap_t, z_top_cap) over (flap_t/2, local_h) to back (0, z_top_cap)
    cap_r = flap_t * 0.5
    p_front_top = front_pts[-1]
    p_cap_mid = pt(cap_r, local_h)
    p_back_top = pt(0.0, z_top_cap)
    p_back_bot = pt(0.0, 0.0)
    p_front_bot = front_pts[0]

    bs_front = Part.BSplineCurve()
    bs_front.interpolate(front_pts)
    e_front = bs_front.toShape()
    e_cap = Part.Arc(p_front_top, p_cap_mid, p_back_top).toShape()
    e_back = Part.makeLine(p_back_top, p_back_bot)
    e_bot = Part.makeLine(p_back_bot, p_front_bot)

    return Part.Wire([e_front, e_cap, e_back, e_bot])


def build_curved_shield(profile_type, chord_len, max_height, barrel_depth, barrel_h):
    """
    Build a curved-arch 2-zone Lash Oasis style giant shield standing upright on Z=0.
    Uses 11 radial cross-sections swept/lofted along the eyelid circular arch!
    """
    arch_r = PARAMS["Arch_Radius"]
    flap_t = PARAMS["Upper_Flap_Thickness"]
    theta_max = math.asin(min(0.95, (chord_len / 2.0) / arch_r))

    # 11 stations along the arch from -1 to +1
    u_stations = [-1.0, -0.88, -0.72, -0.52, -0.28, 0.0, 0.28, 0.52, 0.72, 0.88, 1.0]
    wires = []

    for u in u_stations:
        theta = u * theta_max

        # Semicircular upper flap height envelope (just like Lash Oasis: tall dome in center,
        # sweeping smoothly down to the barrel height at the left & right end tabs!)
        # For Hybrid, keep slightly asymmetric inner vs outer corner taper
        dome_env = math.sqrt(max(0.0, 1.0 - (min(1.0, abs(u) / 0.90)) ** 2))
        local_h = barrel_h + (max_height - barrel_h) * (dome_env ** 0.75)

        # Gentle barrel depth taper toward extreme corners (keeps clear side cross-section visible at ends!)
        if profile_type == "Hybrid" and u < 0:
            corner_scale = 0.72 + 0.28 * math.cos(0.5 * math.pi * u)
        else:
            corner_scale = 0.82 + 0.18 * math.cos(0.5 * math.pi * u)

        local_barrel_d = barrel_depth * corner_scale
        local_barrel_frac = min(0.92, barrel_h / local_h)

        w = make_arch_section_wire(
            theta, arch_r, local_h, local_barrel_d, local_barrel_frac, flap_t, profile_type
        )
        wires.append(w)

    solid = Part.makeLoft(wires, True, False)
    return solid


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

    print("\n=== Part B: 5 Giant Curved-Arch Lash Lift Shields (Lash Oasis 2-Zone Anatomy) ===")
    shield_specs = [
        # (name, profile_type, chord_len, max_height, barrel_depth, barrel_h, pos, color)
        ("Shield_Round",       "Round",    170.0, 82.0, 28.0, 38.0, (0,   0, 0), (0.98, 0.80, 0.10)),  # Bright yellow like reel!
        ("Shield_Hybrid",      "Hybrid",   175.0, 85.0, 26.0, 34.0, (210, 0, 0), (0.96, 0.94, 0.62)),  # Pale yellow like reel!
        ("Shield_Teardrop",    "Teardrop", 170.0, 85.0, 32.0, 42.0, (420, 0, 0), (0.86, 0.52, 0.65)),
        ("Shield_Flat_Korean", "Flat",     180.0, 95.0, 16.0, 24.0, (630, 0, 0), (0.52, 0.72, 0.82)),
    ]

    hybrid_shape = None
    for name, ptype, clen, mh, bd, bh, pos, col in shield_specs:
        s = build_curved_shield(ptype, clen, mh, bd, bh)
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
