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

import http.server
import json
import socket
import sys
import threading
import webbrowser
from pathlib import Path

# ── Taxonomy import ───────────────────────────────────────────────────────────
# Ensure 03_src/ is on sys.path so ai.taxonomy is importable even when
# report.py is imported before run_pipeline.py sets up sys.path.
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from ai.taxonomy import TAXONOMY, LABEL_COLORS as _LABEL_COLORS, LABEL_DESCRIPTIONS
except ImportError:
    # Absolute fallback — should never happen in normal usage
    _LABEL_COLORS = {
        "formwork_imprint":  "#60a5fa",
        "fracture_surface":  "#f87171",
        "exposed_aggregate": "#fbbf24",
        "rebar_visible":     "#f97316",
        "weathered":         "#a3e635",
        "staining":          "#c084fc",
        "original_finish":   "#34d399",
    }
    TAXONOMY = list(_LABEL_COLORS.keys())
    LABEL_DESCRIPTIONS = {k: "" for k in TAXONOMY}


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
.data-table tr.row-active td { background: rgba(124,131,253,0.18); }
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

# Candidate uses are computed into the record and are queryable via query.py,
# but are NOT shown in the interface: presenting a closed list of uses in the
# viewer would read as prescriptive and understate the open-ended vocabulary the
# descriptors support. Set True to surface them (e.g. for a figure).
SHOW_USE_SUGGESTIONS = False


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
      <div class="stat-label">Mass Estimate</div>
      <div class="stat-value">{_fmt(mass, 3)}<span class="stat-unit"> kg</span></div>
      <div class="stat-sub">@ 2400 kg/m³ concrete</div>
    </div>
  </div>
</div>"""


def _viewer_section(regions: list, viewer_data: dict,
                    glb_rel_path: str = "",
                    feat_tex_rels: dict = None,
                    grid_data: dict = None) -> str:
    """
    Build the 3D viewer section HTML + embedded Three.js script.

    feat_tex_rels : {"all": rel_path, "<label>": rel_path, ...}
                    produced by build_feature_textures() in feature_texture.py
    """
    feat_tex_rels = feat_tex_rels or {}
    if not viewer_data or not viewer_data.get("points"):
        return ""

    point_json  = json.dumps(viewer_data["points"])
    color_mode  = viewer_data.get("color_mode", "region")
    scale_mm    = viewer_data.get("scale_mm", "?")

    # ── RANSAC region legend (point cloud mode) ──────────────────────────────
    legend_items = ""
    for i, region in enumerate(regions):
        color    = REGION_COLORS[i % len(REGION_COLORS)]
        area     = region.get("area_m2_est")
        area_str = f"{area:.4f} m²" if area else "—"
        legend_items += (
            f'<div class="legend-item">'
            f'<div class="legend-dot" style="background:{color}"></div>'
            f'Region {i+1} · {area_str}</div>'
        )
    legend_items += (
        '<div class="legend-item">'
        '<div class="legend-dot" style="background:#3d4455"></div>Unclassified</div>'
    )
    if viewer_data.get("has_unscanned"):
        legend_items += (
            '<div class="legend-row">'
            '<div class="legend-dot" style="background:#94a3b8"></div>'
            'Unscanned (ground contact)</div>'
        )

    has_scan_js = "true" if color_mode == "scan" else "false"

    # ── Feature chip buttons ──────────────────────────────────────────────────
    # Show ALL taxonomy labels. Detected labels (with feature texture) are
    # coloured and clickable. Undetected labels are dimmed with a tooltip.
    detected_labels = [k for k in feat_tex_rels if k != "all"]
    chips_html = ""
    if feat_tex_rels:
        chips_html = '<div id="feat-chips" style="display:none;flex-wrap:wrap;gap:8px;margin-top:10px">'
        if detected_labels:
            chips_html += (
                '<button onclick="window.activateFeature(\'all\')" data-feat="all" '
                'style="background:#1e2030;border:1px solid #7c83fd;color:#7c83fd;'
                'font-size:11px;padding:4px 12px;border-radius:20px;cursor:pointer">All features</button>'
            )
        for lbl in TAXONOMY:
            col  = _LABEL_COLORS.get(lbl, "#b0b8d0")
            desc = LABEL_DESCRIPTIONS.get(lbl, "")
            if lbl in feat_tex_rels:
                # Detected — clickable, coloured
                chips_html += (
                    f'<button onclick="window.activateFeature(\'{lbl}\')" data-feat="{lbl}" '
                    f'title="{desc}" '
                    f'style="background:#1e2030;border:1px solid {col};color:{col};'
                    f'font-size:11px;padding:4px 12px;border-radius:20px;cursor:pointer">'
                    f'{lbl.replace("_", " ")}</button>'
                )
            else:
                # Not detected — dimmed, non-interactive
                chips_html += (
                    f'<span title="not detected — {desc}" '
                    f'style="background:#13151f;border:1px solid #252836;color:#3d4455;'
                    f'font-size:11px;padding:4px 12px;border-radius:20px;cursor:default;'
                    f'text-decoration:line-through">'
                    f'{lbl.replace("_", " ")}</span>'
                )
        chips_html += "</div>"

    # ── Overlay buttons inside canvas ─────────────────────────────────────────
    if glb_rel_path:
        mesh_toggle_btn = (
            '<button id="mesh-toggle" onclick="window.toggleMeshMode()" '
            'style="position:absolute;top:8px;left:8px;background:#1e2030;'
            'border:1px solid #7c83fd;color:#7c83fd;font-size:10px;'
            'padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Point Cloud</button>'
        )
        feature_main_btn = (
            '<button id="feature-btn" onclick="window.toggleFeaturePanel()" '
            'style="position:absolute;top:8px;right:8px;background:#1e2030;'
            'border:1px solid #fbbf24;color:#fbbf24;font-size:10px;'
            'padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Feature Map</button>'
        ) if feat_tex_rels else ""
        scan_toggle_btn = (
            '<button id="color-toggle" style="display:none;position:absolute;top:8px;right:8px;'
            'background:#1e2030;border:1px solid #3d4455;color:#b0b8d0;font-size:10px;'
            'padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Show Regions</button>'
        ) if color_mode == "scan" else ""
        gltf_script_tag = (
            '<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/'
            'examples/js/loaders/GLTFLoader.js"></script>'
        )

        # ── Serialise texture map for JS ─────────────────────────────────────
        feat_tex_js = json.dumps(feat_tex_rels)   # {"all": "path", "staining": "path", ...}

        # ── Grid classification data for vertex-colour feature overlay ────────
        # When present, mesh vertices are coloured by UV→cell→label directly
        # (16×16 quadrant-classified grid; labels follow the texture on the
        # 3D surface).
        if grid_data:
            grid_cells_js   = json.dumps(grid_data["cells"])
            grid_n_js       = str(grid_data["grid_n"])
        else:
            grid_cells_js   = "null"
            grid_n_js       = "8"
        taxonomy_idx_js = json.dumps({lbl: i for i, lbl in enumerate(TAXONOMY)})
        # UNSCANNED 3D test parameters (mesh-local space) — authoritative
        # opt-out of the reconstructed bottom face in the feature overlay.
        unsc_3d_js = json.dumps(viewer_data.get("unscanned_3d"))

        # ── Feature Labels button (point cloud mode, shown only when features exist) ──
        has_features    = viewer_data.get("has_features", False)
        has_features_js = json.dumps(has_features)
        feat_colors_js  = json.dumps([_LABEL_COLORS.get(lbl, "#b0b8d0") for lbl in TAXONOMY])
        feat_labels_btn = (
            '<button id="feat-labels-btn" onclick="window.toggleFeatureLabels()" '
            'style="display:none;position:absolute;top:8px;right:8px;background:#1e2030;'
            'border:1px solid #7c83fd;color:#7c83fd;font-size:10px;'
            'padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Feature Labels</button>'
        ) if has_features else ""

        glb_js = f"""

  // ── GLB textured mesh ─────────────────────────────────────────────────────
  var meshGroup    = null;
  var showMeshMode = true;
  var activeFeat   = null;

  // Grid classification — used to colour mesh vertices by UV→cell→label
  // (GRID_N × GRID_N global grid, quadrant-classified with majority voting).
  var GRID_CELLS     = {grid_cells_js};
  var GRID_N         = {grid_n_js};
  var TAXONOMY_INDEX = {taxonomy_idx_js};
  // UNSCANNED patch test in mesh-local space: {{normal, cos_angle, y_max}}
  var UNSC_3D        = {unsc_3d_js};

  (function loadGLB() {{
    var loader = new THREE.GLTFLoader();
    loader.load('{glb_rel_path}', function (gltf) {{
      meshGroup = gltf.scene;
      var box    = new THREE.Box3().setFromObject(meshGroup);
      var center = box.getCenter(new THREE.Vector3());
      var size   = box.getSize(new THREE.Vector3());
      var s = 2.0 / Math.max(size.x, size.y, size.z);
      meshGroup.scale.setScalar(s);
      meshGroup.position.copy(center).negate().multiplyScalar(s);
      scene.add(meshGroup);
      cloud.visible = false;
    }}, undefined, function (err) {{
      console.warn('GLB load failed — falling back to point cloud', err);
      cloud.visible = true;
      showMeshMode  = false;
      var fBtn = document.getElementById('feature-btn');
      if (fBtn) fBtn.style.display = 'none';
    }});
  }})();

  // ── Feature overlay (per-vertex UV → grid cell → label) ──────────────────
  //
  // Each vertex looks up its own UV coordinate in the GRID_N × GRID_N
  // classification grid and takes that cell's label. Labels therefore sit
  // exactly where the classified texture sits on the 3D surface — no
  // spatial-grid smearing, no bbox-aligned blocks. The finer grid (16×16,
  // quadrant-classified with majority voting) keeps cell labels reliable
  // enough that UV-island boundaries no longer fragment the result.
  //
  // UNSCANNED handling: majority-patch UV cells are cleared to null in Phase
  // 3B, and additionally every vertex on the patched bottom face is forced
  // unlabeled by the UNSC_3D normal + height test (mesh-local space) — the
  // patch scatters into many UV cells at trace coverage, so cell-clearing
  // alone cannot opt it out.

  function _applyFeatureVertexColors(targetLabel) {{
    if (!meshGroup || !GRID_CELLS) return;
    var c = new THREE.Color();
    var cosLim = UNSC_3D ? UNSC_3D.cos_angle : 0;
    var unx = UNSC_3D ? UNSC_3D.normal[0] : 0,
        uny = UNSC_3D ? UNSC_3D.normal[1] : 0,
        unz = UNSC_3D ? UNSC_3D.normal[2] : 0;
    // World-space height cut: GLB node transforms + viewer scaling make local
    // Y meaningless, so the cut is a fraction of the world bbox vertical span.
    var yLim = -Infinity;
    if (UNSC_3D) {{
      meshGroup.updateMatrixWorld(true);
      var wb = new THREE.Box3().setFromObject(meshGroup);
      yLim = wb.min.y + UNSC_3D.y_frac * (wb.max.y - wb.min.y);
    }}
    var wPos = new THREE.Vector3();
    var wNrm = new THREE.Vector3();
    var nMat = new THREE.Matrix3();

    meshGroup.traverse(function (child) {{
      if (!child.isMesh) return;
      var geo     = child.geometry;
      var posAttr = geo.attributes.position;
      var uvAttr  = geo.attributes.uv;
      var nrmAttr = geo.attributes.normal;
      if (!posAttr || !uvAttr) return;
      var mat = child.material;
      if (mat._origMap === undefined) mat._origMap = mat.map;
      if (mat._origVC  === undefined) mat._origVC  = mat.vertexColors;
      var wMat = child.matrixWorld;
      nMat.getNormalMatrix(wMat);
      var n      = posAttr.count;
      var colArr = new Float32Array(n * 3);
      for (var i = 0; i < n; i++) {{
        var u   = Math.max(0, Math.min(1, uvAttr.getX(i)));
        var v   = Math.max(0, Math.min(1, uvAttr.getY(i)));
        var ugc = Math.min(Math.floor(u * GRID_N), GRID_N - 1);
        var ugr = Math.min(Math.floor(v * GRID_N), GRID_N - 1);
        var lbl = GRID_CELLS[ugr][ugc];
        // UNSCANNED patch opt-out (world-space normal + height test)
        if (lbl && UNSC_3D && nrmAttr) {{
          wPos.fromBufferAttribute(posAttr, i).applyMatrix4(wMat);
          if (wPos.y <= yLim) {{
            wNrm.fromBufferAttribute(nrmAttr, i).applyMatrix3(nMat).normalize();
            var dot = Math.abs(wNrm.x * unx + wNrm.y * uny + wNrm.z * unz);
            if (dot >= cosLim) lbl = null;
          }}
        }}
        var fid = (lbl && TAXONOMY_INDEX[lbl] !== undefined) ? TAXONOMY_INDEX[lbl] : -1;
        if (targetLabel === 'all') {{
          c.set(fid >= 0 ? FEAT_COLORS[fid] : '#111318');
        }} else {{
          if (lbl === targetLabel && fid >= 0) c.set(FEAT_COLORS[fid]);
          else if (fid >= 0)                   c.set('#1e1e26');
          else                                 c.set('#111318');
        }}
        colArr[i*3] = c.r; colArr[i*3+1] = c.g; colArr[i*3+2] = c.b;
      }}
      geo.setAttribute('color', new THREE.Float32BufferAttribute(colArr, 3));
      mat.vertexColors = true;
      mat.map          = null;
      mat.needsUpdate  = true;
    }});
  }}

  function _restoreOrigMesh() {{
    if (!meshGroup) return;
    meshGroup.traverse(function (child) {{
      if (!child.isMesh || !child.material) return;
      var mat = child.material;
      mat.map          = mat._origMap !== undefined ? mat._origMap : mat.map;
      mat.vertexColors = mat._origVC  !== undefined ? mat._origVC  : false;
      mat.needsUpdate  = true;
    }});
  }}

  // ── Feature chip activation ───────────────────────────────────────────────
  window.activateFeature = function (label) {{
    activeFeat = label;
    _applyFeatureVertexColors(label);
    document.querySelectorAll('#feat-chips button').forEach(function (b) {{
      var isActive = b.dataset.feat === label;
      b.style.background = isActive ? '#2d3250' : '#1e2030';
      b.style.fontWeight  = isActive ? 'bold' : 'normal';
    }});
  }};

  // ── Feature panel toggle (top-right button) ───────────────────────────────
  var featurePanelOpen = false;
  window.toggleFeaturePanel = function () {{
    featurePanelOpen = !featurePanelOpen;
    var chips = document.getElementById('feat-chips');
    var btn   = document.getElementById('feature-btn');
    if (chips) chips.style.display = featurePanelOpen ? 'flex' : 'none';
    if (btn)   btn.textContent     = featurePanelOpen ? 'Hide Features' : 'Feature Map';
    if (featurePanelOpen) {{
      if (!activeFeat) window.activateFeature('all');
    }} else {{
      activeFeat = null;
      _restoreOrigMesh();
      document.querySelectorAll('#feat-chips button').forEach(function (b) {{
        b.style.background = '#1e2030';
        b.style.fontWeight  = 'normal';
      }});
    }}
  }};

  // ── Mesh / Point Cloud toggle ─────────────────────────────────────────────
  window.toggleMeshMode = function () {{
    if (!meshGroup) return;
    showMeshMode  = !showMeshMode;
    meshGroup.visible = showMeshMode;
    cloud.visible     = !showMeshMode;
    document.getElementById('mesh-toggle').textContent = showMeshMode ? 'Point Cloud' : 'Textured Mesh';
    if (!showMeshMode && featurePanelOpen) window.toggleFeaturePanel();
    if (showMeshMode && showFeatureLabels) window.toggleFeatureLabels();
    var leg   = document.getElementById('viewer-legend');
    if (leg)  leg.style.display = (!showMeshMode && curMode === 'region' && !showFeatureLabels) ? '' : 'none';
    var ctBtn = document.getElementById('color-toggle');
    if (ctBtn) ctBtn.style.display = (!showMeshMode && {has_scan_js}) ? '' : 'none';
    var fBtn  = document.getElementById('feature-btn');
    if (fBtn)  fBtn.style.display = showMeshMode && {json.dumps(bool(feat_tex_rels))}.toString() === 'true' ? '' : 'none';
    var flBtn = document.getElementById('feat-labels-btn');
    if (flBtn) flBtn.style.display = (!showMeshMode && HAS_FEATURES) ? '' : 'none';
  }};
"""
    else:
        mesh_toggle_btn  = ""
        feature_main_btn = ""
        feat_labels_btn  = ""
        gltf_script_tag  = ""
        glb_js           = ""
        has_features     = False
        has_features_js  = "false"
        feat_colors_js   = json.dumps([_LABEL_COLORS.get(lbl, "#b0b8d0") for lbl in TAXONOMY])
        grid_cells_js    = "null"
        grid_n_js        = "8"
        taxonomy_idx_js  = json.dumps({lbl: i for i, lbl in enumerate(TAXONOMY)})
        scan_toggle_btn  = (
            '<button id="color-toggle" style="position:absolute;top:8px;right:8px;'
            'background:#1e2030;border:1px solid #3d4455;color:#b0b8d0;font-size:10px;'
            'padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Show Regions</button>'
        ) if color_mode == "scan" else ""

    # ── Feature legend (shown in Feature Labels point-cloud mode) ────────────
    if has_features:
        _fl_items = "".join(
            f'<div class="legend-item">'
            f'<div class="legend-dot" style="background:{_LABEL_COLORS.get(lbl, "#b0b8d0")}"></div>'
            f'{lbl.replace("_", " ")}</div>'
            for lbl in TAXONOMY
        ) + '<div class="legend-item"><div class="legend-dot" style="background:#111318"></div>Unlabeled</div>'
        feat_legend_html = (
            f'<div class="viewer-legend" id="feat-legend" style="display:none">{_fl_items}</div>'
        )
    else:
        feat_legend_html = ""

    return f"""
<div class="section">
  <div class="section-title">3D Viewer <span style="font-size:10px;color:#3d4455;text-transform:none;letter-spacing:0">— drag to rotate · scroll to zoom · scale {scale_mm} mm</span></div>
  <div class="viewer-wrap">
    <canvas id="three-canvas"></canvas>
    <div class="viewer-hint">drag to rotate &nbsp;·&nbsp; scroll to zoom</div>
    {mesh_toggle_btn}
    {feature_main_btn}
    {feat_labels_btn}
    {scan_toggle_btn}
  </div>
  <div class="viewer-legend" id="viewer-legend" style="display:none">{legend_items}</div>
  {feat_legend_html}
  {chips_html}
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
{gltf_script_tag}
<script>
(function () {{
  var POINT_DATA   = {point_json};
  var HAS_SCAN     = {has_scan_js};
  var HAS_FEATURES = {has_features_js};
  var COLORS       = {json.dumps(REGION_COLORS)};
  var FEAT_COLORS  = {feat_colors_js};
  var UNCLASSIFIED = '#3d4455';
  var curMode      = '{color_mode}';

  var container = document.querySelector('.viewer-wrap');
  var W = container.clientWidth, H = 420;
  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c14);
  // Lights — required for MeshStandardMaterial (GLTF default); without these the mesh renders black
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  var _key = new THREE.DirectionalLight(0xffffff, 0.85);
  _key.position.set(1.5, 2.5, 2.0);
  scene.add(_key);
  var _fill = new THREE.DirectionalLight(0xffffff, 0.25);
  _fill.position.set(-1.5, 0.5, -1.5);
  scene.add(_fill);
  var camera = new THREE.PerspectiveCamera(45, W / H, 0.001, 100);
  camera.position.set(0, 1.2, 2.8);
  var renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('three-canvas'), antialias: true }});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W, H);
  renderer.outputEncoding = THREE.sRGBEncoding;

  var UNSCANNED_ID    = 100;
  var UNSCANNED_COLOR = '#94a3b8';   // grey-blue — ground-contact face (not scanned)

  var positions = [], scanColors = [], regionColors = [], featureColors = [];
  var showFeatureLabels = false;
  var col = new THREE.Color();
  for (var i = 0; i < POINT_DATA.length; i++) {{
    var p = POINT_DATA[i];
    positions.push(p[0], p[1], p[2]);
    if (HAS_SCAN && p.length >= 8)      col.setRGB(p[5], p[6], p[7]);
    else if (HAS_SCAN && p.length === 7) col.setRGB(p[4], p[5], p[6]);
    else col.set(p[3] === UNSCANNED_ID ? UNSCANNED_COLOR : (p[3] < 0 ? UNCLASSIFIED : COLORS[p[3] % COLORS.length]));
    scanColors.push(col.r, col.g, col.b);
    col.set(p[3] === UNSCANNED_ID ? UNSCANNED_COLOR : (p[3] < 0 ? UNCLASSIFIED : COLORS[p[3] % COLORS.length]));
    regionColors.push(col.r, col.g, col.b);
    // Feature label colour: UNSCANNED stays grey, labeled points → FEAT_COLORS[fid], unlabeled → near-black
    var fid = (p.length === 5 || p.length >= 8) ? p[4] : -1;
    if (p[3] === UNSCANNED_ID) col.set(UNSCANNED_COLOR);
    else if (fid >= 0 && fid < FEAT_COLORS.length) col.set(FEAT_COLORS[fid]);
    else col.set('#111318');
    featureColors.push(col.r, col.g, col.b);
  }}
  var geo  = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(
    (curMode === 'scan' && HAS_SCAN) ? scanColors : regionColors, 3));
  var mat   = new THREE.PointsMaterial({{ size: 0.018, vertexColors: true, sizeAttenuation: true }});
  var cloud = new THREE.Points(geo, mat);
  scene.add(cloud);

  var scanBtn = document.getElementById('color-toggle');
  if (scanBtn) scanBtn.addEventListener('click', function () {{
    curMode = curMode === 'scan' ? 'region' : 'scan';
    var arr = (curMode === 'scan' && HAS_SCAN) ? scanColors : regionColors;
    cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(arr, 3));
    scanBtn.textContent = curMode === 'scan' ? 'Show Regions' : 'Show Scan';
    var leg = document.getElementById('viewer-legend');
    if (leg) leg.style.display = curMode === 'region' ? '' : 'none';
  }});

  var theta = 0.4, phi = 1.1, radius = 3.0, isDragging = false, lastX = 0, lastY = 0;
  function updateCamera() {{
    camera.position.set(
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.cos(theta));
    camera.lookAt(0, 0, 0);
  }}
  updateCamera();
  var cvs = renderer.domElement;
  cvs.style.cursor = 'grab';
  cvs.addEventListener('mousedown',   function (e) {{ isDragging = true;  lastX = e.clientX; lastY = e.clientY; cvs.style.cursor = 'grabbing'; }});
  window.addEventListener('mouseup',  function ()  {{ isDragging = false; cvs.style.cursor = 'grab'; }});
  window.addEventListener('mousemove', function (e) {{
    if (!isDragging) return;
    theta -= (e.clientX - lastX) * 0.008;
    phi    = Math.max(0.08, Math.min(Math.PI - 0.08, phi + (e.clientY - lastY) * 0.008));
    lastX = e.clientX; lastY = e.clientY;
    updateCamera();
  }});
  cvs.addEventListener('wheel', function (e) {{
    radius = Math.max(0.8, Math.min(8.0, radius + e.deltaY * 0.003));
    updateCamera(); e.preventDefault();
  }}, {{ passive: false }});
  function animate() {{ requestAnimationFrame(animate); renderer.render(scene, camera); }}
  animate();
  window.addEventListener('resize', function () {{
    var w = container.clientWidth;
    camera.aspect = w / H; camera.updateProjectionMatrix(); renderer.setSize(w, H);
  }});

  var curHighlight = null, hlCol = new THREE.Color();
  window.highlightRegion = function (regionId) {{
    if (curHighlight === regionId) {{
      curHighlight = null;
      var restore = (curMode === 'scan' && HAS_SCAN) ? scanColors : regionColors;
      cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(restore, 3));
      document.querySelectorAll('.region-row').forEach(function (r) {{ r.classList.remove('row-active'); }});
      return;
    }}
    curHighlight = regionId;
    var arr = [];
    for (var j = 0; j < POINT_DATA.length; j++) {{
      var p = POINT_DATA[j];
      hlCol.set(p[3] === regionId ? COLORS[regionId % COLORS.length] : '#111318');
      arr.push(hlCol.r, hlCol.g, hlCol.b);
    }}
    cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(arr, 3));
    document.querySelectorAll('.region-row').forEach(function (r) {{
      r.classList.toggle('row-active', parseInt(r.dataset.regionId) === regionId);
    }});
  }};

  // ── Feature Labels colour mode (point cloud) ──────────────────────────────
  // Colours each sampled point by its 8×8 grid feature label rather than
  // RANSAC region — shows the true spatial distribution of surface features.
  window.toggleFeatureLabels = function () {{
    showFeatureLabels = !showFeatureLabels;
    var arr = showFeatureLabels ? featureColors : regionColors;
    cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(arr, 3));
    var btn = document.getElementById('feat-labels-btn');
    if (btn) {{
      btn.textContent       = showFeatureLabels ? 'Region Colors' : 'Feature Labels';
      btn.style.color       = showFeatureLabels ? '#fbbf24' : '#7c83fd';
      btn.style.borderColor = showFeatureLabels ? '#fbbf24' : '#7c83fd';
    }}
    var leg  = document.getElementById('viewer-legend');
    var fleg = document.getElementById('feat-legend');
    if (showFeatureLabels) {{
      if (leg)  leg.style.display  = 'none';
      if (fleg) fleg.style.display = '';
    }} else {{
      if (leg)  leg.style.display  = (curMode === 'region') ? '' : 'none';
      if (fleg) fleg.style.display = 'none';
    }}
  }};
{glb_js}
}})();
</script>"""


def _procedural_section(proc: dict, vision: dict) -> str:
    """Fragment-level design factors + how many faces were classified vs inferred."""
    if not proc:
        return ""
    h    = proc.get("handling_class") or {}
    hv   = h.get("value") or "—"
    hr   = h.get("reason") or ""
    coverage = ""

    regions_html = ""
    for r in (vision or {}).get("regions", []) or []:
        skipped = r.get("skipped")
        coh     = r.get("uv_coherence")
        note    = (f'<span style="color:var(--warning)">not classified ({skipped}, '
                   f'coherence {coh})</span>') if skipped else (r.get("label") or "—")
        an = len(r.get("anomalies") or [])
        regions_html += f"""
      <tr>
        <td>#{r.get('region_id')}</td>
        <td style="font-size:11px">{r.get('kind','')}</td>
        <td class="num">{(r.get('area_frac') or 0)*100:.1f}%</td>
        <td style="font-size:11px">{note}</td>
        <td class="num">{an if an else '—'}</td>
      </tr>"""
    regions_table = f"""
  <table class="data-table" style="margin-top:12px">
    <thead><tr><th>Region</th><th>Kind</th><th class="num">Area</th>
      <th>Label</th><th class="num">Anomalies</th></tr></thead>
    <tbody>{regions_html}</tbody>
  </table>""" if regions_html else ""

    # ── Design implications: combinations of descriptors → candidate uses ────
    uses = (proc.get("use_suggestions") or []) if SHOW_USE_SUGGESTIONS else []
    if uses:
        cards = ""
        for u in uses:
            faces_txt = ", ".join(f"region {i+1}" for i in u.get("faces", []))
            caveat = (f'<div style="font-size:10px;color:var(--warning);margin-top:4px">'
                      f'{u["caveat"]}</div>') if u.get("caveat") else ""
            cards += f"""
      <div style="border:1px solid var(--line);border-radius:6px;padding:10px 12px;
                  background:#15171f">
        <div style="font-size:13px;font-weight:bold;color:var(--text)">{u['label']}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px">{u['note']}</div>
        <div style="font-size:11px;color:var(--accent);margin-top:5px">satisfied by {faces_txt}</div>
        {caveat}
      </div>"""
        uses_html = f"""
  <div style="margin-top:14px">
    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;
                letter-spacing:0.06em;margin-bottom:8px">Candidate uses {_badge('proposed')}</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px">{cards}
    </div>
  </div>"""
    else:
        uses_html = ("""
  <div style="margin-top:14px;font-size:11px;color:var(--muted)">
    No candidate use met its conditions for this fragment.</div>"""
            if SHOW_USE_SUGGESTIONS else "")

    return f"""
<div class="section">
  <div class="section-title">Design Factors {_badge('proposed')}
    <span style="font-size:10px;color:var(--muted);text-transform:none;letter-spacing:0">
      — derived from encoded links, provisional and not expert-verified</span></div>
  <div class="stat-grid">
    <div class="stat-block">
      <div class="stat-label">Handling class</div>
      <div class="stat-value" style="font-size:18px">{hv}</div>
      <div style="font-size:11px;color:var(--muted)">{hr}</div>
    </div>{coverage}
  </div>{uses_html}{regions_table}
</div>"""


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
        lbl   = r.get("surface_label") or "—"
        proc  = r.get("procedural") or {}
        conn  = (proc.get("connection_strategy") or {}).get("value") or "—"
        asg   = (proc.get("design_assignment") or {}).get("value") or "—"
        conn_t = (proc.get("connection_strategy") or {}).get("rule") or ""
        asg_t  = (proc.get("design_assignment") or {}).get("rule") or ""
        rel   = "" if r.get("scan_reliable", True) else (
                ' <span style="color:var(--warning);font-size:10px">unscanned</span>')
        rows += f"""
      <tr class="region-row" data-region-id="{i}" onclick="highlightRegion({i})" style="cursor:pointer">
        <td><span class="region-dot" style="background:{color}"></span>{i+1}{rel}</td>
        <td class="num">{area}</td>
        <td class="num">{frac}</td>
        <td class="num">{rms}</td>
        <td style="font-size:11px">{lbl}</td>
        <td style="font-size:11px" title="{conn_t}">{conn}</td>
        <td style="font-size:11px" title="{asg_t}">{asg}</td>
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
        <th>Surface</th>
        <th>Connection <span class="badge badge-pseudo">proposed</span></th>
        <th>Assignment <span class="badge badge-pseudo">proposed</span></th>
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


# ── Vision section ───────────────────────────────────────────────────────────
# _LABEL_COLORS and TAXONOMY are imported from ai.taxonomy at the top of this file.

def _vision_section(vision: dict, texture_rel_path: str = "") -> str:
    if not vision or vision.get("parse_error"):
        return ""

    dominant   = vision.get("dominant_label", "—")
    dom_color  = _LABEL_COLORS.get(dominant, "#b0b8d0")
    labels     = vision.get("labels_present", [])
    coverage   = vision.get("label_coverage", {})
    cracks     = vision.get("cracks", {})
    aggregate  = vision.get("aggregate", {})
    condition  = vision.get("surface_condition", "—")
    color_note = vision.get("color_notes", "")
    reuse_note = vision.get("reuse_notes", "")
    confidence = vision.get("confidence", "—")
    provider   = vision.get("provider", "")
    model      = vision.get("model", "")
    n_runs     = vision.get("n_runs", "—")

    condition_color = {"good": "#4ade80", "moderate": "#fbbf24", "poor": "#f87171"}.get(condition, "#b0b8d0")
    conf_color      = {"high": "#4ade80", "medium": "#fbbf24", "low": "#f87171"}.get(confidence, "#b0b8d0")

    # Coverage bars with subtype + notes
    label_details = vision.get("label_details", {})
    bars = ""
    for label in TAXONOMY:
        pct = coverage.get(label, 0)
        if pct == 0:
            continue
        col    = _LABEL_COLORS.get(label, "#b0b8d0")
        detail = label_details.get(label, {})
        subtype = detail.get("subtype", "")
        notes   = detail.get("notes", "")
        subtype_html = ""
        if subtype and subtype != "unknown":
            subtype_html = (
                f'<span style="background:{col}22;color:{col};font-size:9px;'
                f'padding:1px 6px;border-radius:10px;margin-left:6px;'
                f'font-weight:600;letter-spacing:0.04em">'
                f'{subtype.replace("_", " ")}</span>'
            )
        notes_html = (
            f'<div style="font-size:10px;color:var(--muted);margin-top:3px;'
            f'font-style:italic;padding-left:2px">{notes}</div>'
            if notes else ""
        )
        bars += f"""
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;margin-bottom:3px">
        <span style="color:{col}">{label.replace('_',' ')}{subtype_html}</span>
        <span style="color:var(--muted)">{pct}%</span>
      </div>
      <div style="background:#1e2030;border-radius:3px;height:6px">
        <div style="background:{col};width:{pct}%;height:6px;border-radius:3px"></div>
      </div>
      {notes_html}
    </div>"""

    crack_html = ""
    if cracks.get("present"):
        crack_html = f"""
    <div class="stat-card" style="border-color:#f87171">
      <div class="stat-label">Cracks</div>
      <div class="stat-value" style="font-size:14px;color:#f87171">{cracks.get('pattern','—')}</div>
      <div class="stat-sub">{cracks.get('coverage_pct', 0)}% surface coverage</div>
    </div>"""

    agg_html = ""
    if aggregate.get("visible"):
        agg_html = f"""
    <div class="stat-card">
      <div class="stat-label">Aggregate</div>
      <div class="stat-value" style="font-size:14px">{aggregate.get('estimated_size','—')}</div>
      <div class="stat-sub">size class</div>
    </div>"""

    # Texture image preview
    texture_html = ""
    if texture_rel_path:
        texture_html = f"""
  <div style="margin-bottom:16px">
    <div style="font-size:11px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em">Texture Map</div>
    <img src="{texture_rel_path}" style="width:100%;max-height:280px;object-fit:contain;border-radius:6px;border:1px solid var(--border);background:#0a0c14" alt="Fragment texture map">
  </div>"""

    return f"""
<div class="section">
  <div class="section-title">Surface Vision Analysis
    <span style="font-size:10px;color:var(--muted);text-transform:none;letter-spacing:0">
      — {provider}/{model} · {n_runs}× majority vote
    </span>
  </div>

  {texture_html}

  <div class="stat-row" style="margin-bottom:16px">
    <div class="stat-card">
      <div class="stat-label">Dominant Surface</div>
      <div class="stat-value" style="font-size:14px;color:{dom_color}">{dominant.replace('_',' ')}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Surface Condition</div>
      <div class="stat-value" style="font-size:16px;color:{condition_color}">{condition}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Confidence</div>
      <div class="stat-value" style="font-size:16px;color:{conf_color}">{confidence}</div>
    </div>
    {crack_html}
    {agg_html}
  </div>

  <div style="margin-bottom:16px">
    <div style="font-size:11px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em">Surface Coverage</div>
    {bars}
  </div>

  {"<div class='stat-sub' style='margin-bottom:8px'><b style='color:var(--fg)'>Color:</b> " + color_note + "</div>" if color_note else ""}
  {"<div class='stat-sub'><b style='color:var(--fg)'>Reuse notes:</b> " + reuse_note + "</div>" if reuse_note else ""}
</div>"""


# ── Main entry points ─────────────────────────────────────────────────────────

def generate_report(data: dict, output_dir: Path, viewer_data: dict = None,
                    glb_path: Path = None, texture_path: Path = None,
                    feature_texture_paths: dict = None) -> Path:
    """
    Build a self-contained HTML descriptor report and write it to output_dir.

    Parameters
    ----------
    data                  : output of run_phase2()
    output_dir            : where to write the HTML file
    viewer_data           : output of build_viewer_data() — point cloud for Three.js
    glb_path              : optional Path to the textured .glb — 3D viewer default
    texture_path          : optional Path to texture PNG — shown in vision section
    feature_texture_paths : dict from build_feature_textures():
                            {"all": Path, "<label>": Path, ...}

    Returns
    -------
    Path to the generated HTML file.
    """
    import os as _os
    feature_texture_paths = feature_texture_paths or {}

    frag_id        = data.get("fragment_id", "unknown")
    archetype_code = data.get("archetype", "")
    archetype_label= data.get("archetype_label", "")
    version        = data.get("pipeline_version", "")
    timestamp      = data.get("computed_at", "")
    bounding       = data.get("bounding", {})
    regions        = data.get("planarity", [])
    curvature      = data.get("curvature", {})
    vision         = data.get("vision", {})
    procedural     = data.get("procedural", {})

    def _rel(p):
        return _os.path.relpath(p, output_dir).replace("\\", "/") if p and Path(p).exists() else ""

    glb_rel = _rel(glb_path)
    tex_rel = _rel(texture_path)

    # Build relative paths for all feature textures
    feat_tex_rels = {k: _rel(v) for k, v in feature_texture_paths.items() if _rel(v)}

    # Grid classification data for vertex-colour feature overlay in the viewer
    grid_data = vision.get("grid_classification") if vision else None

    banner_html    = _mesh_banner(bounding)
    bounding_html  = _bounding_section(bounding)
    viewer_html    = _viewer_section(regions, viewer_data or {},
                                     glb_rel_path=glb_rel,
                                     feat_tex_rels=feat_tex_rels,
                                     grid_data=grid_data)
    planarity_html = _planar_section(regions)
    curvature_html = _curvature_section(curvature)
    vision_html    = _vision_section(vision, texture_rel_path=tex_rel)
    procedural_html= _procedural_section(procedural, vision)

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
      <div style="display:flex;align-items:center;gap:10px;margin-top:6px">
        {f'<span style="background:#1e293b;border:1px solid var(--border);border-radius:4px;padding:2px 8px;font-size:11px;color:var(--accent);font-weight:600;letter-spacing:0.06em">{archetype_code}</span><span style="color:var(--muted);font-size:11px">{archetype_label}</span>' if archetype_code else ''}
      </div>
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
  {vision_html}
  {procedural_html}

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
    """
    Serve the output folder via a local HTTP server and open the report.

    Chrome blocks XMLHttpRequest on file:// URLs even within the same directory,
    which prevents Three.js from loading the GLB mesh.  Serving via HTTP avoids
    this restriction entirely and makes all assets (GLB, PNGs) load correctly.
    """
    serve_dir = path.parent

    # Find a free ephemeral port
    with socket.socket() as _s:
        _s.bind(("", 0))
        port = _s.getsockname()[1]

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def log_message(self, fmt, *args):  # silence access log spam
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/{path.name}"
    print(f"\n  Report served at: {url}")
    webbrowser.open(url)

    print("  (Keep this terminal open while viewing — server exits when you press Enter)")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        server.shutdown()


# ── Collective inventory interface ────────────────────────────────────────────

_INDEX_CSS = """
:root {
  --bg:      #0f1117;
  --surface: #1a1d2e;
  --border:  #2d3250;
  --accent:  #7c83fd;
  --text:    #e2e8f0;
  --muted:   #94a3b8;
  --hover:   #1f2340;
  --radius:  8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'SF Mono','Cascadia Code','Fira Mono',monospace;
  font-size: 13px;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Top bar ── */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.topbar h1 { font-size: 15px; color: var(--accent); letter-spacing: 0.05em; }
.topbar .count { font-size: 11px; color: var(--muted); }

/* ── Two-panel layout ── */
.panels {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Viewer in detail panel ── */
#viewer-wrap {
  position: relative;
  background: #0a0c14;
  border-bottom: 1px solid var(--border);
  height: 280px;
  flex-shrink: 0;
  display: none;
}
#idx-canvas { display: block; width: 100%; height: 100%; }
.viewer-hint-idx {
  position: absolute;
  bottom: 8px; left: 50%; transform: translateX(-50%);
  background: rgba(0,0,0,0.55);
  color: var(--muted); font-size: 10px;
  padding: 2px 8px; border-radius: 99px;
  pointer-events: none; white-space: nowrap;
}
#viewer-legend-idx {
  display: none;
  flex-wrap: wrap; gap: 6px;
  padding: 7px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}

/* ── Left: fragment list ── */
.frag-list {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 8px;
}
.frag-item {
  padding: 10px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 4px;
  transition: background 0.1s;
}
.frag-item:hover { background: var(--hover); }
.frag-item.active {
  background: var(--hover);
  border-color: var(--accent);
}
.frag-id {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.frag-id span { font-size: 12px; font-weight: 600; color: var(--text); }
.grade-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 99px;
}
.frag-dims { font-size: 11px; color: var(--muted); }
.frag-meta { font-size: 10px; color: #4b5563; margin-top: 2px; }

/* ── Right: detail panel ── */
.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
#detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}
.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
  font-size: 12px;
}

/* ── Detail sections ── */
.detail-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.detail-header h2 { font-size: 18px; color: var(--accent); letter-spacing: 0.05em; }
.detail-header .open-link {
  font-size: 11px;
  color: var(--muted);
  text-decoration: none;
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--radius);
}
.detail-header .open-link:hover { color: var(--text); border-color: var(--accent); }

.dsection { margin-bottom: 24px; }
.dsection-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
}

.stat-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.stat-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  min-width: 130px;
}
.chip-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 2px; }
.chip-val   { font-size: 15px; font-weight: 600; }
.chip-sub   { font-size: 10px; color: var(--muted); }

.roughness-row {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
}
.rgrade-code  { font-size: 24px; font-weight: 700; }
.rgrade-label { font-size: 13px; font-weight: 600; }
.rgrade-desc  { font-size: 11px; color: var(--muted); }
.rgrade-nums  { margin-left: auto; font-size: 11px; color: var(--muted); text-align: right; }

.mesh-warn {
  background: #2d1b00;
  border: 1px solid #92400e;
  border-left: 3px solid #fbbf24;
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 11px;
  color: #fde68a;
  margin-bottom: 12px;
}

.dtable {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  font-size: 12px;
}
.dtable th {
  background: #12152a;
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  padding: 7px 10px;
  text-align: left;
}
.dtable td { padding: 7px 10px; border-top: 1px solid var(--border); }
.dtable tr:hover td { background: var(--hover); }
.dtable tr.row-active-idx td { background: rgba(124,131,253,0.18); }
.nr { text-align: right; font-variant-numeric: tabular-nums; }
.rdot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
"""

_INDEX_JS = """
const REGION_COLORS = [
  '#7c83fd','#4ade80','#fbbf24','#f87171',
  '#60a5fa','#c084fc','#fb923c','#34d399'
];
const UNSCANNED_ID    = 100;
const UNSCANNED_COLOR = '#94a3b8';   // grey-blue — ground-contact face (not scanned)

const ROUGHNESS_GRADES = {
  S:  { label: 'Smooth',     color: '#4ade80' },
  M:  { label: 'Moderate',   color: '#a3e635' },
  R:  { label: 'Rough',      color: '#fbbf24' },
  VR: { label: 'Very Rough', color: '#f87171' },
};

const DESC_MAP = {
  S:  'Cast / cut face — original formwork surface',
  M:  'Lightly textured — mild fracture or weathering',
  R:  'Fractured surface — typical demolition break',
  VR: 'Heavy fracture, spall, or aggregate exposure',
};

function getGrade(coarse_mean) {
  if (coarse_mean === null || coarse_mean === undefined) return null;
  if (coarse_mean < 0.25) return 'S';
  if (coarse_mean < 0.45) return 'M';
  if (coarse_mean < 0.65) return 'R';
  return 'VR';
}

function fmt(v, d, unit) {
  if (v === null || v === undefined) return '—';
  return v.toFixed(d) + (unit ? ' ' + unit : '');
}

// ── Intended design use: chips on each card, and a filter over the list ──────
// The uses come from the encoded design factors and are proposals, not verified
// assignments; the filter selects fragments whose record offers a given use.
var useFilter = '';
var SHOW_USES = {show_uses_js};   // candidate uses hidden in the interface by default

function fragUses(f) {
  return ((f.procedural || {}).use_suggestions) || [];
}

function useChips(f) {
  var us = fragUses(f);
  if (!us.length) return '';
  return '<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:3px">' +
    us.map(function(u) {
      var on = useFilter && u.id === useFilter;
      return '<span style="font-size:9px;padding:1px 5px;border-radius:8px;' +
        'background:' + (on ? '#2d3250' : '#1b1e29') + ';color:' + (on ? '#9aa4ff' : '#6b7280') +
        ';border:1px solid ' + (on ? '#7c83fd' : '#262a36') + '">' + u.label + '</span>';
    }).join('') + '</div>';
}

function buildUseFilter(fragments) {
  var sel = document.getElementById('use-filter');
  if (!sel) return;
  var box = document.getElementById('use-filter-box');
  if (!SHOW_USES) { if (box) box.style.display = 'none'; return; }
  var seen = {};
  fragments.forEach(function(f) {
    fragUses(f).forEach(function(u) { seen[u.id] = u.label; });
  });
  var opts = ['<option value="">All fragments</option>'];
  Object.keys(seen).sort().forEach(function(id) {
    var n = fragments.filter(function(f) {
      return fragUses(f).some(function(u) { return u.id === id; });
    }).length;
    opts.push('<option value="' + id + '">' + seen[id] + ' (' + n + ')</option>');
  });
  sel.innerHTML = opts.join('');
  sel.value = useFilter;
  sel.onchange = function() {
    useFilter = this.value;
    renderList(allFragments, selectedId);
  };
}

function renderList(fragments, selectedId) {
  const list = document.getElementById('frag-list');
  if (useFilter) {
    fragments = fragments.filter(function(f) {
      return fragUses(f).some(function(u) { return u.id === useFilter; });
    });
  }
  list.innerHTML = '';
  fragments.forEach(function(f) {
    const b = f.bounding || {};
    const dims = (b.obb_dims_mm || []).map(function(d){ return d.toFixed(0); }).join(' × ');
    const curv = f.curvature || {};
    const coarse = curv.coarse_mm || {};
    const code = getGrade(coarse.mean_rad);
    const g = code ? ROUGHNESS_GRADES[code] : null;

    const item = document.createElement('div');
    item.className = 'frag-item' + (f.fragment_id === selectedId ? ' active' : '');
    item.dataset.id = f.fragment_id;
    const archCode = f.archetype || '';
    item.innerHTML =
      '<div class="frag-id">' +
        '<span>' + f.fragment_id + '</span>' +
        (g ? '<span class="grade-pill" style="background:' + g.color + '22;color:' + g.color + '">' + code + '</span>' : '') +
      '</div>' +
      (archCode ? '<div style="font-size:10px;color:var(--accent);margin-bottom:2px;letter-spacing:0.04em">' + archCode + ' · ' + (f.archetype_label || '') + '</div>' : '') +
      '<div class="frag-dims">' + dims + ' mm</div>' +
      '<div class="frag-meta">' + fmt(b.mass_kg_est, 2) + ' kg · ' + (f.planarity || []).length + ' regions</div>' +
      (SHOW_USES ? useChips(f) : '');
    item.addEventListener('click', function() { selectFragment(f.fragment_id); });
    list.appendChild(item);
  });
}

function renderDetail(fragment) {
  const panel = document.getElementById('detail-content');
  if (!fragment) {
    panel.innerHTML = '<div class="detail-empty">← select a fragment</div>';
    return;
  }

  const b = fragment.bounding || {};
  const regions = fragment.planarity || [];
  const curv = fragment.curvature || {};
  const coarse = curv.coarse_mm || {};
  const fine   = curv.fine_mm   || {};
  const code = getGrade(coarse.mean_rad);
  const g = code ? ROUGHNESS_GRADES[code] : null;
  const watertight = b.watertight;
  const reportFile = fragment.fragment_id + '_report.html';

  // mesh warning
  const warnHtml = watertight ? '' :
    '<div class="mesh-warn">⚠ Open mesh — volume uses convex hull; convexity N/A. Close in Blender for accurate values.</div>';

  // bounding chips
  const dims = (b.obb_dims_mm || []).map(function(d){ return d.toFixed(1); }).join(' × ');
  const convHtml = b.convexity !== null && b.convexity !== undefined
    ? '<div class="chip-val">' + b.convexity.toFixed(4) + '</div>'
    : '<div class="chip-val" style="color:var(--muted);font-style:italic;font-size:12px">N/A</div><div class="chip-sub">open mesh</div>';

  // roughness
  const roughHtml = g ? (
    '<div class="roughness-row">' +
    '<div class="rgrade-code" style="color:' + g.color + '">' + code + '</div>' +
    '<div><div class="rgrade-label" style="color:' + g.color + '">' + g.label + '</div>' +
    '<div class="rgrade-desc">' + DESC_MAP[code] + '</div></div>' +
    '<div class="rgrade-nums">' +
    '<span>Fine (r=20mm) &nbsp;' + fmt(fine.mean_rad, 5) + ' rad</span>' +
    '<span>Coarse (r=60mm) &nbsp;' + fmt(coarse.mean_rad, 5) + ' rad</span>' +
    '</div></div>'
  ) : '<p style="color:var(--muted)">Curvature not available.</p>';

  // regions table rows
  let regionRows = '';
  regions.forEach(function(r, i) {
    const color = REGION_COLORS[i % REGION_COLORS.length];
    const nx = (r.normal_xyz || [0,0,0]);
    regionRows +=
      '<tr class="region-row-idx" data-region-id="' + i + '" onclick="highlightRegionIdx(' + i + ')" style="cursor:pointer"><td><span class="rdot" style="background:' + color + '"></span>' + (i+1) + '</td>' +
      '<td class="nr">' + (r.area_m2_est !== null ? r.area_m2_est.toFixed(4) + ' m²' : '—') + '</td>' +
      '<td class="nr">' + (r.inlier_fraction * 100).toFixed(1) + '%</td>' +
      '<td class="nr">' + r.fit_rms_mm.toFixed(3) + ' mm</td>' +
      '<td class="nr" style="color:var(--muted);font-size:11px">(' + nx[0].toFixed(3) + ', ' + nx[1].toFixed(3) + ', ' + nx[2].toFixed(3) + ')</td>' +
      '</tr>';
  });

  const date = (fragment.computed_at || '').slice(0, 10);

  const detailArch = fragment.archetype || '';
  const detailArchLabel = fragment.archetype_label || '';
  panel.innerHTML =
    '<div class="detail-header">' +
      '<div><h2>' + fragment.fragment_id + '</h2>' +
      (detailArch ? '<div style="display:inline-flex;align-items:center;gap:8px;margin-top:5px"><span style="background:#1e293b;border:1px solid #2d3250;border-radius:4px;padding:2px 8px;font-size:11px;color:#7c83fd;font-weight:600;letter-spacing:0.06em">' + detailArch + '</span><span style="font-size:11px;color:var(--muted)">' + detailArchLabel + '</span></div>' : '') +
      '<div style="font-size:11px;color:var(--muted);margin-top:3px">processed ' + date + ' · ' + (fragment.pipeline_version || '') + '</div></div>' +
      '<a class="open-link" href="' + reportFile + '" target="_blank">Open 3D Report ↗</a>' +
    '</div>' +

    warnHtml +

    '<div class="dsection">' +
      '<div class="dsection-title">Bounding &amp; Volume</div>' +
      '<div class="stat-row">' +
        '<div class="stat-chip"><div class="chip-label">OBB Dimensions</div><div class="chip-val" style="font-size:12px">' + dims + '</div><div class="chip-sub">mm (L × W × H)</div></div>' +
        '<div class="stat-chip"><div class="chip-label">Volume</div><div class="chip-val">' + fmt(b.volume_m3, 6) + '</div><div class="chip-sub">m³ (' + (b.volume_source || 'mesh') + ')</div></div>' +
        '<div class="stat-chip"><div class="chip-label">Convexity</div>' + convHtml + '</div>' +
        '<div class="stat-chip"><div class="chip-label">Mass Estimate</div><div class="chip-val">' + fmt(b.mass_kg_est, 3) + '</div><div class="chip-sub">kg @ 2400 kg/m³</div></div>' +
      '</div>' +
    '</div>' +

    '<div class="dsection">' +
      '<div class="dsection-title">Surface Roughness</div>' +
      roughHtml +
    '</div>' +

    '<div class="dsection">' +
      '<div class="dsection-title">Planar Regions — RANSAC (' + regions.length + ' found)</div>' +
      '<table class="dtable"><thead><tr>' +
        '<th>#</th><th class="nr">Area</th><th class="nr">Coverage</th><th class="nr">Fit RMS</th><th class="nr">Normal (x, y, z)</th>' +
      '</tr></thead><tbody>' + regionRows + '</tbody></table>' +
    '</div>';
}

// ── Three.js viewer ──────────────────────────────────────────────────────────

var THREE_STATE = null;

function ensureViewer() {
  if (THREE_STATE) return;
  var wrap = document.getElementById('viewer-wrap');
  var W = wrap.clientWidth, H = 280;

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c14);

  var camera = new THREE.PerspectiveCamera(45, W / H, 0.001, 100);
  var renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('idx-canvas'), antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W, H);

  var theta = 0.4, phi = 1.1, radius = 3.0;
  var isDragging = false, lastX = 0, lastY = 0;

  function updateCamera() {
    camera.position.set(
      radius * Math.sin(phi) * Math.sin(theta),
      radius * Math.cos(phi),
      radius * Math.sin(phi) * Math.cos(theta)
    );
    camera.lookAt(0, 0, 0);
  }
  updateCamera();

  var canvas = renderer.domElement;
  canvas.style.cursor = 'grab';
  canvas.addEventListener('mousedown', function(e) { isDragging=true; lastX=e.clientX; lastY=e.clientY; canvas.style.cursor='grabbing'; });
  window.addEventListener('mouseup',   function()  { isDragging=false; canvas.style.cursor='grab'; });
  window.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    theta -= (e.clientX-lastX)*0.008;
    phi    = Math.max(0.08, Math.min(Math.PI-0.08, phi+(e.clientY-lastY)*0.008));
    lastX=e.clientX; lastY=e.clientY;
    updateCamera();
  });
  canvas.addEventListener('wheel', function(e) {
    radius = Math.max(0.8, Math.min(8.0, radius+e.deltaY*0.003));
    updateCamera(); e.preventDefault();
  }, { passive: false });

  function animate() { requestAnimationFrame(animate); renderer.render(scene, camera); }
  animate();

  window.addEventListener('resize', function() {
    var w = wrap.clientWidth;
    camera.aspect = w/H; camera.updateProjectionMatrix(); renderer.setSize(w, H);
  });

  THREE_STATE = { scene: scene, camera: camera, renderer: renderer, updateCamera: updateCamera, cloud: null };
}

function toggleIdxColors() {
  if (!THREE_STATE || !THREE_STATE.cloud) return;
  var state   = THREE_STATE;
  state.curMode = state.curMode === 'scan' ? 'region' : 'scan';
  // clear any active highlight when switching color mode
  state.curHighlight = null;
  document.querySelectorAll('.region-row-idx').forEach(function(r) { r.classList.remove('row-active-idx'); });
  var arr = state.curMode === 'scan' ? state.scanColArr : state.regionColArr;
  state.cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(arr, 3));
  var btn = document.getElementById('color-toggle-idx');
  if (btn) btn.textContent = state.curMode === 'scan' ? 'Show Regions' : 'Show Scan';
  var leg = document.getElementById('viewer-legend-idx');
  if (leg) leg.style.display = state.curMode === 'region' ? 'flex' : 'none';
}

function highlightRegionIdx(regionId) {
  if (!THREE_STATE || !THREE_STATE.cloud) return;
  var state = THREE_STATE;
  var points = state.lastPoints;
  if (!points) return;

  // clicking the same row again → deselect
  if (state.curHighlight === regionId) {
    state.curHighlight = null;
    var restore = state.curMode === 'scan' ? state.scanColArr : state.regionColArr;
    state.cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(restore, 3));
    document.querySelectorAll('.region-row-idx').forEach(function(r) { r.classList.remove('row-active-idx'); });
    return;
  }
  state.curHighlight = regionId;
  var col2 = new THREE.Color();
  var arr = [];
  for (var j = 0; j < points.length; j++) {
    var p = points[j];
    if (p[3] === regionId) {
      col2.set(REGION_COLORS[regionId % REGION_COLORS.length]);
    } else {
      col2.setStyle('#111318');
    }
    arr.push(col2.r, col2.g, col2.b);
  }
  state.cloud.geometry.setAttribute('color', new THREE.Float32BufferAttribute(arr, 3));
  document.querySelectorAll('.region-row-idx').forEach(function(r) {
    r.classList.toggle('row-active-idx', parseInt(r.dataset.regionId) === regionId);
  });
}

function loadPointCloud(points, regions, colorMode) {
  if (!THREE_STATE) return;
  var state = THREE_STATE;
  colorMode = colorMode || 'region';
  var hasScan = (colorMode === 'scan');

  if (state.cloud) { state.scene.remove(state.cloud); state.cloud.geometry.dispose(); state.cloud = null; }
  if (!points || !points.length) return;

  // Build both color arrays once — toggle swaps buffer without re-parsing
  var positions = [], scanColArr = [], regionColArr = [];
  var col = new THREE.Color();
  for (var i = 0; i < points.length; i++) {
    var p = points[i];
    positions.push(p[0], p[1], p[2]);
    if (hasScan && p.length >= 8)       col.setRGB(p[5], p[6], p[7]);
    else if (hasScan && p.length === 7) col.setRGB(p[4], p[5], p[6]);
    else col.set(p[3] === UNSCANNED_ID ? UNSCANNED_COLOR : (p[3] < 0 ? '#3d4455' : REGION_COLORS[p[3] % REGION_COLORS.length]));
    scanColArr.push(col.r, col.g, col.b);
    col.set(p[3] === UNSCANNED_ID ? UNSCANNED_COLOR : (p[3] < 0 ? '#3d4455' : REGION_COLORS[p[3] % REGION_COLORS.length]));
    regionColArr.push(col.r, col.g, col.b);
  }
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(
    hasScan ? scanColArr : regionColArr, 3));
  var mat = new THREE.PointsMaterial({ size: 0.018, vertexColors: true, sizeAttenuation: true });
  state.cloud = new THREE.Points(geo, mat);
  state.scene.add(state.cloud);

  // Store for toggle and highlight
  state.scanColArr   = scanColArr;
  state.regionColArr = regionColArr;
  state.lastPoints   = points;
  state.hasScan      = hasScan;
  state.curMode      = colorMode;
  state.curHighlight = null;

  // Toggle button — only visible when scan colors exist
  var btn = document.getElementById('color-toggle-idx');
  if (btn) { btn.style.display = hasScan ? '' : 'none'; btn.textContent = 'Show Regions'; }

  // Update legend
  var leg = document.getElementById('viewer-legend-idx');
  var html = '';
  for (var j = 0; j < regions.length; j++) {
    var area = regions[j].area_m2_est !== null ? regions[j].area_m2_est.toFixed(4)+' m²' : '—';
    html += '<span style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)">' +
            '<span style="width:8px;height:8px;border-radius:50%;background:' + REGION_COLORS[j % REGION_COLORS.length] + ';display:inline-block"></span>' +
            'R'+(j+1)+' · '+area+'</span>';
  }
  html += '<span style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)"><span style="width:8px;height:8px;border-radius:50%;background:#3d4455;display:inline-block"></span>unclassified</span>';
  // Check if any point has UNSCANNED_ID
  var hasUnscanned = points.some(function(p) { return p[3] === UNSCANNED_ID; });
  if (hasUnscanned) {
    html += '<span style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)"><span style="width:8px;height:8px;border-radius:50%;background:' + UNSCANNED_COLOR + ';display:inline-block"></span>unscanned (ground contact)</span>';
  }
  leg.innerHTML = html;
}

// ── Fragment list & detail ────────────────────────────────────────────────────

var allFragments = [];
var viewerMap    = {};
var selectedId   = null;

function selectFragment(id) {
  selectedId = id;
  location.hash = id;
  renderList(allFragments, selectedId);
  var frag = allFragments.find(function(f){ return f.fragment_id === id; }) || null;
  renderDetail(frag);

  // Update 3D viewer
  var vd = viewerMap[id];
  if (vd && vd.points && vd.points.length) {
    document.getElementById('viewer-wrap').style.display = 'block';
    document.getElementById('viewer-legend-idx').style.display = 'flex';
    ensureViewer();
    // reset any active row highlight from previous fragment
    document.querySelectorAll('.region-row-idx').forEach(function(r) { r.classList.remove('row-active-idx'); });
    var cm = vd.color_mode || 'region';
    loadPointCloud(vd.points, frag ? (frag.planarity || []) : [], cm);
    // legend only makes sense in region mode
    document.getElementById('viewer-legend-idx').style.display = cm === 'region' ? 'flex' : 'none';
  } else {
    document.getElementById('viewer-wrap').style.display = 'none';
    document.getElementById('viewer-legend-idx').style.display = 'none';
  }
}

function init(fragments, vmap) {
  allFragments = fragments.slice().sort(function(a, b) {
    return a.fragment_id.localeCompare(b.fragment_id);
  });
  viewerMap = vmap || {};
  document.getElementById('count').textContent = allFragments.length + ' fragment' + (allFragments.length !== 1 ? 's' : '');
  var hash  = location.hash.replace('#', '') || {hash_init};
  var first = hash || (allFragments[0] ? allFragments[0].fragment_id : null);
  buildUseFilter(allFragments);
  renderList(allFragments, first);
  renderDetail(allFragments.find(function(f){ return f.fragment_id === first; }) || null);
  if (first) { selectedId = first; selectFragment(first); }
}
"""


def update_inventory(output_dir: Path, highlight_id: str = None) -> Path:
    """
    Scan all *_geometry.json files in output_dir and regenerate index.html.
    Called automatically after every pipeline run.

    Parameters
    ----------
    output_dir   : folder containing *_geometry.json files
    highlight_id : fragment ID to open on load (defaults to the most recent)

    Returns
    -------
    Path to the generated index.html.
    """
    fragments = []
    for json_path in sorted(output_dir.glob("*_geometry.json")):
        try:
            with open(json_path, encoding="utf-8") as f:
                fragments.append(json.load(f))
        except Exception:
            pass

    viewer_map = {}
    for vpath in sorted(output_dir.glob("*_viewer.json")):
        frag_id = vpath.stem.replace("_viewer", "")
        try:
            with open(vpath, encoding="utf-8") as f:
                viewer_map[frag_id] = json.load(f)
        except Exception:
            pass

    fragment_json = json.dumps(fragments)
    viewer_json   = json.dumps(viewer_map)
    hash_init     = f'"{highlight_id}"' if highlight_id else "null"
    count         = len(fragments)

    # _INDEX_JS is a plain string (not an f-string), so {hash_init} inside it
    # must be substituted manually before embedding into the HTML template.
    index_js = (_INDEX_JS.replace('{hash_init}', hash_init)
               .replace('{show_uses_js}',
                        'true' if SHOW_USE_SUGGESTIONS else 'false'))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Material Inventory ({count})</title>
  <style>{_INDEX_CSS}</style>
</head>
<body>

<div class="topbar">
  <h1>Material Inventory</h1>
  <span class="count" id="count"></span>
</div>

<div class="panels">
  <div id="use-filter-box" style="padding:8px 10px;border-bottom:1px solid #262a36">
    <div style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">Intended use</div>
    <select id="use-filter" style="width:100%;background:#15171f;color:#b0b8d0;border:1px solid #262a36;border-radius:4px;font-size:11px;padding:4px 6px"></select>
  </div>
  <div class="frag-list" id="frag-list"></div>
  <div class="detail-panel" id="detail-panel">
    <div id="viewer-wrap">
      <canvas id="idx-canvas"></canvas>
      <div class="viewer-hint-idx">drag to rotate · scroll to zoom</div>
      <button id="color-toggle-idx" onclick="toggleIdxColors()" style="display:none;position:absolute;top:8px;right:8px;background:#1e2030;border:1px solid #3d4455;color:#b0b8d0;font-size:10px;padding:4px 10px;border-radius:20px;cursor:pointer;z-index:10">Show Regions</button>
    </div>
    <div id="viewer-legend-idx"></div>
    <div id="detail-content">
      <div class="detail-empty">← select a fragment</div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
{index_js}
init({fragment_json}, {viewer_json});
</script>
</body>
</html>"""

    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path
