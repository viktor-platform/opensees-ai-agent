import openseespy.opensees as ops
from app.types import (
    Vec3,
    NodesDict,
    LinesDict,
    MembersDict,
    MaterialDictType,
    MassDict,
    CrossSectionsDict,
    material_dict,
)
from app.opensees.utils import v_cross, v_sub, v_norm
from app.geometry.utils import get_nodes_by_z
from collections import defaultdict
from typing import DefaultDict, Annotated


class Model:
    def __init__(
        self,
        nodes: NodesDict,
        lines: LinesDict,
        cross_sections: CrossSectionsDict,
        members: MembersDict,
        nodesWithLoad: Annotated[list[int] | None, "Joist Nodes"] = None,
        nodalLoadMagnitud: Annotated[float | None, "Load to be applied in Newton per Node"] = None
    ) -> None:
        self.nodes = nodes
        self.lines = lines
        self.cross_sections = cross_sections
        self.members = members
        self.materials:MaterialDictType = material_dict
        self.mass: MassDict = {}
        self.g = 10000 #9800
        self.loadsDict: DefaultDict[int, float] = defaultdict(float)
        self.nodesWithLoad = nodesWithLoad
        self.nodalLoadMagnitud = nodalLoadMagnitud

    def create_nodes(self) -> None:
        for n in self.nodes.values():
            ops.node(n["id"], n["x"], n["y"], n["z"])

    def _define_elastic_section(
        self,
        section_id: int,
        rotation: float,
        E: float,
        G_mod: float,
        N: int,
    ) -> None:
        """
        Define an elastic section and a Lobatto integration rule.
        Axis swap when rotation ≠ 0.
        """
        cs = self.cross_sections[section_id]
        if rotation != 0.0:
            Iz, Iy = cs["Iy"], cs["Iz"]
        else:
            Iz, Iy = cs["Iz"], cs["Iy"]
        ops.section(
            "Elastic",
            section_id,
            E,
            cs["A"],
            Iz,
            Iy,
            G_mod,
            cs["Jxx"],
        )
        ops.beamIntegration("Lobatto", section_id, section_id, N)


    def assign_support(self)->None:
        ground_nodes = get_nodes_by_z(self.nodes, z=0)
        for node_tag in ground_nodes:
            ops.fix(node_tag, 1,1,1,1,1,1)

    def create_beam_elements(
        self,
        z_global: Vec3 = (0,0,1),
        N: int = 10,
        verbose: bool = False,
    ) -> None:
        """
        Create geometric transformations, sections, forceBeamColumn
        elements, and update the lumped nodal mass dictionary.
        """

        section_set: set[int] = set()
        for member in self.members.values():
            line_id = member["line_id"]
            section_id = member["cross_section_id"]
            material_name = member["material_name"]
            
            # Geometry
            line = self.lines[line_id]
            node_i = self.nodes[line["Ni"]]
            node_j = self.nodes[line["Nj"]]


            xi: Vec3 = (node_i["x"], node_i["y"], node_i["z"])
            xj: Vec3 = (node_j["x"], node_j["y"], node_j["z"])
            x_axis: Vec3 = v_sub(xi, xj)
            vec_xz: Vec3 = v_cross(x_axis, z_global)

            # Material
            material = self.materials[material_name]
            E,G,gamma = material.E, material.G, material.gamma
                # Elastic member -> rotation = 0
            if section_id not in section_set:
                self._define_elastic_section(section_id, 0, E, G, N)
                section_set.add(section_id)

            # Since I'm not using numpy this make opensees happy.
            vc2 = (1e-29, -1.0, 0)

            # Geometric transformation with original conditions
            if v_norm(vec_xz) == 0.0:
                ops.geomTransf("Linear", line_id, *vc2)
            else:
                # non-zero cross-product, apply vec_xz
                # the nested check for purely horizontal Z stays the same
                if node_i["z"] - node_j["z"] == 0.0:

                    ops.geomTransf("Linear", line_id, *vec_xz)
                else:
                    # We can implement the logic for truss element (diagonal elements)
                    ops.geomTransf("Linear", line_id, *vec_xz)
                    
                    # Element
            ops.element(
                "forceBeamColumn",
                line_id,
                node_i["id"],
                node_j["id"],
                line_id, # geom tranformation
                section_id,
            )

            # Lumped mass
            L = v_norm(x_axis)
            area = self.cross_sections[section_id]["A"]
            m_node = area * L * gamma / (2.0 * self.g)
            for tag in (node_i["id"], node_j["id"]):
                nm = self.mass.setdefault(
                    tag, {"mass_x": 0.0, "mass_y": 0.0, "mass_z": 0.0}
                )
                nm["mass_x"] += m_node
                nm["mass_y"] += m_node
                nm["mass_z"] += m_node

            if verbose:
                print(
                    f"Line {line_id}: section {section_id}, "
                    f"nodes {node_i['id']}–{node_j['id']}",
                    f"Cross Section name: {self.cross_sections[section_id]["name"]}"
                )
    
    def create_loads(self):
        """Create self weight load and point loads"""
        for notetag, mass_values in self.mass.items():
            # Mass in opensees is N/g * g to loads
            self.loadsDict[notetag] += mass_values["mass_z"]*self.g

        if self.nodesWithLoad and self.nodalLoadMagnitud:
            for nodetag in self.nodesWithLoad:
                self.loadsDict[nodetag] += self.nodalLoadMagnitud
            
        for nodetag, loadMag in self.loadsDict.items():    
            ops.load(nodetag, 0, 0, -loadMag, 0, 0, 0)


    def create_model(self):
        ops.wipe()
        # Creates Opensees Model
        ops.model('basic','-ndm',3,'-ndf',6)
        # Create nodes
        self.create_nodes()
        # ops.getNodeTags()
        # Create beam elements
        self.create_beam_elements(verbose=False)
        # Create Support Nodes
        self.assign_support()
        # vfo.plot_model()

    def run_model(self):
        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        self.create_loads()

        ops.system('BandGen')
        ops.constraints('Plain')
        ops.numberer('Plain')
        ops.algorithm('Linear')
        ops.integrator('LoadControl',1)
        ops.analysis('Static')
        ops.analyze(1)
        ops.reactions()
        return ops


    def __repr__(self) -> str:
        unique_cc = {cs["name"] for cs in self.cross_sections.values()}
        format_names = ", ".join(unique_cc)
        return (
            f"<Model(NoNodes={len(self.nodes)}, "
            f"NoLines={len(self.lines)}, "
            f"NoMembers={len(self.members)}, "
            f"CrossSections={format_names})>"
        )
    

def calculate_displacements(lines:LinesDict, nodes:NodesDict):
    disp_by_type: DefaultDict[str, list[float]] = defaultdict(list)
    disp_dict: dict[int, float] = {}
    for lineargs in lines.values():
        for node in (lineargs["Ni"], lineargs["Nj"]):
            disp = ops.nodeDisp(node)
            disp_z = disp[2]
            disp_by_type[lineargs["Type"]].append(disp_z)

            if node not in disp_dict:
                disp_dict[node] = disp_z
                        
    max_disp_by_type = {eletype: min(disp_list) for eletype, disp_list in  disp_by_type.items()}   

    for node in nodes:
        disp = ops.nodeDisp(node)
        disp_z = disp[2]
        disp_dict[node] = disp_z

    
    return max_disp_by_type, disp_dict



