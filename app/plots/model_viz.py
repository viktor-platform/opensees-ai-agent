import plotly.graph_objects as go
import numpy as np

from app.types import NodesDict, LinesDict, MembersDict, CrossSectionsDict

Vec3 = np.ndarray

PASTEL_PALETTE = [
    "#E416C1",  # Light Pink
    "#098BF5",  # Baby Blue
    "#F3083F",  # Cotton Candy
    "#2704F0",  # Soft Sky Blue
]
def compute_beam_vertices_rect(A: Vec3, B: Vec3, width: float, height: float) -> np.ndarray:
    v = B - A
    length = np.linalg.norm(v)
    if length == 0:
        raise ValueError("member with zero length")
    v_hat = v / length

    # pick whichever world‑axis is most perpendicular to v_hat
    axes = [np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1])]
    helper = min(axes, key=lambda ax: abs(np.dot(v_hat, ax)))

    # build a clean 2D frame
    local_y = np.cross(v_hat, helper)
    local_y /= np.linalg.norm(local_y)
    local_z = np.cross(v_hat, local_y)
    local_z /= np.linalg.norm(local_z)

    local_y *= width  / 2.0
    local_z *= height / 2.0

    # eight corners
    v0 = A + local_y + local_z
    v1 = A + local_y - local_z
    v2 = A - local_y - local_z
    v3 = A - local_y + local_z
    v4 = B + local_y + local_z
    v5 = B + local_y - local_z
    v6 = B - local_y - local_z
    v7 = B - local_y + local_z
    return np.stack([v0, v1, v2, v3, v4, v5, v6, v7])

def add_beam_mesh(fig: go.Figure, verts: np.ndarray, color: str) -> None:
    """Insert one rectangular prism into the figure, drawing both sides of each face."""
    # define each face by four verts (a,b,c,d)
    quads = [
        (0, 1, 2, 3),  # face at A
        (4, 5, 6, 7),  # face at B
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]

    i_list, j_list, k_list = [], [], []
    for a, b, c, d in quads:
        # two triangles per quad
        # 1) a→b→c
        i_list.append(a); j_list.append(b); k_list.append(c)
        # 2) a→c→d
        i_list.append(a); j_list.append(c); k_list.append(d)

        # duplicate them reversed so back faces show
        # 3) a→c→b
        i_list.append(a); j_list.append(c); k_list.append(b)
        # 4) a→d→c
        i_list.append(a); j_list.append(d); k_list.append(c)

    fig.add_trace(
        go.Mesh3d(
            x=verts[:, 0],
            y=verts[:, 1],
            z=verts[:, 2],
            i=i_list,
            j=j_list,
            k=k_list,
            color=color,
            # draw both sides, disable flat shading to simplify
            flatshading=False,
            opacity=1.0,
            hoverinfo="skip",
            lighting=dict(ambient=0.5, diffuse=0.7, specular=0.3, roughness=0.9),
            showscale=False,
        )
    )


def compute_cylinder_mesh(
    base_center: Vec3,
    height: float,
    radius: float,
    segments: int = 16
) -> tuple[np.ndarray, list[int], list[int], list[int]]:
    """Return verts and faces for a vertical cylinder pointing down from base_center."""
    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    xs = radius * np.cos(theta)
    ys = radius * np.sin(theta)
    # top circle at z = base_z
    top = np.vstack([base_center + np.array([x, y, 0]) for x, y in zip(xs, ys)])
    # bottom circle at z = base_z - height
    bottom = np.vstack([base_center + np.array([x, y, -height]) for x, y in zip(xs, ys)])
    verts = np.vstack([top, bottom])
    i_list = []
    j_list = []
    k_list = []
    for i in range(segments):
        ni = (i + 1) % segments
        # triangle top→bottom→bottom next
        i_list += [i, i]
        j_list += [i + segments, ni + segments]
        k_list += [ni, ni + segments]
        # reversed for backface
        i_list += [i, i]
        j_list += [ni + segments, i + segments]
        k_list += [i + segments, ni]
    return verts, i_list, j_list, k_list

def compute_cone_mesh(
    base_center: Vec3,
    height: float,
    radius: float,
    segments: int = 16
) -> tuple[np.ndarray, list[int], list[int], list[int]]:
    """Return verts and faces for a downward‐pointing cone at base_center."""
    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    xs = radius * np.cos(theta)
    ys = radius * np.sin(theta)
    # circle at base_center
    base = np.vstack([base_center + np.array([x, y, 0]) for x, y in zip(xs, ys)])
    tip = base_center + np.array([0, 0, -height])
    verts = np.vstack([base, tip])
    tip_idx = len(verts) - 1
    i_list = []
    j_list = []
    k_list = []
    for i in range(segments):
        ni = (i + 1) % segments
        # triangle base[i]→base[ni]→tip
        i_list += [i, i]
        j_list += [ni, tip_idx]
        k_list += [tip_idx, ni]
    return verts, i_list, j_list, k_list

def plot_3d_model(
    nodes: NodesDict,
    lines: LinesDict,
    members: MembersDict,
    cross_sections: CrossSectionsDict,
    load: float = 0.0,
) -> go.Figure:
    """Plot members with pastel colours and add red load arrows."""
    x_nodes = [n["x"] for n in nodes.values()]
    y_nodes = [n["y"] for n in nodes.values()]
    z_nodes = [n["z"] for n in nodes.values()]

    # --- colour map per cross‑section ----------------------------------------
    cs_ids = sorted({m["cross_section_id"] for m in members.values()})
    color_map = {cs_id: PASTEL_PALETTE[i % len(PASTEL_PALETTE)] for i, cs_id in enumerate(cs_ids)}
    cs_labels = {
        cs_id: cross_sections[cs_id].get("Description", f"Section {cross_sections[cs_id]['name']}")
        for cs_id in cs_ids
    }

    fig = go.Figure()

    # This is a trick to stabilize the scene by adding an INVISIBLE bounding box

    x0, x1 = min(x_nodes), max(x_nodes)
    y0, y1 = min(y_nodes), max(y_nodes)
    z0, z1 = min(z_nodes), max(z_nodes)

    # Find the center point of the model
    x_center, y_center, z_center = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    # Find the largest dimension of the model
    max_range = max(x1 - x0, y1 - y0, z1 - z0)
    half_range = max_range / 2.0

    # Define the 8 corners of a perfect cube centered around the model
    xb = [x_center - half_range, x_center + half_range]
    yb = [y_center - half_range, y_center + half_range]
    zb = [z_center - half_range, z_center + half_range]

    fig.add_trace(go.Scatter3d(
        x=[xb[0], xb[1], xb[0], xb[1], xb[0], xb[1], xb[0], xb[1]],
        y=[yb[0], yb[0], yb[1], yb[1], yb[0], yb[0], yb[1], yb[1]],
        z=[zb[0], zb[0], zb[0], zb[0], zb[1], zb[1], zb[1], zb[1]],
        mode='markers',
        marker=dict(size=0, color='rgba(0,0,0,0)'), # Make markers invisible
        showlegend=False,
        hoverinfo='none'
    ))

    fig.add_trace(
        go.Scatter3d(
            x=x_nodes, y=y_nodes, z=z_nodes, mode="markers",
            marker=dict(size=3, color="black"), hoverinfo="text", showlegend=False,
        )
    )

    for member in members.values():
        line = lines[member["line_id"]]
        ni, nj = nodes[line["Ni"]], nodes[line["Nj"]]
        A = np.array([ni["x"], ni["y"], ni["z"]], float)
        B = np.array([nj["x"], nj["y"], nj["z"]], float)
        cs = cross_sections[member["cross_section_id"]]
        width, height = float(cs["h"]), float(cs["h"])
        verts = compute_beam_vertices_rect(A, B, width, height)
        add_beam_mesh(fig, verts, color_map[member["cross_section_id"]])

    nodes_with_load = list(
        {node for ln in lines.values() if ln.get("Type") == "Joist" for node in (ln["Ni"], ln["Nj"])}
    )
    if nodes_with_load:
        arrow_height, offset = 400.0, 300.0
        cyl_h, cone_h = 0.8 * arrow_height, 0.2 * arrow_height
        cyl_radius, cone_radius = 0.04 * arrow_height, 0.15 * arrow_height
        for nid in nodes_with_load:
            n = nodes[nid]
            base = np.array([n["x"], n["y"], n["z"]], float) + np.array([0.0, 0.0, arrow_height + offset])
            cyl_verts, ci, cj, ck = compute_cylinder_mesh(base, cyl_h, cyl_radius)
            fig.add_trace(go.Mesh3d(
                x=cyl_verts[:, 0], y=cyl_verts[:, 1], z=cyl_verts[:, 2],
                i=ci, j=cj, k=ck, color="red", opacity=1.0, hoverinfo="skip", showlegend=False
            ))
            cone_base = base + np.array([0.0, 0.0, -cyl_h])
            cone_verts, qi, qj, qk = compute_cone_mesh(cone_base, cone_h, cone_radius)
            fig.add_trace(go.Mesh3d(
                x=cone_verts[:, 0], y=cone_verts[:, 1], z=cone_verts[:, 2],
                i=qi, j=qj, k=qk, color="red", opacity=1.0, hoverinfo="skip", showlegend=False
            ))

    for cs_id in cs_ids:
        fig.add_trace(
            go.Scatter3d(
                x=[None], y=[None], z=[None], mode="markers",
                marker=dict(symbol="square", size=10, color=color_map[cs_id]),
                name=cs_labels[cs_id], hoverinfo="none", showlegend=True
            )
        )

    fig.update_layout(
        scene=dict(
            aspectmode='data',
            xaxis_visible=False,
            yaxis_visible=False,
            zaxis_visible=False,
            bgcolor="white",
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
        ),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(
            x=0.95, y=0.05, xanchor="right", yanchor="bottom",
            bgcolor="rgba(0,0,0,0)", borderwidth=0, itemsizing="constant", font=dict(size=16, color="black")
        ),
    )

    return fig

def default_blank_scene()->go.Figure:
    """Fallback scene when there is no Plotly objects to plot!"""
    fig = go.Figure()
    fig.update_layout(
        template=None,
        xaxis=dict(visible=False, showgrid=False, zeroline=False, showline=False),
        yaxis=dict(visible=False, showgrid=False, zeroline=False, showline=False),
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=0, r=0, t=0, b=0),
        autosize=True,
    )
    return fig
