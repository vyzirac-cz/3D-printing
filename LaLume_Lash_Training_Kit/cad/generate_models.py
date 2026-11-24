"""
Parametric FreeCAD Generator for LaLume HeadSpa Lash Lift Training Kit
Generates:
  Part A - Enlarged Lash Models (120 mm, C-curl):
    - Lash_Flexible_TPU.step (with internal wire channel, >= 1.2 mm min wall)
    - Lash_Solid_Half_A.step & Lash_Solid_Half_B.step (split matte PLA + 3 filament pin holes)
  Part B - 5 Giant 5.5x Lash Lift Shields (flat back on Z=0, Multi-Section Loft, no text):
    - Shield_Round.step
    - Shield_Teardrop.step
    - Shield_Hybrid.step
    - Shield_Flat_Korean.step
    - Shield_Compensator.step
  Part C - 2-Part PLA Silicone Casting Mold (for Hybrid shield):
    - Shield_Mold_PartA.step (cavity half + 4 key recesses + pour spout + 2 air vents)
    - Shield_Mold_PartB.step (flat lid + 4 alignment keys + matching channels)
"""

import math
import os
import FreeCAD as App
import Part

# ==============================================================================
# 1. PARAMETERS
# ==============================================================================
PARAMS = {
    # Lash parameters
    "Lash_Length": 120.0,
    "Base_Diameter": 12.0,
    "Tip_Diameter": 1.5,
    "Wire_Diameter": 2.0,
    "Channel_Clearance": 0.4,
    "Tip_Safe_Margin": 8.0,
    "Min_Wall_Thickness": 1.2,
    "Pin_Diameter": 1.85,
    "Pin_Depth": 4.0,
    # Shield parameters (5.5x scale)
    "Scale_Factor": 5.5,
    "Shield_Length": 175.0,
    "Shield_Height": 85.0,
    "Shield_Thickness": 28.0,
    "Corner_Taper_Ratio": 0.35,
    "Upper_Flap_Thickness": 4.0,
    # Mold parameters
    "Mold_Wall_Thickness": 5.0,
    "Mold_Key_Diameter": 6.0,
    "Mold_Key_Clearance": 0.2,
    "Pour_Spout_Diameter": 8.0,
    "Air_Vent_Diameter": 2.5,
}

OUT_DIR = "/home/vyzirac/.gemini/antigravity/scratch/lalume_lash_models"
STEP_DIR = os.path.join(OUT_DIR, "step")
os.makedirs(STEP_DIR, exist_ok=True)


def validate_solid(name, shape):
    """Validate that a shape is a clean single solid and print metrics."""
    solids = shape.Solids
    valid = shape.isValid()
    vol = shape.Volume
    bb = shape.BoundBox
    status = "OK" if (valid and len(solids) == 1 and vol > 0) else "WARN"
    print(
        f"[{status}] {name}: valid={valid}, solids={len(solids)}, "
        f"vol={vol:.1f} mm3, bbox=({bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f}) mm"
    )
    return valid and len(solids) >= 1 and vol > 0


# ==============================================================================
# 2. LASH GEOMETRY HELPERS (C-CURL)
# ==============================================================================
def build_lash_spine_points(length=120.0, n_pts=40):
    """
    Generate a smooth C-curl spine in the XZ plane (Y=0 is symmetry plane)
    with exact arc length == `length`.
    """
    # Parametric C-curl: tangent angle progresses smoothly from 0 deg at base to ~75 deg at tip
    # using a slightly accelerating curve (gentle root, graceful curl toward tip)
    raw_pts = []
    ds = 1.0 / (n_pts - 1)
    x, z = 0.0, 0.0
    raw_pts.append(App.Vector(x, 0.0, z))
    for i in range(1, n_pts):
        t = i * ds
        theta = math.radians(78.0) * (t ** 1.35)
        x += math.cos(theta) * ds
        z += math.sin(theta) * ds
        raw_pts.append(App.Vector(x, 0.0, z))

    # Measure total polyline length and scale to exact `length`
    total_len = sum((raw_pts[i] - raw_pts[i - 1]).Length for i in range(1, len(raw_pts)))
    scale = length / total_len
    pts = [App.Vector(p.x * scale, 0.0, p.z * scale) for p in raw_pts]

    bs = Part.BSplineCurve()
    bs.interpolate(pts)
    return bs


def lash_radius_at(u):
    """Smooth taper from Base_Diameter/2 at u=0 to Tip_Diameter/2 at u=1."""
    r_base = PARAMS["Base_Diameter"] / 2.0
    r_tip = PARAMS["Tip_Diameter"] / 2.0
    return r_base + (r_tip - r_base) * u


def make_normal_circle_wire(center, tangent, radius, ellipticity=1.0):
    """Create a closed wire (circle or subtle ellipse) perpendicular to `tangent` in XZ plane."""
    t_dir = App.Vector(tangent).normalize()
    y_axis = App.Vector(0, 1, 0)
    n_dir = y_axis.cross(t_dir).normalize()

    if abs(ellipticity - 1.0) < 1e-6:
        edge = Part.makeCircle(radius, center, t_dir)
        return Part.Wire([edge])
    else:
        # Subtle ellipse: major along n_dir (in XZ), minor along Y (or vice-versa)
        pts = []
        n_seg = 24
        r_n = radius * math.sqrt(ellipticity)
        r_y = radius / math.sqrt(ellipticity)
        for k in range(n_seg):
            ang = 2.0 * math.pi * k / n_seg
            p = center + n_dir * (r_n * math.cos(ang)) + y_axis * (r_y * math.sin(ang))
            pts.append(p)
        bs = Part.BSplineCurve()
        bs.interpolate(pts, PeriodicFlag=True)
        return Part.Wire([bs.toShape()])


def build_solid_lash(spine):
    """Build the solid C-curl lash with smooth taper and spherical dome tip cap."""
    u0, u1 = spine.FirstParameter, spine.LastParameter
    n_sec = 25
    wires = []
    for i in range(n_sec):
        frac = i / (n_sec - 1)
        u = u0 + (u1 - u0) * frac
        pt = spine.value(u)
        tan = spine.tangent(u)[0]
        r = lash_radius_at(frac)
        wires.append(make_normal_circle_wire(pt, tan, r, ellipticity=1.0))

    loft = Part.makeLoft(wires, True, False)

    # Add smooth spherical dome cap at tip
    tip_pt = spine.value(u1)
    tip_r = PARAMS["Tip_Diameter"] / 2.0
    tip_sphere = Part.makeSphere(tip_r, tip_pt)
    solid = loft.fuse(tip_sphere).removeSplitter()
    return solid


def build_flexible_tpu_lash(solid_lash, spine):
    """
    Create Variant A (Flexible TPU) by cutting an internal wire channel along the spine.
    Ensures >= Min_Wall_Thickness (1.2 mm) everywhere around the channel.
    """
    chan_r = (PARAMS["Wire_Diameter"] + PARAMS["Channel_Clearance"]) / 2.0
    min_wall = PARAMS["Min_Wall_Thickness"]
    min_outer_r = chan_r + min_wall  # 1.2 + 1.2 = 2.4 mm (outer dia 4.8 mm)

    # Determine safe fractional end along spine
    r_base = PARAMS["Base_Diameter"] / 2.0
    r_tip = PARAMS["Tip_Diameter"] / 2.0
    u_wall_limit = (r_base - min_outer_r) / (r_base - r_tip)
    u_margin_limit = 1.0 - (PARAMS["Tip_Safe_Margin"] / PARAMS["Lash_Length"])
    u_end_frac = min(u_wall_limit, u_margin_limit)

    print(
        f"  TPU channel: dia={2*chan_r:.2f} mm, wall_limit_frac={u_wall_limit:.3f}, "
        f"margin_limit_frac={u_margin_limit:.3f} -> stopping at {u_end_frac*100:.1f}% "
        f"({u_end_frac*PARAMS['Lash_Length']:.1f} mm from base, "
        f"min outer wall >= {min_wall:.2f} mm)"
    )

    u0, u1 = spine.FirstParameter, spine.LastParameter
    u_end = u0 + (u1 - u0) * u_end_frac

    # Extend channel slightly past base (-2 mm) for clean boolean cut at root
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
    # Round the blind end of the channel with a hemisphere
    end_sphere = Part.makeSphere(chan_r, spine.value(u_end))
    chan_tool = chan_solid.fuse(end_sphere)

    tpu_lash = solid_lash.cut(chan_tool)
    return tpu_lash


def build_split_pla_lashes(solid_lash, spine):
    """
    Create Variant B (Solid Split-in-Half Matte PLA):
    Splits solid lash on Y=0 into Half_A (Y>=0) and Half_B (Y<=0),
    adds 3 blind registration pin holes at 25%, 50%, 75% along spine
    with locally clamped depth so outer wall >= 1.1 mm.
    Returns (half_a_aligned, half_b_aligned, half_a_print_flat, half_b_print_flat).
    """
    bb = solid_lash.BoundBox
    pad = 20.0
    box_neg = Part.makeBox(
        bb.XLength + 2 * pad,
        bb.YLength + 2 * pad,
        bb.ZLength + 2 * pad,
        App.Vector(bb.XMin - pad, -(bb.YLength + 2 * pad), bb.ZMin - pad),
    )
    box_pos = Part.makeBox(
        bb.XLength + 2 * pad,
        bb.YLength + 2 * pad,
        bb.ZLength + 2 * pad,
        App.Vector(bb.XMin - pad, 0.0, bb.ZMin - pad),
    )

    half_a = solid_lash.cut(box_neg)  # keeps Y >= 0
    half_b = solid_lash.cut(box_pos)  # keeps Y <= 0

    pin_r = PARAMS["Pin_Diameter"] / 2.0
    target_depth = PARAMS["Pin_Depth"]
    u0, u1 = spine.FirstParameter, spine.LastParameter

    for frac in (0.25, 0.50, 0.75):
        u = u0 + (u1 - u0) * frac
        pt = spine.value(u)
        local_r = lash_radius_at(frac)
        # Keep >= 1.1 mm outer wall so hole never pierces skin
        safe_depth = max(0.8, min(target_depth, local_r - 1.1))
        print(
            f"  PLA pin at {int(frac*100)}%: local_r={local_r:.2f} mm -> "
            f"hole depth={safe_depth:.2f} mm (outer wall={local_r - safe_depth:.2f} mm)"
        )
        # Cut into Half A (+Y direction from Y=-0.5 to Y=+safe_depth)
        pin_a = Part.makeCylinder(
            pin_r, safe_depth + 0.5, App.Vector(pt.x, -0.5, pt.z), App.Vector(0, 1, 0)
        )
        half_a = half_a.cut(pin_a)

        # Cut into Half B (-Y direction from Y=+0.5 to Y=-safe_depth)
        pin_b = Part.makeCylinder(
            pin_r, safe_depth + 0.5, App.Vector(pt.x, 0.5, pt.z), App.Vector(0, -1, 0)
        )
        half_b = half_b.cut(pin_b)

    # Also prepare print-ready flat orientations (cut face resting on Z=0)
    # Half A has flat face on Y=0 with solid in +Y -> rotate -90 deg around X so +Y becomes +Z
    half_a_flat = half_a.copy()
    half_a_flat.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    # Half B has flat face on Y=0 with solid in -Y -> rotate +90 deg around X so -Y becomes +Z
    half_b_flat = half_b.copy()
    half_b_flat.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)

    return half_a, half_b, half_a_flat, half_b_flat


# ==============================================================================
# 3. GIANT 5.5x LASH LIFT SHIELDS (MULTI-SECTION LOFT, FLAT BACK ON Z=0)
# ==============================================================================
def shield_profile_z(v, thickness, flap_t, profile_type):
    """
    Return Z height (bulge above flat back Z=0) for normalized height v in [0, 1]
    from bottom eyelid edge (v=0) to top flap edge (v=1).
    Ensures smooth C1/C2 organic shape with Z=0 at v=0 and v=1 (via rounded lips).
    """
    # Smooth end-rounding envelope at bottom (v=0) and top (v=1)
    if v <= 0.0 or v >= 1.0:
        return 0.0

    if profile_type == "Round":
        # Classic symmetric semi-elliptical barrel peaking near v=0.45, tapering into flap
        barrel = math.sin(math.pi * (v ** 0.85))
        z = thickness * (barrel ** 0.85)
        # Ensure upper flap maintains minimum thickness before top lip
        flap = flap_t * math.sin(math.pi * v) ** 0.4
        return max(z, flap)

    elif profile_type == "Teardrop":
        # Full lower-to-mid belly peaking around v=0.28, sweeping down to thin upper flap
        # Beta-like curve peaking at v = a/(a+b)
        a, b = 1.35, 3.3
        peak_v = a / (a + b)
        raw = (v ** a) * ((1.0 - v) ** b)
        raw_max = (peak_v ** a) * ((1.0 - peak_v) ** b)
        belly = thickness * (raw / raw_max)
        flap = flap_t * (math.sin(math.pi * v) ** 0.35)
        return max(belly, flap)

    elif profile_type == "Hybrid":
        # Anatomical: slightly straighter root lift, soft rounded apex at v~0.36, smooth upper flap
        a, b = 1.6, 2.7
        peak_v = a / (a + b)
        raw = (v ** a) * ((1.0 - v) ** b)
        raw_max = (peak_v ** a) * ((1.0 - peak_v) ** b)
        belly = thickness * (raw / raw_max)
        flap = flap_t * (math.sin(math.pi * v) ** 0.35)
        return max(belly, flap)

    elif profile_type == "Flat":
        # Korean Step 1 / L-curl: prominent low barrel at bottom (v~0.16), wide very thin flat upper flap
        a, b = 1.15, 6.2
        peak_v = a / (a + b)
        raw = (v ** a) * ((1.0 - v) ** b)
        raw_max = (peak_v ** a) * ((1.0 - peak_v) ** b)
        rim = thickness * (raw / raw_max)
        # Wide flat upper flap (~flap_t = 4 mm) smoothly tapering to top edge
        flap = flap_t * (math.sin(math.pi * v) ** 0.25)
        return max(rim, flap)

    else:
        raise ValueError(f"Unknown shield profile_type: {profile_type}")


def make_shield_section_wire(x_pos, y_base, height, thickness, flap_t, profile_type):
    """
    Build a closed YZ cross-section wire at X = x_pos with:
    - Smooth B-spline upper/front surface (Z >= 0)
    - Flat straight back edge along Z = 0 from top back to bottom
    """
    n_pts = 28
    pts = []
    # Sample from v=0 (bottom) to v=1 (top) with extra density near ends for smooth rounded lips
    for i in range(n_pts + 1):
        # Cosine spacing gives smoother rounding at v=0 and v=1
        v = 0.5 * (1.0 - math.cos(math.pi * i / n_pts))
        y = y_base + height * v
        z = shield_profile_z(v, thickness, flap_t, profile_type)
        pts.append(App.Vector(x_pos, y, z))

    bs = Part.BSplineCurve()
    bs.interpolate(pts)
    front_edge = bs.toShape()

    # Straight flat back edge on Z = 0 closing top back to bottom
    back_edge = Part.makeLine(pts[-1], pts[0])
    wire = Part.Wire([front_edge, back_edge])
    return wire


def build_giant_shield(profile_type, length, height, thickness):
    """
    Build an organic giant lash lift shield using Multi-Section Loft across 9 sections
    with smooth corner taper (Corner_Taper_Ratio = 0.35) and flat back on Z = 0.
    """
    taper_min = PARAMS["Corner_Taper_Ratio"]
    flap_t = PARAMS["Upper_Flap_Thickness"]

    # Normalized X stations u in [-1, 1]
    # Keep end stations very slightly inset from ±1.0 so loft sections are well-formed
    u_stations = [-0.98, -0.88, -0.70, -0.40, 0.0, 0.40, 0.70, 0.88, 0.98]
    wires = []

    for u in u_stations:
        x = u * (length / 2.0)

        # Smooth almond/half-moon envelope: 1.0 at center, smoothly tapering toward corners
        # For Hybrid, make inner corner (u<0) slightly sleeker (anatomical asymmetry)
        local_taper_min = taper_min
        if profile_type == "Hybrid" and u < 0:
            local_taper_min = taper_min * 0.85

        # Smooth cosine-bell envelope
        env = local_taper_min + (1.0 - local_taper_min) * (math.cos(0.5 * math.pi * u) ** 0.75)

        # Near extreme tips (|u| = 0.98), close down cleanly for rounded corners
        tip_round = math.sqrt(max(0.02, 1.0 - (u ** 4)))
        local_h = height * env * (0.45 + 0.55 * tip_round)
        local_t = thickness * env * (0.35 + 0.65 * tip_round)
        local_flap = min(flap_t, local_t * 0.6)

        # Subtle anatomical eyelid arch along the bottom edge (rises ~6 mm toward corners)
        y_base = 6.0 * (u ** 2)

        w = make_shield_section_wire(x, y_base, local_h, local_t, local_flap, profile_type)
        wires.append(w)

    solid = Part.makeLoft(wires, True, False)
    return solid


def build_compensator_strip(length=165.0, height=25.0, thickness=5.0):
    """
    Build Profile 5: Compensator Strip (165 x 25 x 5 mm)
    Thin gently arched demonstration strip with subtle rounded grip tabs at both ends.
    Uses exact stadium (2 lines + 2 semicircular arcs) cross-sections so the loft is 100% valid.
    """
    u_stations = [-1.0, -0.88, -0.75, -0.45, 0.0, 0.45, 0.75, 0.88, 1.0]
    wires = []

    for u in u_stations:
        x = u * (length / 2.0)
        # Gentle arch along X (curving in +Z by ~12 mm at center so it drapes over a shield)
        z_arch = 12.0 * (1.0 - u ** 2)
        # Slightly wider grip tabs at the ends (|u| >= 0.88)
        if abs(u) >= 0.88:
            local_h = height * 1.15
            local_t = thickness * 1.1
        else:
            local_h = height * (0.92 + 0.08 * (1.0 - u ** 2))
            local_t = thickness

        r = local_t / 2.0
        half_flat = max(1.0, (local_h / 2.0) - r)
        zc = z_arch + r

        # 4 corner points + 2 arc midpoints in YZ plane (consistent CCW order)
        p_top_front = App.Vector(x, half_flat, zc + r)
        p_top_mid = App.Vector(x, half_flat + r, zc)
        p_top_back = App.Vector(x, half_flat, zc - r)
        p_bot_back = App.Vector(x, -half_flat, zc - r)
        p_bot_mid = App.Vector(x, -half_flat - r, zc)
        p_bot_front = App.Vector(x, -half_flat, zc + r)

        e1 = Part.Arc(p_top_front, p_top_mid, p_top_back).toShape()
        e2 = Part.makeLine(p_top_back, p_bot_back)
        e3 = Part.Arc(p_bot_back, p_bot_mid, p_bot_front).toShape()
        e4 = Part.makeLine(p_bot_front, p_top_front)
        wires.append(Part.Wire([e1, e2, e3, e4]))

    solid = Part.makeLoft(wires, True, False)
    bb = solid.BoundBox
    solid.translate(App.Vector(0, -bb.YMin, -bb.ZMin))
    return solid


# ==============================================================================
# 4. 2-PART PLA SILICONE CASTING MOLD (FOR HYBRID SHIELD)
# ==============================================================================
def build_silicone_mold(shield_solid):
    """
    Build a 2-part PLA silicone casting mold around `shield_solid` (whose flat back is on Z=0):
      - Part A (Z >= 0): Cavity block with shield subtracted, 4 corner key recesses,
        half pour-spout channel (+Y top edge), and 2 half air-vent channels (+Y left/right).
      - Part B (Z <= 0): Flat lid plate with 4 protruding hemispherical alignment keys
        and matching half pour-spout + air-vent channels.
    Zero undercuts -> clean demolding!
    """
    bb = shield_solid.BoundBox
    wall = max(PARAMS["Mold_Wall_Thickness"], 6.0)
    xy_margin = 16.0  # room for wall + 6 mm alignment keys in the 4 corners
    lid_thick = 8.0

    x_min = bb.XMin - xy_margin
    x_max = bb.XMax + xy_margin
    y_min = bb.YMin - xy_margin
    y_max = bb.YMax + xy_margin
    z_top = bb.ZMax + wall

    block_w = x_max - x_min
    block_h = y_max - y_min

    # --- Part A: Cavity half (Z from 0 to z_top) ---
    block_a = Part.makeBox(block_w, block_h, z_top, App.Vector(x_min, y_min, 0.0))
    part_a = block_a.cut(shield_solid)

    # --- Part B: Flat lid half (Z from -lid_thick to 0) ---
    part_b = Part.makeBox(block_w, block_h, lid_thick, App.Vector(x_min, y_min, -lid_thick))

    # --- 4 Corner Alignment Keys (hemispheres on Z=0 parting plane) ---
    key_r = PARAMS["Mold_Key_Diameter"] / 2.0
    key_recess_r = (PARAMS["Mold_Key_Diameter"] + PARAMS["Mold_Key_Clearance"]) / 2.0
    inset = 8.0
    key_positions = [
        App.Vector(x_min + inset, y_min + inset, 0.0),
        App.Vector(x_max - inset, y_min + inset, 0.0),
        App.Vector(x_min + inset, y_max - inset, 0.0),
        App.Vector(x_max - inset, y_max - inset, 0.0),
    ]
    for kp in key_positions:
        # Protruding hemisphere on Part B (+Z into Part A)
        key_sphere = Part.makeSphere(key_r, kp)
        part_b = part_b.fuse(key_sphere)
        # Matching slightly oversized recess in Part A
        recess_sphere = Part.makeSphere(key_recess_r, kp)
        part_a = part_a.cut(recess_sphere)

    # --- Pour Spout (center top +Y) & 2 Air Vents (left & right +Y) ---
    # Placed along the parting plane Z = 0, running from inside the upper shield cavity
    # straight out through the +Y outer wall so the clamped mold stands upright on its -Y base!
    spout_r = PARAMS["Pour_Spout_Diameter"] / 2.0
    vent_r = PARAMS["Air_Vent_Diameter"] / 2.0

    # Pour spout at X = 0, entering cavity by 10 mm and exiting through y_max + 2 mm
    spout_y_start = bb.YMax - 10.0
    spout_len = (y_max + 2.0) - spout_y_start
    spout_cyl = Part.makeCylinder(
        spout_r, spout_len, App.Vector(0.0, spout_y_start, 0.0), App.Vector(0, 1, 0)
    )
    # Add a small conical funnel at the outer mouth of the pour spout
    funnel_len = 6.0
    funnel = Part.makeCone(
        spout_r,
        spout_r + 3.5,
        funnel_len,
        App.Vector(0.0, y_max - funnel_len + 0.5, 0.0),
        App.Vector(0, 1, 0),
    )
    spout_tool = spout_cyl.fuse(funnel)
    part_a = part_a.cut(spout_tool)
    part_b = part_b.cut(spout_tool)

    # 2 Air vents at X = ±0.35 * shield_length, entering cavity and exiting through y_max + 2 mm
    vent_x_offset = 0.32 * (bb.XMax - bb.XMin)
    for sx in (-vent_x_offset, vent_x_offset):
        vent_y_start = bb.YMax - 22.0
        vent_len = (y_max + 2.0) - vent_y_start
        vent_cyl = Part.makeCylinder(
            vent_r, vent_len, App.Vector(sx, vent_y_start, 0.0), App.Vector(0, 1, 0)
        )
        part_a = part_a.cut(vent_cyl)
        part_b = part_b.cut(vent_cyl)

    return part_a, part_b


# ==============================================================================
# 5. MAIN DOCUMENT GENERATION & STEP EXPORT
# ==============================================================================
def run():
    doc_name = "LaLume_Lash_Training_Kit"
    if doc_name in App.listDocuments():
        App.closeDocument(doc_name)
    doc = App.newDocument(doc_name)

    # Add parametric Spreadsheet
    sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
    sheet.set("A1", "Parameter")
    sheet.set("B1", "Value")
    for idx, (k, v) in enumerate(PARAMS.items(), start=2):
        sheet.set(f"A{idx}", k)
        sheet.set(f"B{idx}", str(v))
    doc.recompute()

    exported = []

    def add_and_export(name, shape, step_filename, pos=(0, 0, 0), color=(0.25, 0.25, 0.28)):
        valid = validate_solid(name, shape)
        # Export in clean local print-ready coordinates BEFORE layout shift
        step_path = os.path.join(STEP_DIR, step_filename)
        shape.exportStep(step_path)
        exported.append((name, step_path, valid))

        # Add to FreeCAD document with nice visual layout spacing
        obj = doc.addObject("Part::Feature", name)
        display_shape = shape.copy()
        display_shape.translate(App.Vector(*pos))
        obj.Shape = display_shape
        if App.GuiUp and obj.ViewObject:
            obj.ViewObject.ShapeColor = color
        return obj

    print("=== Generating Part A: Lash Models (C-Curl) ===")
    spine = build_lash_spine_points(PARAMS["Lash_Length"])
    solid_lash = build_solid_lash(spine)
    validate_solid("Lash_Solid_Full_Internal", solid_lash)

    tpu_lash = build_flexible_tpu_lash(solid_lash, spine)
    add_and_export(
        "Lash_Flexible_TPU",
        tpu_lash,
        "Lash_Flexible_TPU.step",
        pos=(0, -140, 0),
        color=(0.22, 0.24, 0.28),
    )

    _, _, half_a_flat, half_b_flat = build_split_pla_lashes(solid_lash, spine)
    add_and_export(
        "Lash_Solid_Half_A",
        half_a_flat,
        "Lash_Solid_Half_A.step",
        pos=(140, -140, 0),
        color=(0.15, 0.15, 0.17),
    )
    add_and_export(
        "Lash_Solid_Half_B",
        half_b_flat,
        "Lash_Solid_Half_B.step",
        pos=(280, -140, 0),
        color=(0.18, 0.18, 0.20),
    )

    print("\n=== Generating Part B: 5 Giant 5.5x Lash Lift Shields ===")
    shield_specs = [
        ("Shield_Round", "Round", 170.0, 80.0, 28.0, "Shield_Round.step", (0, 0, 0), (0.85, 0.55, 0.65)),
        ("Shield_Teardrop", "Teardrop", 170.0, 85.0, 32.0, "Shield_Teardrop.step", (200, 0, 0), (0.78, 0.48, 0.62)),
        ("Shield_Hybrid", "Hybrid", 175.0, 85.0, 26.0, "Shield_Hybrid.step", (400, 0, 0), (0.65, 0.52, 0.78)),
        ("Shield_Flat_Korean", "Flat", 180.0, 95.0, 18.0, "Shield_Flat_Korean.step", (600, 0, 0), (0.52, 0.68, 0.78)),
    ]

    hybrid_shield_shape = None
    for name, ptype, length, height, thick, fname, pos, col in shield_specs:
        s_shape = build_giant_shield(ptype, length, height, thick)
        if ptype == "Hybrid":
            hybrid_shield_shape = s_shape
        add_and_export(name, s_shape, fname, pos=pos, color=col)

    comp_shape = build_compensator_strip(165.0, 25.0, 5.0)
    add_and_export(
        "Shield_Compensator",
        comp_shape,
        "Shield_Compensator.step",
        pos=(800, 25, 0),
        color=(0.88, 0.72, 0.55),
    )

    print("\n=== Generating Part C: 2-Part PLA Silicone Casting Mold (Hybrid Shield) ===")
    mold_a, mold_b = build_silicone_mold(hybrid_shield_shape)
    # Orient Part A cavity face UP (+Z) and Part B lid keys UP (+Z) for easy inspection & flat printing!
    mold_a_print = mold_a.copy()
    # Part A currently has flat outer back at Z = z_top and cavity opening at Z = 0 -> flip 180 around X so cavity opens UP
    bb_a = mold_a_print.BoundBox
    mold_a_print.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    bb_a2 = mold_a_print.BoundBox
    mold_a_print.translate(App.Vector(0, -bb_a2.YMin, -bb_a2.ZMin))

    # Part B currently has flat outer back at Z = -lid_thick and keys on Z = 0 pointing +Z -> translate Z so back sits at Z = 0
    mold_b_print = mold_b.copy()
    bb_b = mold_b_print.BoundBox
    mold_b_print.translate(App.Vector(0, -bb_b.YMin, -bb_b.ZMin))

    add_and_export(
        "Shield_Mold_PartA",
        mold_a_print,
        "Shield_Mold_PartA.step",
        pos=(200, 140, 0),
        color=(0.35, 0.55, 0.75),
    )
    add_and_export(
        "Shield_Mold_PartB",
        mold_b_print,
        "Shield_Mold_PartB.step",
        pos=(440, 140, 0),
        color=(0.45, 0.65, 0.85),
    )

    doc.recompute()
    fcstd_path = os.path.join(OUT_DIR, "LaLume_Lash_Training_Kit.FCStd")
    doc.saveAs(fcstd_path)
    print(f"\nSaved FreeCAD document: {fcstd_path}")
    print(f"Exported {len(exported)} STEP files to: {STEP_DIR}")


if __name__ == "__main__" or True:
    run()
