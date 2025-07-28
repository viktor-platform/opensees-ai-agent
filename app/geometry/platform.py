from app.types import LinesDict, NodesDict
from app.geometry.truss import Truss, Columns
from app.geometry.utils import clean_model
from typing import Annotated

class Platform:
    def __init__(
        self,
        xLenght: Annotated[float, "Length around x axis"],
        yLenght: Annotated[float, "Length around y axis"],
        height: Annotated[float, "Platform height"],
        nJoist: Annotated[int, "Joist number"],
        nDivision: Annotated[int, "Sub divisions per joist"] = 6,
    ) -> None:
        self.nodes: NodesDict = {}
        self.lines: LinesDict = {}
        self.nodetag: int = 0
        self.linetag: int = 0

        self.xLenght: float = xLenght
        self.yLenght: float = yLenght
        self.height: float = height
        self.nJoist: int = nJoist
        self.nDivision: int = nDivision

    def get_new_node_tag(self) -> int:
        self.nodetag += 1
        return self.nodetag

    def get_new_line_tag(self) -> int:
        self.linetag += 1
        return self.linetag

    def get_current_nodes_tag(self) -> int:
        return self.nodetag

    def get_current_line_tag(self) -> int:
        return self.linetag

    def set_nodes(self, nodes: NodesDict) -> None:
        self.nodes = nodes

    def set_lines(self, lines: LinesDict) -> None:
        self.lines = lines

    def set_node_tag(self, new_tag: int) -> None:
        self.nodetag = new_tag

    def set_line_tag(self, new_tag: int) -> None:
        self.linetag = new_tag

    @staticmethod
    def create_frame_data(
        xlength: float, ylength: float, height: float
    ) -> tuple[NodesDict, LinesDict]:
        nodes: NodesDict = {
            1: {"id": 1, "x": 0, "y": 0, "z": 0},
            2: {"id": 2, "x": 0, "y": ylength, "z": 0},
            3: {"id": 3, "x": 0, "y": 0, "z": height},
            4: {"id": 4, "x": 0, "y": ylength, "z": height},
            5: {"id": 5, "x": xlength, "y": 0, "z": 0},
            6: {"id": 6, "x": xlength, "y": ylength, "z": 0},
            7: {"id": 7, "x": xlength, "y": 0, "z": height},
            8: {"id": 8, "x": xlength, "y": ylength, "z": height},
        }
        lines: LinesDict = {
            1: {"id": 1, "Ni": 1, "Nj": 3, "Type": "Column"},
            2: {"id": 2, "Ni": 2, "Nj": 4, "Type": "Column"},
            3: {"id": 3, "Ni": 3, "Nj": 4, "Type": "Beam"},
            4: {"id": 4, "Ni": 6, "Nj": 8, "Type": "Column"},
            5: {"id": 5, "Ni": 5, "Nj": 7, "Type": "Column"},
            6: {"id": 6, "Ni": 3, "Nj": 7, "Type": "Beam"},
            7: {"id": 7, "Ni": 4, "Nj": 8, "Type": "Beam"},
            8: {"id": 8, "Ni": 7, "Nj": 8, "Type": "Beam"},
        }
        return nodes, lines

    def create_nodes_for_joist(self, id: int, eleType: Annotated[str, "Beam or Joist"]) -> list[int]:
        line = self.lines[id]
        node_i = self.nodes[line["Ni"]]
        node_j = self.nodes[line["Nj"]]
        self.lines.pop(id, None)

        vx = node_j["x"] - node_i["x"]
        vy = node_j["y"] - node_i["y"]
        vz = node_j["z"] - node_i["z"]

        length = (vx**2 + vy**2 + vz**2) ** 0.5
        step_len = length / (self.nJoist + 1)

        ux, uy, uz = vx / length, vy / length, vz / length
        step = (ux * step_len, uy * step_len, uz * step_len)

        new_nodes: list[int] = []
        current_node_id = node_i["id"]

        for i in range(1, self.nJoist + 1):
            new_node_tag = self.get_new_node_tag()
            new_nodes.append(new_node_tag)
            self.nodes[new_node_tag] = {
                "id": new_node_tag,
                "x": node_i["x"] + step[0] * i,
                "y": node_i["y"] + step[1] * i,
                "z": node_i["z"] + step[2] * i,
            }

            new_line_tag = self.get_new_line_tag()
            self.lines[new_line_tag] = {
                "id": new_line_tag,
                "Ni": current_node_id,
                "Nj": new_node_tag,
                "Type": eleType
            }
            current_node_id = new_node_tag

        end_line_tag = self.get_new_line_tag()
        self.lines[end_line_tag] = {
            "id": end_line_tag,
            "Ni": current_node_id,
            "Nj": node_j["id"],
            "Type": eleType

        }
        return new_nodes

    def create_model(
        self,
    ) -> tuple[NodesDict, LinesDict]:
        nodes, lines = self.create_frame_data(
            xlength=self.xLenght, ylength=self.yLenght, height=self.height
        )
        self.set_nodes(nodes)
        self.set_lines(lines)

        self.set_node_tag(max(nodes.keys()))
        self.set_line_tag(max(lines.keys()))

        # Subdivide top beams (lines 3 and 8) and create joists between them
        top_left_nodes = self.create_nodes_for_joist(3, "Beam")
        top_right_nodes = self.create_nodes_for_joist(8, "Beam")

        original_njoist = self.nJoist
        for left_tag, right_tag in zip(top_left_nodes, top_right_nodes):
            new_line_id = self.get_new_line_tag()
            self.lines[new_line_id] = {
                "id": new_line_id,
                "Ni": left_tag,
                "Nj": right_tag,
                "Type": "Joist"
            }

            # Further subdivide this joist
            self.nJoist = self.nDivision
            self.create_nodes_for_joist(new_line_id, "Joist")
            self.nJoist = original_njoist

        return self.nodes, self.lines


class PlatformMixed(Platform):
    def __init__(
        self,
        xLenght: Annotated[float, "Length around x axis"],
        yLenght: Annotated[float, "Length around y axis"],
        height: Annotated[float, "Platform height"],
        nJoist: Annotated[int, "Joist number"],
        TrussDir: Annotated[str, "Axis in wich the truss will be created  `y` or `x`"],
        TrussDepth: Annotated[float, "Truss Depth"] ,
        nDivision: Annotated[int, "Sub divisions per joist"] = 6,
    ) -> None:
        super().__init__(
            xLenght=xLenght,
            yLenght=yLenght,
            height=height,
            nJoist=nJoist,
            nDivision=nDivision,
        )
        self.TrussDir = TrussDir
        self.TrussDepth = TrussDepth

    def create_model(
        self,
    ) -> tuple[NodesDict, LinesDict]:
        nodes, lines = self.create_frame_data(
            xlength=self.xLenght, ylength=self.yLenght, height=self.height
        )

        self.set_nodes(nodes)
        self.set_lines(lines)

        self.set_node_tag(max(nodes.keys()))
        self.set_line_tag(max(lines.keys()))

        # Subdivide top beams (lines 3 and 8) and create joists between them
        # We replace current beams for trusses!
        self.lines.pop(3)
        self.lines.pop(8)

        leftTruss = Truss(
            height=self.TrussDepth,
            width=self.yLenght,
            n_diagonals=self.nJoist + 1,
            xo=0,
            yo=0,
            zo=self.height,
            nodes_id=self.get_current_nodes_tag(),
            lines_id=self.get_current_line_tag(),
            component_name="Left Truss",
            plane="yz",
        )
        nodes, lines = leftTruss.create()
        self.nodes.update(nodes)
        self.lines.update(lines)
        self.set_node_tag(max(nodes.keys()))
        self.set_line_tag(max(lines.keys()))

        rightTruss = Truss(
            height=self.TrussDepth,
            width=self.yLenght,
            n_diagonals=self.nJoist + 1,
            xo=self.xLenght,
            yo=0,
            zo=self.height,
            nodes_id=self.get_current_nodes_tag(),
            lines_id=self.get_current_line_tag(),
            component_name="Left Truss",
            plane="yz",
        )
        nodes, lines = rightTruss.create()
        self.nodes.update(nodes)
        self.lines.update(lines)
        self.set_node_tag(max(nodes.keys()))
        self.set_line_tag(max(lines.keys()))

        original_njoist = self.nJoist
        for left_tag, right_tag in zip(leftTruss.joist_nodes, rightTruss.joist_nodes):
            new_line_id = self.get_new_line_tag()
            self.lines[new_line_id] = {
                "id": new_line_id,
                "Ni": left_tag,
                "Nj": right_tag,
                "Type": "Joist"
            }

            # Further subdivide this joist
            self.nJoist = self.nDivision
            self.create_nodes_for_joist(new_line_id, "Joist")
            self.nJoist = original_njoist

        base_cords = [
            (0, 0),
            (self.xLenght, 0),
            (0, self.yLenght),
            (self.xLenght, self.yLenght),
        ]
        for base_cord in base_cords:
            current_nodes_id = max(list(self.nodes.keys()))
            current_lines_id = max(list(self.lines.keys()))
            new_colums = Columns(
                height=self.height - 0.5,
                xo=base_cord[0],
                yo=base_cord[1],
                zo=0,
                nodes_id=current_nodes_id,
                lines_id=current_lines_id,
                partition=4,
            )

            column_nodes, column_lines = new_colums.create()

            self.nodes.update(column_nodes)
            self.lines.update(column_lines)
        
        self.nodes, self.lines = clean_model(self.nodes, self.lines)

        return self.nodes, self.lines


if __name__ == "__main__":
    from app.geometry.utils import plot_model
    platform = Platform(
        xLenght=8.0, yLenght=14.0, height=4.0, nJoist=7, nDivision=6
    )
    nodes, lines = platform.create_model()
    nodes, lines = clean_model(nodes, lines)
    plot_model(nodes, lines)
