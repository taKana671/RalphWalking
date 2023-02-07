from collections import namedtuple
from functools import partial

from panda3d.core import Vec3, Vec2, LColor, Point3, CardMaker, Point2, Texture, TextureStage
from panda3d.core import GeomVertexFormat, GeomVertexData
from panda3d.core import Geom, GeomTriangles, GeomVertexWriter
from panda3d.core import GeomNode

from panda3d.core import BitMask32
from panda3d.core import NodePath, PandaNode
# from direct.showbase.ShowBase import ShowBase
# from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.bullet import BulletConvexHullShape, BulletBoxShape
from panda3d.bullet import BulletRigidBodyNode
from panda3d.bullet import BulletHingeConstraint

import numpy as np


def prim_vertices(faces):
    start = 0
    for face in faces:
        match num := len(face):
            case 3:
                yield (start, start + 1, start + 2)
            case 4:
                for x, y, z in [(0, 1, 3), (1, 2, 3)]:
                    yield (start + x, start + y, start + z)
            case _:
                for i in range(2, num):
                    if i == 2:
                        yield (start, start + i - 1, start + i)
                    else:
                        yield (start + i - 1, start, start + i)
        start += num





def calc_uv(vertices):
    """
    vertices: list of Vec3
    """
    total = Vec3()
    length = len(vertices)
    for vertex in vertices:
        total += vertex
    center = total / length

    pt = vertices[0]
    vec = pt - center
    radius = sum(v ** 2 for v in vec) ** 0.5

    for vertex in vertices:
        nm = (vertex - center) / radius
        phi = np.arctan2(nm.z, nm.x)
        theta = np.arcsin(nm.y)
        u = (phi + np.pi) / (2 * np.pi)
        v = (theta + np.pi / 2) / np.pi
        yield Vec2(u, v)


def make_geomnode(faces, uv_list):
    format_ = GeomVertexFormat.getV3n3cpt2()
    vdata = GeomVertexData('triangle', format_, Geom.UHStatic)
    vdata.setNumRows(len(faces))

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    # color = GeomVertexWriter(vdata, 'color')
    texcoord = GeomVertexWriter(vdata, 'texcoord')


    for face_pts, uv_pts in zip(faces, uv_list):
        for pt, uv in zip(face_pts, uv_pts):
            vertex.addData3(pt)
            normal.addData3(pt.normalized())
            # color.addData4f(LColor(1, 1, 1, 1))
            texcoord.addData2(uv)
    
    # for pts in faces:
    #     for pt, uv in zip(pts, [(0.0, 1.0), (0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]):
    #         vertex.addData3(pt)
    #         normal.addData3(pt.normalized())
    #         texcoord.addData2(*uv)

    node = GeomNode('geomnode')
    prim = GeomTriangles(Geom.UHStatic)

    for vertices in prim_vertices(faces):
        prim.addVertices(*vertices)

    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node.addGeom(geom)
    return node


class Block(NodePath):

    def __init__(self, cube, name):
        super().__init__(BulletRigidBodyNode(name))
        model = cube.copyTo(self)
        end, tip = model.getTightBounds()
        self.node().addShape(BulletBoxShape((tip - end) / 2))
        self.setCollideMask(BitMask32.bit(1))


class Cylinder(NodePath):

    def __init__(self, cylinder, name):
        super().__init__(BulletRigidBodyNode(name))
        model = cylinder.copyTo(self)
        end, tip = model.getTightBounds()
        self.node().addShape(BulletBoxShape((tip - end) / 2))
        self.setCollideMask(BitMask32.bit(1))


# class Materials(NodePath):

#     def __init__(self, name, parent, np, pos, hpr, scale):
#         super().__init__(BulletRigidBodyNode(name))
#         self.model = np.copyTo(self)
#         self.setPos(pos)
#         self.setHpr(hpr)
#         self.setScale(scale)


# class Block(Materials):

#     def __init__(self, name, parent, np, pos, hpr, scale):
#         super().__init__(self, name, parent, np, pos, hpr, scale)
#         end, tip = self.model.getTightBounds()
#         self.node().addShape(BulletBoxShape((tip - end) / 2))
#         self.setCollideMask(BitMask32.bit(1))


# class Cylinder(Materials):

#     def __init__(self, name, parent, np, pos, hpr, scale):
#         super().__init__(self, name, parent, np, pos, hpr, scale)
#         shape = BulletConvexHullShape()
#         shape.addGeom(self.model.node().getGeom(0))
#         self.node().addShape(shape)
#         self.setCollideMask(BitMask32.bit(1))


class CubeModel(NodePath):

    def __new__(cls, *args, **kargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(CubeModel, cls).__new__(cls)
        return cls._instance

    def __init__(self, nd):
        super().__init__(nd)
        self.setTwoSided(True)


Material = namedtuple('Material', 'pos hpr scale')


class Build:

    def __init__(self, world):
        self.world = world
        self.cube = None
        self.cylinder = None

    def set_tex_scale(self, np, x, z):
        su = x / 2
        sv = z / 3 if z > 1 else z
        np.setTexScale(TextureStage.getDefault(), su, sv)

    def get_hpr(self, horizontal=True, angle=None):
        hpr = Vec3(0, 0, 0)
        if not horizontal:
            hpr.x = 90
        if angle:
            hpr = angle
        return hpr

    def floor(self, name, parent, pos, scale, tex_scale=False):
        hpr = Vec3(0, 90, 0)
        floor = Block(name, parent, self.cube, pos, hpr, scale)
        self.world.attachRigidBody(floor.node())

    def wall(self, name, parent, pos, scale, horizontal=True, angle=None):
        hpr = self.get_hpr(horizontal, angle)
        wall = Block(name, parent, self.cube, pos, hpr, scale)
        self.set_tex_scale(wall, scale.x, scale.z)
        self.world.attachRigidBody(wall.node())

    def door(self, name, parent, pos, scale, wall, horizontal=True, angle=None, left_hinge=True):
        hpr = self.get_hpr(horizontal, angle)
        door = Block(name, parent, self.cube, pos, hpr, scale)
        self.set_tex_scale(door, scale.x, scale.z)

        door.node().setMass(1)
        door.node().setDeactivationEnabled(False)
        self.world.attachRigidBody(door.node())

        end, tip = door.getTightBounds()
        door_size = tip - end
        end, tip = wall.getTightBounds()
        wall_size = tip - end

        door_x = -(door_size.x / 2) if left_hinge else wall_size.x / 2
        wall_x = wall_size.x / 2 if left_hinge else -wall_size.x / 2 

        hinge = BulletHingeConstraint(
            wall.node(),
            door.node(),
            Vec3(wall_x, wall_size.y / 2, 0),
            Vec3(door_x, door_size.y / 2, 0),
            Vec3(0, 1, 0),
            Vec3(0, 1, 0),
            True,
        )
        hinge.setDebugDrawSize(2.0)
        hinge.setLimit(-90, 120, softness=0.9, bias=0.3, relaxation=1.0)
        self.world.attachConstraint(hinge)

    def steps(self):
        pass


class StoneHouse(NodePath):

    def __init__(self, world):
        super().__init__(PandaNode('stoneHouse'))
        self.reparentTo(base.render)
        self.world = world
        self.center = Point3(-5, 10, 0)  # -5
        self.setPos(self.center)
        self.cube = self.make_cube()
        self.cylinder = self.make_cylinder()
        self.build()

    def make_cylinder(self):
        vertices = DECAGONAL_PRISM['vertices']
        idx_faces = DECAGONAL_PRISM['faces']
        vertices = [Vec3(vertex) for vertex in vertices]
        faces = [[vertices[i] for i in face] for face in idx_faces]
        uv_list = [uv for uv in calc_uv(vertices)]
        uv = [[uv_list[i] for i in face] for face in idx_faces]

        geomnode = make_geomnode(faces, uv)
        cylinder = NodePath(geomnode)
        cylinder.setTwoSided(True)

        return cylinder


    def make_cube(self):
        vertices = CUBE['vertices']
        idx_faces = CUBE['faces']
        vertices = [Vec3(vertex) for vertex in vertices]
        faces = [[vertices[i] for i in face] for face in idx_faces]
        # print(faces)
        # uv_list = [uv for uv in calc_uv(vertices)]
        # uv = [[uv_list[i] for i in face] for face in idx_faces]
        # print(uv)

        # uv = [Vec2(0, 2.0), Vec2(0, 0), Vec2(2.0, 0), Vec2(2.0, 2.0)]
        # uv = [Vec2(0, 1.0), Vec2(0, 0), Vec2(1.0, 0), Vec2(1.0, 1.0)]
        # uv = [uv for _ in range(6)]

        # uv = [
        #     [Vec2(1, 1), Vec2(0.75, 1), Vec2(0.75, 0), Vec2(1, 0)],
        #     [Vec2(0, 1), Vec2(0, 0), Vec2(0.25, 0), Vec2(0.25, 1)],
        #     [Vec2(0, 1), Vec2(0.25, 1), Vec2(0.5, 1), Vec2(0.75, 1)],
        #     [Vec2(0.75, 1), Vec2(0.5, 1), Vec2(0.5, 0), Vec2(0.75, 0)],
        #     [Vec2(0.5, 1), Vec2(0.25, 1), Vec2(0.25, 0), Vec2(0.5, 0)],
        #     [Vec2(1, 0), Vec2(0.75, 0), Vec2(0.5, 0), Vec2(0.25, 0)]
        # ]

        uv = [
            [Vec2(1, 1), Vec2(0.9, 1), Vec2(0.9, 0), Vec2(1, 0)],
            [Vec2(0, 1), Vec2(0, 0), Vec2(0.4, 0), Vec2(0.4, 1)],
            [Vec2(0, 1), Vec2(0.4, 1), Vec2(0.5, 1), Vec2(0.9, 1)],
            [Vec2(0.9, 1), Vec2(0.5, 1), Vec2(0.5, 0), Vec2(0.9, 0)],
            [Vec2(0.5, 1), Vec2(0.4, 1), Vec2(0.4, 0), Vec2(0.5, 0)],
            [Vec2(1, 0), Vec2(0.9, 0), Vec2(0.5, 0), Vec2(0.4, 0)]
        ]

        geomnode = make_geomnode(faces, uv)
        # cube = CubeModel(geomnode) copyto -> NodePathを継承して作った自作クラスのメソッドはコピーされない
        cube = NodePath(geomnode)
        cube.setTwoSided(True)
        return cube

    def _build(self, class_, model, parent, name, materials, tex_scale=True):
        for i, m in enumerate(materials):
            np = class_(model, f'{name}_{i}')
            np.reparentTo(parent)
            np.setPos(m.pos)
            np.setHpr(m.hpr)
            np.setScale(m.scale)
            if tex_scale:
                su = m.scale.x / 2
                sv = z / 3 if (z := m.scale.z) > 1 else z
                np.setTexScale(TextureStage.getDefault(), su, sv)

            # if name.startswith('door'):
            #     np.node().setMass(1)
            #     np.node().setDeactivationEnabled(False)
            
            self.world.attachRigidBody(np.node())

    def make_textures(self):
        self.wall_tex = base.loader.loadTexture('textures/fieldstone.jpg')
        self.wall_tex.setWrapU(Texture.WM_repeat)
        self.wall_tex.setWrapV(Texture.WM_repeat)

        self.floor_tex = base.loader.loadTexture('textures/iron.jpg')
        self.floor_tex.setWrapU(Texture.WM_repeat)
        self.floor_tex.setWrapV(Texture.WM_repeat)

        self.fence_tex = base.loader.loadTexture('textures/concrete2.jpg')

        self.door_tex = base.loader.loadTexture('textures/7-8-19a-300x300.jpg')
        self.door_tex.setWrapU(Texture.WM_repeat)
        self.door_tex.setWrapV(Texture.WM_repeat)


    def build(self):
        self.make_textures()

        walls = NodePath(PandaNode('walls'))
        walls.reparentTo(self)
        floors = NodePath(PandaNode('floors'))
        floors.reparentTo(self)
        fences = NodePath(PandaNode('fences'))
        fences.reparentTo(self)

        assemble_blocks = partial(self._build, Block, self.cube)

        # the 1st floor
        # Floor(Material(Point3(0, 0, -3.5), Vec3(0, 90, 0), Vec3(32, 1, 24)))
        materials = [Material(Point3(0, 0, -3.5), Vec3(0, 90, 0), Vec3(32, 1, 24))]
        assemble_blocks(floors, 'floor1', materials)

        # rear wall on the lst floor
        materials = [Material(Point3(0, 8.25, 0), Vec3(0, 0, 0), Vec3(12, 0.5, 6))]
        assemble_blocks(walls, 'wall1_rear', materials)

        # left wall on the 1st floor
        materials = [Material(Point3(-5.75, 0, 0), Vec3(90, 0, 0), Vec3(16, 0.5, 6))]
        assemble_blocks(walls, 'wall1_left', materials)

        # right wall on the 1st floor
        materials = [
            Material(Point3(5.75, 0, -2), Vec3(90, 0, 0), Vec3(16, 0.5, 2)),   # under
            Material(Point3(5.75, 3, 0), Vec3(90, 0, 0), Vec3(10, 0.5, 2)),    # middle back
            Material(Point3(5.75, -7, 0), Vec3(90, 0, 0), Vec3(2, 0.5, 2)),    # middle front
            Material(Point3(5.75, 0, 2), Vec3(90, 0, 0), Vec3(16, 0.5, 2)),    # top
        ]
        assemble_blocks(walls, 'wall1_right', materials)

        # front wall on the 1st floor
        materials = [
            Material(Point3(-4, -8.25, -1), Vec3(0, 0, 0), Vec3(4, 0.5, 4)),    # front left
            Material(Point3(4, -8.25, -1), Vec3(0, 0, 0), Vec3(4, 0.5, 4)),     # front right
            Material(Point3(0, -8.25, 2.0), Vec3(0, 0, 0), Vec3(12, 0.5, 2)),   # front top
        ]
        assemble_blocks(walls, 'wall1_front', materials)

        # 2nd floor
        materials = [
            Material(Point3(-4, 4.25, 3.25), Vec3(0, 90, 0), Vec3(20, 0.5, 8.5)),  # back
            Material(Point3(4, -4.25, 3.25), Vec3(0, 90, 0), Vec3(20, 0.5, 8.5)),  # flont
            Material(Point3(-10, -1, 3.25), Vec3(0, 90, 0), Vec3(8, 0.5, 2)),      # front doors
            Material(Point3(4, -8.25, 4), Vec3(0, 90, 90), Vec3(0.5, 1, 20)),      # fence
            Material(Point3(-5.75, -5, 4), Vec3(0, 90, 0), Vec3(0.5, 1, 6)),       # fence
            Material(Point3(13.75, -4, 4), Vec3(0, 90, 0), Vec3(0.5, 1, 8)),       # fence
            Material(Point3(10, 0.25, 3.75), Vec3(0, 90, 90), Vec3(0.5, 1.5, 8)),  # fence
        ]
        assemble_blocks(floors, 'floor2', materials)

        # rear wall on the 2nd floor
        materials = [Material(Point3(-4, 8.25, 6.5), Vec3(0, 0, 0), Vec3(20, 0.5, 6))]
        assemble_blocks(walls, 'wall2_back', materials)

        # left wall on the 2nd floor
        materials = [
            Material(Point3(-13.75, 4, 4.5), Vec3(90, 0, 0), Vec3(8, 0.5, 2)),
            Material(Point3(-13.75, 1.5, 6.5), Vec3(90, 0, 0), Vec3(3, 0.5, 2)),
            Material(Point3(-13.75, 6.5, 6.5), Vec3(90, 0, 0), Vec3(3, 0.5, 2)),
            Material(Point3(-13.75, 4, 8.5), Vec3(90, 0, 0), Vec3(8, 0.5, 2)),
        ]
        assemble_blocks(walls, 'wall2_left', materials)

        # right wall on the 2nd floor
        materials = [Material(Point3(5.75, 4.25, 6.5), Vec3(90, 0, 0), Vec3(7.5, 0.5, 6))]
        assemble_blocks(walls, 'wall2_right', materials)

        # front wall on the 2nd floor
        materials = [
            Material(Point3(-12.5, 0.25, 5.5), Vec3(0, 0, 0), Vec3(2, 0.5, 4)),
            Material(Point3(-7.25, 0.25, 5.5), Vec3(0, 0, 0), Vec3(2.5, 0.5, 4)),
            Material(Point3(-9.75, 0.25, 8.5), Vec3(0, 0, 0), Vec3(7.5, 0.5, 2)),
            Material(Point3(0, 0.25, 4.5), Vec3(0, 0, 0), Vec3(12, 0.5, 2)),
            Material(Point3(-4, 0.25, 6.5), Vec3(0, 0, 0), Vec3(4, 0.5, 2)),    # front left
            Material(Point3(4, 0.25, 6.5), Vec3(0, 0, 0), Vec3(4, 0.5, 2)),
            Material(Point3(0, 0.25, 8.5), Vec3(0, 0, 0), Vec3(12, 0.5, 2)),
        ]
        assemble_blocks(walls, 'wall2_front', materials)

        # roof
        materials = [Material(Point3(-4, 4.25, 9.75), Vec3(0, 90, 0), Vec3(20, 0.5, 8.5))]
        assemble_blocks(floors, 'roof', materials)

        # steps
        materials = [Material(Point3(-10, -7.5 + i, -2.5 + i), Vec3(0, 90, 0), Vec3(8, 1, 1)) for i in range(6)]
        assemble_blocks(floors, 'steps', materials)

        # fences for steps
        materials = []
        h = 0
        for i in range(8):
            if i <= 6:
                h = i
            pos = Point3(-13.75, -7.5 + i, -1.5 + h)
            materials.append(Material(pos, Vec3(0, 0, 0), Vec3(0.1, 0.1, 5)))
        self._build(Cylinder, self.cylinder, fences, 'fences', materials, False)

        doors = NodePath(PandaNode('doors'))
        doors.reparentTo(self)
        
        materials = [
            Material(Point3(-1, -8.25, -1), Vec3(0, 0, 0), Vec3(2, 0.5, 4))
        ]
        self._build(Block, self.cube, doors, 'doors', materials)
        self.set_hinge('wall1_front_0', 'doors_0', Point3(2, 0.25, 0), Point3(-1, 0.25, 0))

        doors.setTexture(self.door_tex)
        fences.setTexture(self.fence_tex)
        walls.setTexture(self.wall_tex)
        floors.setTexture(self.floor_tex)

    def set_hinge(self, name_a, name_b, piv_a, piv_b):

        node_a = self.find(f'*/{name_a}')
        node_b = self.find(f'*/{name_b}')

        node_b.node().setMass(1)
        node_b.node().setDeactivationEnabled(False)
        hinge = BulletHingeConstraint(
            node_a.node(),
            node_b.node(),
            piv_a,
            piv_b,
            Vec3(0, 1, 0),
            Vec3(0, 1, 0),
            True,
        )
        hinge.setDebugDrawSize(2.0)
        hinge.setLimit(-90, 120, softness=0.9, bias=0.3, relaxation=1.0)
        self.world.attachConstraint(hinge)
        
        
        # door = [Point3(0, -6.25, 1), Vec3(90, 90, 0), Vec3(0.5, 8, 4)]
        #     # [Point3(2, -6.25, 1), Vec3(90, 90, 0), Vec3(0.5, 8, 2)]

        # tex = base.loader.loadTexture('textures/iron.jpg')
        # tex.setWrapU(Texture.WM_repeat)
        # tex.setWrapV(Texture.WM_repeat)

        # import pdb; pdb.set_trace()
        
        # door = Block(
        #     self.cube,
        #     Point3(0, -6.25, 1) + self.center,
        #     Vec3(90, 90, 0),
        #     Vec3(0.5, 8, 4),
        #     'door'
        # )
        # door.reparentTo(self)
        # door.setTexture(tex)
        # # door.setTexScale(TextureStage.getDefault(), 0.5, 1)
        # door.node().setMass(1)
        # door.node().setDeactivationEnabled(False)
        # self.world.attachRigidBody(door.node())


        # wall = self.getChild(4)
        # # hinge = BulletHingeConstraint(
        # #     wall.node(),
        # #     door.node(),
        # #     Point3(0.25, 0, 2),
        # #     Point3(0.25, 0, -2),
        # #     Vec3(0, 1, 0),
        # #     Vec3(0, 1, 0),
        # #     True,
        # # )
        # # hinge.setDebugDrawSize(2.0)
        # # hinge.setLimit(-90, 120, softness=0.9, bias=0.3, relaxation=1.0)
        # # self.world.attachConstraint(hinge)



CUBE = {
    'vertices': [
        (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5),
        (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)
    ],
    'faces': [
        (0, 1, 5, 4), (0, 4, 7, 3), (0, 3, 2, 1),
        (1, 2, 6, 5), (2, 3, 7, 6), (4, 5, 6, 7)
    ]
}

DECAGONAL_PRISM = {
    'vertices': [
        (-0.29524181, -0.90866085, 0.29524181),
        (-0.77295309, -0.56158329, 0.29524181),
        (-0.95542256, 0.0, 0.29524181),
        (-0.77295309, 0.56158329, 0.29524181),
        (-0.29524181, 0.90866085, 0.29524181),
        (0.29524181, 0.90866085, 0.29524181),
        (0.77295309, 0.56158329, 0.29524181),
        (0.95542256, -0.0, 0.29524181),
        (0.77295309, -0.56158329, 0.29524181),
        (0.29524181, -0.90866085, 0.29524181),
        (-0.29524181, -0.90866085, -0.2952418),
        (-0.77295309, -0.56158329, -0.2952418),
        (-0.95542256, 0.0, -0.29524181),
        (-0.77295309, 0.56158329, -0.29524181),
        (-0.29524181, 0.90866085, -0.29524181),
        (0.29524181, 0.90866085, -0.29524181),
        (0.77295309, 0.56158329, -0.29524181),
        (0.95542256, -0.0, -0.29524181),
        (0.77295309, -0.56158329, -0.29524181),
        (0.29524181, -0.90866085, -0.29524181),
    ],
    'faces': [
        (0, 1, 11, 10),
        (0, 10, 19, 9),
        (0, 9, 8, 7, 6, 5, 4, 3, 2, 1),
        (1, 2, 12, 11),
        (2, 3, 13, 12),
        (3, 4, 14, 13),
        (4, 5, 15, 14),
        (5, 6, 16, 15),
        (6, 7, 17, 16),
        (7, 8, 18, 17),
        (8, 9, 19, 18),
        (10, 11, 12, 13, 14, 15, 16, 17, 18, 19),
    ]
}



# >>> from panda3d.core import Vec3
# >>> li = [(-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)]
# >>> li = [Vec3(item) for item in li]
# >>> li
# [LVector3f(-0.5, -0.5, 0.5), LVector3f(-0.5, 0.5, 0.5), LVector3f(0.5, 0.5, 0.5), LVector3f(0.5, -0.5, 0.5), LVector3f(-0.5, -0.5, -0.5), LVector3f(-0.5, 0.5, -0.5), LVector3f(0.5, 0.5, -0.5), LVector3f(0.5, -0.5, -0.5)]
# >>> min(li)
# LVector3f(-0.5, -0.5, -0.5)
# >>> max(li)
# LVector3f(0.5, 0.5, 0.5)
# >>> left_bottom = min(li)
# >>> right_top = max(li)
# >>> height = right_top.z - left_bottom.z
# >>> height
# 1.0
# >>> width = right_top.x - left_bottom.x
# >>> width
# 1.0
# >>> pt = li[0]
# >>> pt
# LVector3f(-0.5, -0.5, 0.5)
# >>> (pt.x - right_bottom.x) / width
# Traceback (most recent call last):
#   File "<stdin>", line 1, in <module>
# NameError: name 'right_bottom' is not defined. Did you mean: 'left_bottom'?
# >>> (pt.x - left_bottom.x) / width
# 0.0
# >>> (pt.z - left_bottom.z) / height
# 1.0
# >>> li2 = [((item.x - left_bottom.x) / width, (item.z - left_bottom.z) / height) for item in li]
# >>> li2
# [(0.0, 1.0), (0.0, 1.0), (1.0, 1.0), (1.0, 1.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (1.0, 0.0)]
# >>>