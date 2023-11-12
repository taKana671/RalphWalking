from panda3d.core import AmbientLight, DirectionalLight
from panda3d.core import NodePath, PandaNode
from panda3d.core import Vec3, Point3, LColor


class BasicAmbientLight(NodePath):

    def __init__(self):
        super().__init__(AmbientLight('ambient_light'))
        base.render.set_light(self)
        self.set_brightness()
        self.reparent_to(base.render)

    def set_brightness(self, color=None):
        if color is None:
            color = LColor(0.6, 0.6, 0.6, 1)

        self.node().set_color(color)


class BasicDayLight(NodePath):

    def __init__(self, parent):
        super().__init__(DirectionalLight('directional_light'))
        self.node().get_lens().set_film_size(200, 200)
        self.node().get_lens().set_near_far(10, 200)
        self.set_pos_hpr(Point3(0, 0, 50), Vec3(-30, -45, 0))
        self.node().set_shadow_caster(True, 8192, 8192)

        state = self.node().get_initial_state()
        temp = NodePath(PandaNode('temp_np'))
        temp.set_state(state)
        temp.set_depth_offset(-3)
        self.node().set_initial_state(temp.get_state())

        base.render.set_light(self)
        base.render.set_shader_auto()
        self.set_brightness()
        self.reparent_to(parent)

    def set_brightness(self, color=None):
        if color is None:
            color = LColor(1, 1, 1, 1)

        self.node().set_color(color)
