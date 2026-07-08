"""
Generate a self-contained HTML descriptor report from pipeline JSON output.

Designed as a static HTML generator (no server required) so each run produces
a file you can open, share, or archive. When a future web interface is built,
the CSS variables, section structure, and Three.js viewer transfer directly.

Usage (called automatically by run_pipeline.py):
    from report import generate_report, open_report
    report_path = generate_report(data, output_dir, viewer_data)
    open_report(report_path)
"""

import json
import webbrowser
from pathlib import Path


# ── Roughness grading standard ────────────────────────────────────────────────
#
# Based on COARSE-scale curvature mean (radius = 60 mm).
# Coarse scale is used — not fine — because it is less sensitive to
# photogrammetry mesh noise and reflects the fragment's overall surface form.
#
# PROVISIONAL thresholds — recalibrate after ≥ 10 fragments.
# Grade  Label       Code  Threshold   Interpretation
# ─────  ──────────  ────  ─────────   ──────────────────────────────────────
#  1     Smooth       S    < 0.25 rad  Cast / cut face; original formwork surface
#  2     Moderate     M    0.25–0.45   Lightly textured; mild fracture or weathering
#  3     Rough        R    0.45–0.65   Fractured surface; typical demolition break
#  4     Very Rough   VR   > 0.65      Heavy fracture, spall, or aggregate exposure

ROUGHNESS_GRADES = [
    (0.25, "Smooth",     "S",  "#4ade80"),
    (0.45, "Moderate",   "M",  "#a3e635"),
    (0.65, "Rough",      "R",  "#fbbf24"),
    (float("inf"), "Very Rough", "VR", "#f87171"),
]


def _roughness_grade(coarse_mean_rad: float):
    """Return (label, code, hex_color) for a coarse curvature mean value."""
    for threshold, label, code, color in ROUGHNESS_GRADES:
        if coarse_mean_rad < threshold:
            return label, code, color
    return "Very Rough", "VR", "#f87171"


# ── Region colours (matches Three.js viewer palette) ─────────────────────────

REGION_COLORS = [
    "#7c83fd", "#4ade80", "#fbbf24", "#f87171",
    "#60a5fa", "#c084fc", "#fb923c", "#34d399",
]


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg:       #0f1117;
  --surface:  #1a1d2e;
  --border:   #2d3250;
  --accent:   #7c83fd;
  --text:     #e2e8f0;
  --muted:    #94a3b8;
  --success:  #4ade80;
  --warning:  #fbbf24;
  --danger:   #f87171;
  --radius:   8px;
  --gap:      16px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 32px;
}

.report { max-width: 1000px; margin: 0 auto; }

/* ── Header ── */
.header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--gap);
  margin-bottom: 24px;
}
.header h1 { font-size: 20px; color: var(--accent); letter-spacing: 0.05em; }
.header .meta { color: var(--muted); font-size: 11px; text-align: right; }

/* ── Mesh error banner ── */
.mesh-banner {
  background: #2d1b00;
  border: 1px solid #92400e;
  border-left: 4px solid var(--warning);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 20px;
  font-size: 12px;
  color: var(--warning);
}
.mesh-banner strong { display: block; margin-bottom: 2px; }
.mesh-banner span { color: #fde68a; font-size: 11px; }

/* ── Section ── */
.section { margin-bottom: 28px; }
.section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-bottom: 10px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Stat grid ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--gap);
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.stat-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
.stat-value { font-size: 18px; color: var(--text); font-weight: 600; }
.stat-unit  { font-size: 11px; color: var(--muted); margin-left: 3px; }
.stat-sub   { font-size: 11px; color: var(--muted); margin-top: 2px; }
.stat-na    { font-size: 14px; color: var(--muted); font-style: italic; }

/* ── Badges ── */
.badge {
  display: inline-block;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 99px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.badge-computed { background: #14532d; color: var(--success); }
.badge-pseudo   { background: #451a03; color: var(--warning); }

/* ── Roughness badge ── */
.roughness-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.roughness-code {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  min-width: 48px;
}
.roughness-label { font-size: 14px; font-weight: 600; }
.roughness-desc  { font-size: 11px; color: var(--muted); margin-top: 2px; }
.roughness-nums  { margin-left: auto; text-align: right; font-size: 11px; color: var(--muted); }
.roughness-nums span { display: block; }
.roughness-notice {
  margin-top: 8px;
  font-size: 10px;
  color: #4b5563;
  font-style: italic;
}

/* ── Table ── */
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.data-table th {
  background: #12152a;
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 8px 12px;
  text-align: left;
}
.data-table td {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
}
.data-table tr:hover td { background: #1f2340; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.region-dot {
  display: inline-block;
  width: 9px; height: 9px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

/* ── Three.js viewer ── */
.viewer-wrap {
  position: relative;
  background: #0a0c14;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  height: 420px;
}
#three-canvas {
  display: block;
  width: 100%;
  height: 100%;
}
.viewer-hint {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.55);
  color: var(--muted);
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 99px;
  pointer-events: none;
  white-space: nowrap;
}
.viewer-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
}
.legend-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
"""


# ── Helper renderers ──────────────────────────────────────────────────────────

def _badge(status: str) -> str:
    cls = "badge-computed" if status == "computed" else "badge-pseudo"
    return f'<span class="badge {cls}">{status}</span>'


def _fmt(val, digits=3, unit=""):
    if val is None:
        return "—"
    s = f"{val:.{digits}f}"
    if unit:
        s += f'<span class="stat-unit">{unit}</span>'
    return s


# ── Section builders ──────────────────────────────────────────────────────────

def _mesh_banner(b: dict) -> str:
    if b.get("watertight"):
        return ""
    return """
<div class="mesh-banner">
  <strong>⚠ Open mesh — volume and mass are estimates</strong>
  <span>Mesh has unclosed holes. Volume falls back to convex hull; convexity cannot be computed.
  Close the mesh in Blender (Mesh &gt; Fill Holes) to get accurate values.</span>
</div>"""


def _bounding_section(b: dict) -> str:
    dims = b.get("obb_dims_mm", [])
    dims_str = " × ".join(f"{d:.1f}" for d in dims) if dims else "—"
    vol_source = b.get("volume_source", "mesh")
    vol_note   = "convex hull — open mesh" if vol_source == "convex_hull" else "mesh volume"
    convexity  = b.get("convexity")
    mass       = b.get("mass_kg_est")
    status     = b.get("data_status", "computed")
    mass_status = b.get("mass_data_status", "pseudo")

    convexity_html = (
        f'<div class="stat-value">{convexity:.4f}</div>'
        if convexity is not None else
        '<div class="stat-na">N/A</div><div class="stat-sub">requires closed mesh</div>'
    )

    return f"""
<div class="section">
  <div class="section-title">Bounding &amp; Volume {_badge(status)}</div>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-label">OBB Dimensions</div>
      <div class="stat-value" style="font-size:14px">{dims_str}</div>
      <div class="stat-sub">mm (L × W × H)</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Volume</div>
      <div class="stat-value">{_fmt(b.get('volume_m3'), 6)}<span class="stat-unit"> m³</span></div>
      <div class="stat-sub">{vol_note}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Convexity Ratio</div>
      {convexity_html}
    </div>
    <div class="stat-card">
      <div class="stat-label">Mass Estimate {_badge(mass_status)}</div>
      <div class="stat-value">{_fmt(mass, 3)}<span class="stat-unit"> kg</span></div>
      <div class="stat-sub">@ 2400 kg/m³ concrete</div>
    </div>
  </div>
</div>"""


def _viewer_section(regions: list, viewer_data: dict) -> str:
    if not viewer_data or not viewer_data.get("points"):
        return ""

    point_json = json.dumps(viewer_data["points"])
    n_regions  = viewer_data.get("n_regions", len(regions))
    scale_mm   = viewer_data.get("scale_mm", "?")

    # Legend items
    legend_items = ""
    for i, region in enumerate(regions):
        color = REGION_COLORS[i % len(REGION_COLORS)]
        area  = region.get("area_m2_est")
        area_str = f"{area:.4f} m²" if area else "—"
        legend_items += f"""
    <div class="legend-item">
      <div class="legend-dot" style="background:{color}"></div>
      Region {i+1} · {area_str}
    </div>"""
    legend_items += """
    <div class="legend-item">
      <div class="legend-dot" style="background:#3d4455"></div>
      Unclassified
    </div>"""

    return f"""
<div class="section">
  <div class="section-title">3D Region Viewer <span style="font-size:10px;color:#3d4455;text-transform:none;letter-spacing:0">— drag to rotate · scroll to zoom · scale {scale_mm} mm</span></div>
  <div class="viewer-wrap">
    <canvas id="three-canvas"></canvas>
    <div class="viewer-hint">drag to rotate &nbsp;·&nbsp; scroll to zoom</div>
  </div>
  <div class="viewer-legend">{legend_items}
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {{
  var POINT_DATA = {point_json};
  var COLORS = {json.dumps(REGION_COLORS)};
  var UNCLASSIFIED = '#3d4455';

  var container = document.querySelector('.viewer-wrap');
  var W = container.clientWidth, H = 420;

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c14);

  var camera = new THREE.PerspectiveCamera(45, W / H, 0.001, 100);
  camera.position.set(0, 1.2, 2.8);

  var renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('three-canvas'), antialias: true }});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W, H);

  // Build point cloud
  var positions = [], colors = [];
  var col = new THREE.Color();
  for (var i = 0; i < POINT_DATA.length; i++) {{
    var p = POINT_DATA[i];
    positions.push(p[0], p[1], p[2]);
    col.set(p[3] < 0 ? UNCLASSIFIED : COLORS[p[3] % COLORS.length]);
    colors.push(col.r, col.g, col.b);
  }}
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color',    new THREE.Float32BufferAttribute(colors,    3));
  var mat = new THREE.PointsMaterial({{ size: 0.018, vertexColors: true, sizeAttenuation: true }});
  scene.add(new THREE.Points(geo, mat));

  // Manual orbit controls
  var theta = 0.4, phi = 1.1, radius = 3.0;
  var isDragging = false, lastX = 0, lastY = 0;

  function updateCamera() {{
    camera.position.set(
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.cos(theta)
    );
    camera.lookAt(0, 0, 0);
  }}
  updateCamera();

  var canvas = renderer.domElement;
  canvas.style.cursor = 'grab';
  canvas.addEventListener('mousedown', function (e) {{
    isDragging = true; lastX = e.clientX; lastY = e.clientY;
    canvas.style.cursor = 'grabbing';
  }});
  window.addEventListener('mouseup', function () {{
    isDragging = false; canvas.style.cursor = 'grab';
  }});
  window.addEventListener('mousemove', function (e) {{
    if (!isDragging) return;
    theta -= (e.clientX - lastX) * 0.008;
    phi    = Math.max(0.08, Math.min(Math.PI - 0.08, phi + (e.clientY - lastY) * 0.008));
    lastX  = e.clientX; lastY = e.clientY;
    updateCamera();
  }});
  canvas.addEventListener('wheel', function (e) {{
    radius = Math.max(0.8, Math.min(8.0, radius + e.deltaY * 0.003));
    updateCamera();
    e.preventDefault();
  }}, {{ passive: false }});

  function animate() {{ requestAnimationFrame(animate); renderer.render(scene, camera); }}
  animate();

  window.addEventListener('resize', function () {{
    var w = container.clientWidth;
    camera.aspect = w / H;
    camera.updateProjectionMatrix();
    renderer.setSize(w, H);
  }});
}})();
</script>"""


def _planar_section(regions: list) -> str:
    if not regions:
        return """
<div class="section">
  <div class="section-title">Planar Regions</div>
  <p style="color:var(--muted)">No regions extracted.</p>
</div>"""

    rows = ""
    for i, r in enumerate(regions):
        color = REGION_COLORS[i % len(REGION_COLORS)]
        area  = f"{r['area_m2_est']:.4f} m²" if r.get("area_m2_est") is not None else "—"
        frac  = f"{r.get('inlier_fraction', 0):.1%}"
        rms   = f"{r.get('fit_rms_mm', 0):.3f} mm"
        nx, ny, nz = (r.get("normal_xyz") or [0, 0, 0])
        rows += f"""
      <tr>
        <td><span class="region-dot" style="background:{color}"></span>{i+1}</td>
        <td class="num">{area}</td>
        <td class="num">{frac}</td>
        <td class="num">{rms}</td>
        <td class="num" style="color:var(--muted);font-size:11px">({nx:.3f}, {ny:.3f}, {nz:.3f})</td>
      </tr>"""

    return f"""
<div class="section">
  <div class="section-title">Planar Regions — RANSAC ({len(regions)} found)</div>
  <table class="data-table">
    <thead>
      <tr>
        <th>#</th>
        <th class="num">Area</th>
        <th class="num">Coverage</th>
        <th class="num">Fit RMS</th>
        <th class="num">Normal (x, y, z)</th>
      </tr>
    </thead>
    <tbody>{rows}
    </tbody>
  </table>
</div>"""


def _curvature_section(curv: dict) -> str:
    coarse = curv.get("coarse_mm", {})
    fine   = curv.get("fine_mm",   {})
    status = curv.get("data_status", "computed")

    if "error" in coarse or "mean_rad" not in coarse:
        return f"""
<div class="section">
  <div class="section-title">Surface Roughness {_badge(status)}</div>
  <p style="color:var(--muted)">Curvature could not be computed: {coarse.get('error','unknown error')}</p>
</div>"""

    coarse_mean = coarse["mean_rad"]
    fine_mean   = fine.get("mean_rad") if "mean_rad" in fine else None

    label, code, color = _roughness_grade(coarse_mean)

    # Roughness grade description (from standard)
    desc_map = {
        "Smooth":     "Cast / cut face — original formwork surface",
        "Moderate":   "Lightly textured — mild fracture or weathering",
        "Rough":      "Fractured surface — typical demolition break",
        "Very Rough": "Heavy fracture, spall, or aggregate exposure",
    }
    desc = desc_map.get(label, "")

    fine_str   = f"{fine_mean:.5f} rad" if fine_mean is not None else "—"
    coarse_str = f"{coarse_mean:.5f} rad"

    return f"""
<div class="section">
  <div class="section-title">Surface Roughness {_badge(status)}</div>
  <div class="roughness-card">
    <div class="roughness-code" style="color:{color}">{code}</div>
    <div>
      <div class="roughness-label" style="color:{color}">{label}</div>
      <div class="roughness-desc">{desc}</div>
    </div>
    <div class="roughness-nums">
      <span>Fine (r=20mm) &nbsp; {fine_str}</span>
      <span>Coarse (r=60mm) &nbsp; {coarse_str}</span>
    </div>
  </div>
  <div class="roughness-notice">
    Grade based on coarse-scale curvature mean · thresholds provisional — recalibrate after ≥10 fragments
  </div>
</div>"""


# ── Main entry points ─────────────────────────────────────────────────────────

def generate_report(data: dict, output_dir: Path, viewer_data: dict = None) -> Path:
    """
    Build a self-contained HTML descriptor report and write it to output_dir.

    Parameters
    ----------
    data        : output of run_phase2() — keys: fragment_id, bounding, planarity, curvature
    output_dir  : where to write the HTML file (same folder as the JSON)
    viewer_data : output of build_viewer_data() — point cloud for Three.js viewer

    Returns
    -------
    Path to the generated HTML file.
    """
    frag_id   = data.get("fragment_id", "unknown")
    version   = data.get("pipeline_version", "")
    timestamp = data.get("computed_at", "")
    bounding  = data.get("bounding", {})
    regions   = data.get("planarity", [])
    curvature = data.get("curvature", {})

    banner_html    = _mesh_banner(bounding)
    bounding_html  = _bounding_section(bounding)
    viewer_html    = _viewer_section(regions, viewer_data or {})
    planarity_html = _planar_section(regions)
    curvature_html = _curvature_section(curvature)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{frag_id} — Descriptor Report</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="report">

  <div class="header">
    <div>
      <h1>{frag_id}</h1>
      <div style="color:var(--muted);font-size:11px;margin-top:4px">
        Study 2 Descriptor Pipeline · {version}
      </div>
    </div>
    <div class="meta">
      {timestamp}<br>
      geometry descriptors
    </div>
  </div>

  {banner_html}
  {bounding_html}
  {viewer_html}
  {planarity_html}
  {curvature_html}

  <div style="margin-top:40px;color:var(--border);font-size:10px;text-align:right">
    Generated by Study2_Descriptor_Pipeline {version}
  </div>

</div>
</body>
</html>"""

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{frag_id}_report.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def open_report(path: Path) -> None:
    """Open the HTML report in the system default browser."""
    webbrowser.open(path.as_uri())
