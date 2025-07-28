from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from app.types import CrossSectionInfo, NodesDict, LinesDict, MembersDict, MemberType
from app.plots.model_viz import  Vec3

def compute_beam_vertices_rect(A: Vec3, B: Vec3, width: float, height: float) -> np.ndarray:
    v = B - A
    length = np.linalg.norm(v)
    if length == 0:
        return np.array([A] * 8)
    v_hat = v / length

    axes = [np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1])]
    helper = min(axes, key=lambda ax: abs(np.dot(v_hat, ax)))

    local_y = np.cross(v_hat, helper)
    local_y /= np.linalg.norm(local_y)
    local_z = np.cross(v_hat, local_y)
    local_z /= np.linalg.norm(local_z)

    local_y *= width  / 2.0
    local_z *= height / 2.0

    v0, v1, v2, v3 = A + local_y + local_z, A + local_y - local_z, A - local_y - local_z, A - local_y + local_z
    v4, v5, v6, v7 = B + local_y + local_z, B + local_y - local_z, B - local_y - local_z, B - local_y + local_z
    return np.stack([v0, v1, v2, v3, v4, v5, v6, v7])

def add_beam_mesh(fig: go.Figure, verts: np.ndarray, color: str) -> None:
    quads = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    i_list, j_list, k_list = [], [], []
    for a, b, c, d in quads:
        i_list.extend([a, a]); j_list.extend([b, c]); k_list.extend([c, d]) # Draw one side
        i_list.extend([a, a]); j_list.extend([c, d]); k_list.extend([b, c]) # Draw the other side for visibility

    fig.add_trace(go.Mesh3d(x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i_list, j=j_list, k=k_list, color=color, flatshading=False, opacity=1.0, hoverinfo="skip", lighting=dict(ambient=0.5, diffuse=0.7, specular=0.3, roughness=0.9), showscale=False))


def normalise(val: float, vmin: float, vmax: float) -> float:
    if vmax == vmin:
        return 0.5
    return (val - vmin) / (vmax - vmin)


def jet_colour(val: float, vmin: float, vmax: float, colorscale: list) -> str:
    """Gets a color from a provided Plotly sequential colorscale list."""
    idx = int(normalise(val, vmin, vmax) * (len(colorscale) - 1))
    return colorscale[idx]

def plot_deformed_mesh(
    nodes: dict[int, dict],
    lines: dict[int, dict],
    members: dict[int, dict],
    cross_sections: dict[int, dict],
    disp_dict: dict[int, float],
    scale: float = 25,
) -> go.Figure:
    """Return a Plotly figure of the scaled deformed shape with meshed elements."""

    # ------------------------------------------------------------------ #
    # 1. Deformed node coordinates
    # ------------------------------------------------------------------ #
    def_nodes: dict[int, dict] = {}
    for nid, data in nodes.items():
        def_nodes[nid] = {
            "x": data["x"],
            "y": data["y"],
            "z": data["z"] + disp_dict.get(nid, 0.0) * scale,
        }

    # mean displacement per line
    line_disp = {
        lid: (disp_dict.get(ln["Ni"], 0.0) + disp_dict.get(ln["Nj"], 0.0)) / 2.0
        for lid, ln in lines.items()
    }
    dmin, dmax = (min(line_disp.values()), max(line_disp.values())) if line_disp else (0.0, 0.0)

    # ------------------------------------------------------------------ #
    # 2. Figure with bounding cube
    # ------------------------------------------------------------------ #
    fig = go.Figure()

    all_x, all_y, all_z = (
        [n["x"] for n in def_nodes.values()],
        [n["y"] for n in def_nodes.values()],
        [n["z"] for n in def_nodes.values()],
    )
    if all_x:                                              # keep aspect 1:1:1
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        z_min, z_max = min(all_z), max(all_z)
        cx, cy, cz = (x_min + x_max) / 2, (y_min + y_max) / 2, (z_min + z_max) / 2
        half = max(x_max - x_min, y_max - y_min, z_max - z_min) / 2 or 1.0
        fig.add_trace(
            go.Scatter3d(
                x=[cx - half, cx + half] * 4,
                y=[cy - half, cy - half, cy + half, cy + half] * 2,
                z=[cz - half] * 4 + [cz + half] * 4,
                mode="markers",
                marker=dict(size=0, color="rgba(0,0,0,0)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # colour helper
    scale_name = "Jet_r"
    scale = getattr(px.colors.sequential, scale_name)
    def map_colour(val: float) -> str:
        if dmax == dmin:
            return scale[0]
        ratio = (val - dmin) / (dmax - dmin)
        return scale[int(ratio * (len(scale) - 1))]

    # draw members (assumes helper funcs exist)
    for lid, ln in lines.items():
        cs_id = members[lid]["cross_section_id"]
        if cs_id not in cross_sections:
            continue
        n1, n2 = def_nodes[ln["Ni"]], def_nodes[ln["Nj"]]
        A = np.array([n1["x"], n1["y"], n1["z"]])
        B = np.array([n2["x"], n2["y"], n2["z"]])
        cs = cross_sections[cs_id]
        verts = compute_beam_vertices_rect(A, B, width=float(cs["h"]), height=float(cs["b"]))
        add_beam_mesh(fig, verts, map_colour(line_disp[lid]))

    # nodes
    fig.add_trace(
        go.Scatter3d(
            x=[n["x"] for n in def_nodes.values()],
            y=[n["y"] for n in def_nodes.values()],
            z=[n["z"] for n in def_nodes.values()],
            mode="markers",
            marker=dict(size=3, color="black"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # colour‑bar
    fig.add_trace(
        go.Scatter3d(
            x=[None], y=[None], z=[None],
            mode="markers",
            marker=dict(
                colorscale=scale_name,
                cmin=dmin, cmax=dmax,
                color=[dmin, dmax],
                showscale=True,
                colorbar=dict(
                    title="ΔZ [mm]",
                    # ‑‑ size ----------------------------------------------------------------
                    len=0.45,            # 45 % of plot height  (default: 1.0 = full height)
                    lenmode="fraction",  # “fraction” = percentage, “pixels” = absolute px
                    thickness=25,        # 25 px wide           (default: 30 px)
                    thicknessmode="pixels",
                    # ‑‑ position ------------------------------------------------------------
                    y=0.5, yanchor="middle",
                    x=1.02, xanchor="left",
                    # ‑‑ appearance (optional) ----------------------------------------------
                    outlinewidth=1,
                    ticks="outside",
                    tickfont=dict(size=12),
                ),
            ),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # ------------------------------------------------------------------ #
    # 3. Section legend entries
    # ------------------------------------------------------------------ #
    legend_labels = set()
    for lid, ln in lines.items():
        m_type: MemberType | None = ln.get("Type")
        if m_type is None:
            continue
        cs_id = members[lid]["cross_section_id"]
        if cs_id not in cross_sections:
            continue
        desc = cross_sections[cs_id].get("Description", f"Section {cross_sections[cs_id]['name']}")
        legend_labels.add(f"{m_type}: {desc}")

    for label in sorted(legend_labels):
        fig.add_trace(
            go.Scatter3d(
                x=[None], y=[None], z=[None],
                mode="markers",
                marker=dict(size=8, color="rgba(0,0,0,0)", symbol="square"),
                name=label,
                legendgroup="sections",
                hoverinfo="skip",
            )
        )

    # ------------------------------------------------------------------ #
    # 4. Max‑displacement box
    # ------------------------------------------------------------------ #
    max_abs = max(abs(dmin), abs(dmax))
    fig.add_annotation(
        text=f"<b>Max Model Deformation |ΔZ|</b><br>{max_abs:.3f} mm",
        xref="paper", yref="paper",
        x=0.5 , y=1,
        showarrow=False,
        bgcolor="rgba(255,255,255,0.85)",
        borderwidth=1,
        font=dict(size=16, color="black"),
    )

    # ------------------------------------------------------------------ #
    # 5. Layout
    # ------------------------------------------------------------------ #
    fig.update_layout(
        scene=dict(
            xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
            aspectmode="data",
            bgcolor="white",
            camera=dict(eye=dict(x=1.3, y=1.3, z=1.3)),
        ),
        legend=dict(
            title=dict(text="Sections"),
            x=0.02, y=0.02,                # bottom‑left
            xanchor="left", yanchor="bottom",
            bgcolor="rgba(255,255,255,0.85)",
            borderwidth=1,
            itemsizing="constant",
            font=dict(size=16, color="black")
        ),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=40, b=0),
    )

    return fig