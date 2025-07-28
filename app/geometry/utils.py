import matplotlib.pyplot as plt
from collections import defaultdict
from app.types import NodesDict, LinesDict

def clean_model(Nodes: dict, Lines: dict) -> tuple[dict, dict]:
    """Deletes duplicated nodes"""
    # Create a mapping from coordinates to node IDs
    coord_to_nodes = defaultdict(list)
    for node_id, attrs in Nodes.items():
        coord = (attrs["x"], attrs["y"], attrs["z"])
        coord_to_nodes[coord].append(node_id)

    # Identify duplicates: coordinates with more than one node ID
    duplicates = {coord: ids for coord, ids in coord_to_nodes.items() if len(ids) > 1}

    node_replacements = {}
    for _, ids in duplicates.items():
        kept_node = min(ids)  # Choose the node with the smallest ID to keep
        for duplicate_node in ids:
            if duplicate_node != kept_node:
                node_replacements[duplicate_node] = kept_node

    # Update Lines to replace deleted Nodes with Kept Nodes
    for line in Lines.values():
        if line["Ni"] in node_replacements:
            line["Ni"] = node_replacements[line["Ni"]]
        if line["Nj"] in node_replacements:
            line["Nj"] = node_replacements[line["Nj"]]

    # Remove duplicate Nodes
    for dup_node in node_replacements.keys():
        del Nodes[dup_node]

    return Nodes, Lines

def get_nodes_by_z(Nodes: dict, z: float) -> list[int]:
    selected = [node_id for node_id, attrs in Nodes.items() if attrs["z"] == z]
    return selected


def plot_model(nodes: NodesDict, lines: LinesDict) -> None:
    fig = plt.figure(figsize=(7, 5))
    ax = fig.add_subplot(111, projection="3d")

    # Draw nodes
    for nid, data in nodes.items():
        ax.scatter(data["x"], data["y"], data["z"])
        ax.text(data["x"], data["y"], data["z"], f"{nid}", fontsize=8, ha="center")

    # Draw lines
    for line in lines.values():
        ni = nodes[line["Ni"]]
        nj = nodes[line["Nj"]]
        ax.plot([ni["x"], nj["x"]], [ni["y"], nj["y"]], [ni["z"], nj["z"]])

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")  # Z is vertical
    ax.set_title("Platform Model / Node IDs and Connectivity")
    plt.tight_layout()
    plt.show()