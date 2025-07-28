from typing import TypedDict, Annotated, Literal, Union



class NodeInfo(TypedDict):
    id: int
    x: float
    y: float
    z: float


class LineInfo(TypedDict):
    id: int
    Ni: int
    Nj: int
    Type: str

MemberType = Literal["Truss Diagonal", "Joist", "Beam", "Column", "Truss Chord"]

class CrossSectionInfo(TypedDict):
    name: str
    id: int
    A: Annotated[float, "Area"]
    Iz: Annotated[float, "Inertia around z, Strong Axis"]
    Iy: Annotated[float, "Inertia around y, Weak Axis"]
    Jxx: Annotated[float, "Torsional Inertia"]
    b: Annotated[float, "Section width"]
    h: Annotated[float, "Section height"]


class MemberInfo(TypedDict):
    line_id: int
    cross_section_id: int
    material_name: Literal["Concrete", "Steel"]


class NodeMass(TypedDict):
    mass_x: float
    mass_y: float
    mass_z: float


# Aliases
NodesDict = dict[int, NodeInfo]
LinesDict = dict[int, LineInfo]
CrossSectionsDict = dict[int, CrossSectionInfo]
MembersDict = dict[int, MemberInfo]
MassDict = dict[int, NodeMass]

Vec3 = tuple[float, float, float]


# Materials
class Steel:
    name: Literal["Steel"] = "Steel"
    G: float = 0.25 * 10**3
    gamma: float = 7.85 * 10**-5
    E: float = 200 * 10**3
    units: Literal["N,mm"] = "N,mm"


class Concrete:
    name: Literal["Concrete"] = "Concrete"
    gamma: float = 2.5 * 10**-5
    E: float = 26_700.0
    units: Literal["N,mm"] = "N,mm"
    G: float     = E / (2 * 1.2)


MaterialName = Literal["Steel", "Concrete"]
MaterialType = Union[Steel, Concrete]
MaterialDictType = dict[MaterialName, MaterialType]

material_dict: MaterialDictType = {
    "Steel": Steel(),
    "Concrete": Concrete(),
}

steel_cost: float = 3.81 # Euros