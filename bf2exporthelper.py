# To make this add-on installable, create an extension with it:
# https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html
bl_info = {
    "name": "BF2 Export Helper",
    "author": "[R-DEV]PotatoLord, Project Reality Team",
    "version": (0, 21),
    "blender": (4, 5, 0),
    "location": "View3d > N",
    "description": "To be used in conjunction with BF2 Tools",
    "warning": "",
    "doc_url": "",
    "category": "",
}

import bpy
from bpy.types import (Panel, Operator)


def add_triangulate(obj):
    obj.modifiers.new(name="Triangulate", type='TRIANGULATE')


def rename_uv_to_uv0(obj):
    if obj.type == 'MESH' and obj.data.uv_layers:
        obj.data.uv_layers[0].name = "UV0"


def gen_lod(obj, decimate_ratio):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    child_parents = {}
    for child in obj.children:
        child_parents[child] = child.matrix_world.copy()
        child.parent = None

    bpy.ops.object.duplicate()
    new_obj = bpy.context.active_object

    for child, matrix in child_parents.items():
        child.parent = obj
        child.matrix_world = matrix

    decimate_mod = new_obj.modifiers.new(name="Decimate", type='DECIMATE')
    decimate_mod.ratio = decimate_ratio
    decimate_mod.use_collapse_triangulate = False
    add_triangulate(new_obj)
    rename_uv_to_uv0(new_obj)
    return new_obj


def duplicate_obj(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    child_parents = {}
    for child in obj.children:
        child_parents[child] = child.matrix_world.copy()
        child.parent = None

    bpy.ops.object.duplicate()
    new_obj = bpy.context.active_object

    for child, matrix in child_parents.items():
        child.parent = obj
        child.matrix_world = matrix

    add_triangulate(new_obj)
    rename_uv_to_uv0(new_obj)
    return new_obj


def apply_scale(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(scale=True)


def gen_lod_chain(original, children, count, base_name, prefix):
    lod_objects = []
    for i in range(count):
        ratio = 0.5 - (0.4 * i / max(count - 1, 1))
        lod = gen_lod(original, ratio)
        lod.name = f"G1L{i + 1}__{base_name}"
        for child in children:
            child_lod = gen_lod(child, ratio)
            child_lod.name = f"G1L{i + 1}__{child.name.replace(prefix, '')}"
            child_lod.parent = lod
            child_lod.matrix_parent_inverse = lod.matrix_world.inverted()
        lod_objects.append(lod)
    return lod_objects


def make_empty(name, collection):
    empty = bpy.data.objects.new(name, None)
    collection.objects.link(empty)
    return empty


class ButtonOperator(bpy.types.Operator):
    """Generate LODs"""
    bl_idname = "bf2helper.1"
    bl_label = "Generate LODs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        original = bpy.context.active_object
        count = context.scene.lods_num
        base_name = original.name
        children = list(original.children)

        original.name = f"G1L0__{base_name}"
        for child in children:
            child.name = f"G1L0__{child.name}"

        add_triangulate(original)
        rename_uv_to_uv0(original)
        for child in children:
            add_triangulate(child)
            rename_uv_to_uv0(child)

        gen_lod_chain(original, children, count, base_name, 'G1L0__')
        return {'FINISHED'}


class HierarchyOperator(bpy.types.Operator):
    """Also sets all UVs to UV0"""
    bl_idname = "bf2helper.2"
    bl_label = "Generate Hierarchy + LODs"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Before generating, please ensure the following:", icon='ERROR')
        layout.separator(factor=0.5)
        layout.label(text="  • Apply all transforms (Ctrl+A)")
        layout.label(text="  • Apply all modifiers")
        layout.label(text="  • Active object must be the parent")

    def execute(self, context):
        original = bpy.context.active_object
        count = context.scene.lods_num
        base_name = original.name
        children = list(original.children)
        collection = original.users_collection[0]
        scale_up = context.scene.g0_scale_up
        scale_percent = context.scene.g0_scale_percent
        scale_factor = 1 + (scale_percent / 100) if scale_up else 1 - (scale_percent / 100)

        bundled = make_empty(f"bundledmesh__{base_name}", collection)
        g0 = make_empty(f"G0__{base_name}", collection)
        g0.parent = bundled
        g1 = make_empty(f"G1__{base_name}", collection)
        g1.parent = bundled

        add_triangulate(original)
        rename_uv_to_uv0(original)
        for child in children:
            add_triangulate(child)
            rename_uv_to_uv0(child)

        if scale_up:
            original.name = f"G1L0__{base_name}"
            for child in children:
                child.name = f"G1L0__{child.name}"

            lod_objects = gen_lod_chain(original, children, count, base_name, 'G1L0__')

            g0l0 = duplicate_obj(original)
            g0l0.name = f"G0L0__{base_name}"
            g0l0.scale = original.scale * scale_factor
            g0l0.parent = g0
            g0l0.matrix_parent_inverse = g0.matrix_world.inverted()
            

            for child in children:
                child_base_name = child.name.replace('G1L0__', '')
                g0_child = duplicate_obj(child)
                g0_child.name = f"G0L0__{child_base_name}"
                g0_child.scale = child.scale * scale_factor
                g0_child.location = g0l0.location + (child.location - g0l0.location) * scale_factor
                g0_child.parent = g0l0
                g0_child.matrix_parent_inverse = g0l0.matrix_world.inverted()

            original.parent = g1
            original.matrix_parent_inverse = g1.matrix_world.inverted()
            for lod in lod_objects:
                lod.parent = g1
                lod.matrix_parent_inverse = g1.matrix_world.inverted()

        else:
            original.name = f"G0L0__{base_name}"
            for child in children:
                child.name = f"G0L0__{child.name}"

            g1l0 = duplicate_obj(original)
            g1l0.name = f"G1L0__{base_name}"
            g1l0.scale = original.scale * scale_factor
            apply_scale(g1l0)

            g1l0_children = []
            for child in children:
                child_base_name = child.name.replace('G0L0__', '')
                g1l0_child = duplicate_obj(child)
                g1l0_child.name = f"G1L0__{child_base_name}"
                g1l0_child.scale = child.scale * scale_factor
                g1l0_child.location = g1l0.location + (child.location - g1l0.location) * scale_factor
                apply_scale(g1l0_child)
                g1l0_child.parent = g1l0
                g1l0_child.matrix_parent_inverse = g1l0.matrix_world.inverted()
                g1l0_children.append((g1l0_child, child_base_name))

            lod_objects = gen_lod_chain(g1l0, [c for c, _ in g1l0_children], count, base_name, 'G1L0__')

            original.parent = g0
            original.matrix_parent_inverse = g0.matrix_world.inverted()
            for child in children:
                child.parent = original
                child.matrix_parent_inverse = original.matrix_world.inverted()

            g1l0.parent = g1
            g1l0.matrix_parent_inverse = g1.matrix_world.inverted()
            for lod in lod_objects:
                lod.parent = g1
                lod.matrix_parent_inverse = g1.matrix_world.inverted()

        return {'FINISHED'}


class CustomPanel(bpy.types.Panel):
    bl_label = f"BF2 Export Helper v{'.'.join(str(v) for v in bl_info['version'])}"
    bl_idname = "OBJECT_PT_bf2helper"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BF2 Helper"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="Bundledmesh Hierarchy Formatter", icon='EMPTY_AXIS')

        split = box.split(factor=0.4)
        split.label(text="LOD Count")
        split.prop(scene, "lods_num", text="")

        box.operator(ButtonOperator.bl_idname, text="Generate LODs Only", icon='MOD_DECIM')

        split = box.split(factor=0.4)
        split.label(text="Current is")
        row = split.row(align=True)
        row.prop(scene, "g0_scale_up", text="G1L0", toggle=True)
        row.prop(scene, "g0_scale_up", text="G0L0", toggle=True, invert_checkbox=True)

        split = box.split(factor=0.4)
        split.label(text="Scale Factor")
        split.prop(scene, "g0_scale_percent", text="")

        big_row = box.row()
        big_row.scale_y = 2.0
        big_row.operator(HierarchyOperator.bl_idname, text="Generate Hierarchy + LODs", icon='EMPTY_AXIS')


from bpy.utils import register_class, unregister_class

_classes = [
    ButtonOperator,
    HierarchyOperator,
    CustomPanel,
]

def register():
    bpy.types.Scene.lods_num = bpy.props.IntProperty(name="LOD Count (Not including LOD0)", default=3, min=1, max=10)
    bpy.types.Scene.g0_scale_up = bpy.props.BoolProperty(
        name="Scale Up",
        default=True,
        description="G1L0: Selected object is the G1L0, G0L0 will be scaled up from it.\nG0L0: Selected object is the G0L0, G1L0 will be scaled down from it."
    )
    bpy.types.Scene.g0_scale_percent = bpy.props.FloatProperty(name="Scale %", default=0.0, min=0.0, max=100.0)
    for cls in _classes:
        register_class(cls)

def unregister():
    del bpy.types.Scene.lods_num
    del bpy.types.Scene.g0_scale_up
    del bpy.types.Scene.g0_scale_percent
    for cls in _classes:
        unregister_class(cls)

if __name__ == "__main__":
    register()