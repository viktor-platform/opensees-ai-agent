from typing import Literal
from app.types import (
    NodeInfo,
    LineInfo,
    NodesDict,
    LinesDict,
)

Plane = Literal["xz", "yz"]


class NodeList:
    def __init__(self) -> None:
        self.node_list: list[NodeInfo] = []

    def add_node(self, new_node: NodeInfo) -> None:
        self.node_list.append(new_node)

    def add_node_list(self, new_node_list: list[NodeInfo]) -> None:
        self.node_list.extend(new_node_list)

    def serialize(self) -> NodesDict:
        return {node["id"]: node for node in self.node_list}


class LineList:
    def __init__(self) -> None:
        self.line_list: list[LineInfo] = []

    def add_line(self, new_line: LineInfo) -> None:
        self.line_list.append(new_line)

    def add_line_list(self, new_line_list: list[LineInfo]) -> None:
        self.line_list.extend(new_line_list)

    def serialize(self) -> LinesDict:
        return {line["id"]: line for line in self.line_list}


class Truss:
    def __init__(
        self,
        height: float,
        width: float,
        n_diagonals: int,
        xo: float,
        yo: float,
        zo: float,
        plane: Plane,
        lines_id: int = 0,
        nodes_id: int = 0,
        component_name: str | None = None,
    ) -> None:
        self.height = height
        self.width = width
        self.n_diagonals = n_diagonals
        self.xo = xo
        self.yo = yo
        self.zo = zo
        self.plane = plane
        self.component_name = component_name

        self.nodes = NodeList()
        self.lines = LineList()
        self.nodes_id = nodes_id
        self.lines_id = lines_id
        self.joist_nodes: list[int] = []

    def gen_node_tag(self) -> int:
        self.nodes_id += 1
        return self.nodes_id

    def gen_line_tag(self) -> int:
        self.lines_id += 1
        return self.lines_id

    def get_joist_node_tag(self) -> list[int]:
        return self.joist_nodes

    def create_chord_nodes(
        self, width: float, xo: float, yo: float, zo: float, plane: Plane
    ) -> list[NodeInfo]:
        count = self.n_diagonals + 1
        delta = width / (count - 1)
        chord: list[NodeInfo] = []

        for i in range(count):
            x = xo + (delta * i) if plane == "xz" else xo
            y = yo + (delta * i) if plane == "yz" else yo
            z = zo
            chord.append(
                {
                    "id": self.gen_node_tag(),
                    "x": x,
                    "y": y,
                    "z": z,
                }
            )

        self.nodes.add_node_list(chord)
        return chord

    def connect_chord_lines(self, chord_nodes: list[NodeInfo]) -> None:
        lines: list[LineInfo] = []
        for i in range(len(chord_nodes) - 1):
            lines.append(
                {
                    "id": self.gen_line_tag(),
                    "Ni": chord_nodes[i]["id"],
                    "Nj": chord_nodes[i + 1]["id"],
                    "Type": "Truss Chord"
                }
            )
        self.lines.add_line_list(lines)

    def create_diagonals(self, top_ids: list[int], bot_ids: list[int]) -> None:
        for i in range(self.n_diagonals):
            if i % 2 == 0:
                a = top_ids[i]
                b = bot_ids[i + 1]
            else:
                a = top_ids[i + 1]
                b = bot_ids[i]
            self.lines.add_line(
                {
                    "id": self.gen_line_tag(),
                    "Ni": a,
                    "Nj": b,
                    "Type": "Truss Diagonal"
                }
            )

        for t, b in zip(top_ids, bot_ids, strict=True):  # verticals
            self.lines.add_line(
                {
                    "id": self.gen_line_tag(),
                    "Ni": t,
                    "Nj": b,
                    "Type": "Truss Diagonal"
                }
            )

    def create(self) -> tuple[NodesDict, LinesDict]:
        # bottom chord
        bottom = self.create_chord_nodes(
            width=self.width,
            xo=self.xo,
            yo=self.yo,
            zo=self.zo - self.height,
            plane=self.plane,
        )
        self.connect_chord_lines(bottom)

        # top chord
        top = self.create_chord_nodes(
            width=self.width,
            xo=self.xo,
            yo=self.yo,
            zo=self.zo,
            plane=self.plane,
        )
        self.connect_chord_lines(top)

        self.joist_nodes = [n["id"] for n in top[1:-1]]
        self.create_diagonals(
            [n["id"] for n in top],
            [n["id"] for n in bottom],
        )

        return self.nodes.serialize(), self.lines.serialize()


class Columns:
    def __init__(
        self,
        height: float,
        xo: float,
        yo: float,
        zo: float = 0,
        partition: int = 2,
        nodes_id: int = 0,
        lines_id: int = 0,
        component_name: str | None = None,
    ) -> None:
        self.height = height
        self.xo = xo
        self.yo = yo
        self.zo = zo
        self.partition = partition
        self.component_name = component_name

        self.nodes = NodeList()
        self.lines = LineList()
        self.nodes_id = nodes_id
        self.lines_id = lines_id

    def gen_node_tag(self) -> int:
        self.nodes_id += 1
        return self.nodes_id

    def gen_line_tag(self) -> int:
        self.lines_id += 1
        return self.lines_id

    def create(self) -> tuple[NodesDict, LinesDict]:
        delta = self.height / self.partition
        col_nodes: list[NodeInfo] = []

        for i in range(self.partition + 1):
            col_nodes.append(
                {
                    "id": self.gen_node_tag(),
                    "x": self.xo,
                    "y": self.yo,
                    "z": self.zo + delta * i,
                }
            )
        self.nodes.add_node_list(col_nodes)

        col_lines: list[LineInfo] = []
        for i in range(len(col_nodes) - 1):
            col_lines.append(
                {
                    "id": self.gen_line_tag(),
                    "Ni": col_nodes[i]["id"],
                    "Nj": col_nodes[i + 1]["id"],
                    "Type": "Column"
                }
            )
        self.lines.add_line_list(col_lines)

        return self.nodes.serialize(), self.lines.serialize()
