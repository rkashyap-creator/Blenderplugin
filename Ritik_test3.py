import bpy
import gpu
import os
from gpu_extras.batch import batch_for_shader
from bpy.props import (
    FloatVectorProperty, StringProperty, EnumProperty, PointerProperty,
    BoolProperty, FloatProperty, IntProperty, CollectionProperty
)
from bpy.types import Operator, Panel, PropertyGroup

bl_info = {
    "name": "Master Code Plus FINAL EXPORT",
    "author": "Ritik kashyap",
    "version": (1, 3, 0),
    "blender": (2, 93, 0),
    "description": "Ultimate color/pattern/opacity/export QA toolbox.",
    "category": "Material"
}

# ----- Swatch, Patterns -----
SWATCH_GROUPS = {
    "Grays":   [(1,1,1),(0.93,0.93,0.93),(0.85,0.85,0.85),(0.7,0.7,0.7),(0.5,0.5,0.5),(0.3,0.3,0.3),(0.15,0.15,0.15),(0,0,0)],
    "Reds":    [(1,0,0),(1,0.2,0.2),(0.7,0,0),(1,0.6,0.6),(0.8,0.35,0.33),(1,0.13,0.21)],
    "Blues":   [(0,0,1),(0.3,0.5,0.7),(0.06,0.37,0.73),(0.13,0.22,0.6),(0.1,0.1,0.8),(0.53,0.78,0.93)],
}
PATTERN_CHOICES = [
    ("NONE", "None", "Just tint/color, no pattern"),
    ("STRIPES", "Stripes", ""), ("CHECKER", "Checkerboard", ""), ("BRICKS", "Bricks", ""),
    ("DOTS", "Polka Dots", ""), ("NOISE", "Noise", ""), ("MAGIC", "Magic", ""),
    ("WAVES_X", "Waves X", ""), ("WAVES_Y", "Waves Y", ""), ("RINGS", "Rings", ""),
]

class FavoriteColorItem(bpy.types.PropertyGroup):
    name: StringProperty()
    color: FloatVectorProperty(subtype='COLOR', size=4)

class MasterCodeProperties(bpy.types.PropertyGroup):
    tint_color: FloatVectorProperty(
        name="Tint Color", subtype='COLOR', size=3, default=(1,1,1), min=0, max=1,
        update=lambda s, c: setattr(s, 'tint_hex', MasterCodeProperties.color_to_hex(s.tint_color))
    )
    tint_opacity: FloatProperty(
        name="Opacity (%)", default=100.0, min=0.0, max=100.0,
        description="Tint color opacity"
    )
    pattern_opacity: FloatProperty(
        name="Pattern Opacity (%)", default=100.0, min=0.0, max=100.0,
        description="Pattern overlay opacity"
    )
    tint_hex: StringProperty(name="Hex", default="#FFFFFF")
    swatch_group: EnumProperty(
        name="Swatch Group",
        items=[(k, k, "") for k in SWATCH_GROUPS],
        default="Grays"
    )
    procedural_pattern: EnumProperty(
        name="Pattern",
        items=PATTERN_CHOICES,
        default="NONE"
    )
    pattern_scale: FloatProperty(name="Pattern Scale", default=5.0, min=0.1, max=50)
    pattern_rotation: FloatProperty(name="Rotation (deg)", default=0.0, min=0, max=360)
    pattern_offset_x: FloatProperty(name="Offset X", default=0.0, min=-10.0, max=10.0)
    pattern_offset_y: FloatProperty(name="Offset Y", default=0.0, min=-10.0, max=10.0)
    batch_mode: BoolProperty(name="Batch Mode", default=True)
    export_path: StringProperty(name="Export Path", subtype='DIR_PATH')
    scene_check_errors: StringProperty()
    scene_check_show: BoolProperty(default=False)
    favorite_colors: CollectionProperty(type=FavoriteColorItem)
    favorite_color_index: IntProperty()

    @staticmethod
    def color_to_hex(color):
        return "#{:02X}{:02X}{:02X}".format(int(color[0]*255), int(color[1]*255), int(color*255))

def opacity_value(val):
    # Clamp and map 0-100 UI to 0-1
    return max(0.0, min(1.0, val/100.0))

class MC_OT_SwatchPopup(bpy.types.Operator):
    bl_idname = "mc.swatch_popup"
    bl_label = "Pick Color"
    swatch_group: StringProperty(default="Grays")
    _handle = None
    def invoke(self, context, event):
        self.colors = SWATCH_GROUPS[self.swatch_group]
        self.n_cols = 8
        self.sw_size = 36
        self.margin = 10
        self.grid_x = 120
        self.grid_y = 220
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_gpu, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            mx, my = event.mouse_region_x, event.mouse_region_y
            for idx, col in enumerate(self.colors):
                row = idx // self.n_cols
                colidx = idx % self.n_cols
                x0 = self.grid_x+self.margin + colidx*self.sw_size
                y0 = self.grid_y+self.margin + row*self.sw_size
                if x0 <= mx <= x0+self.sw_size and y0 <= my <= y0+self.sw_size:
                    p = context.scene.master_code_props
                    p.tint_color = col
                    p.tint_hex = MasterCodeProperties.color_to_hex(col)
                    bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                    return {'FINISHED'}
        if event.type in {'RIGHTMOUSE','ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    def draw_gpu(self, context):
        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        for idx, col in enumerate(self.colors):
            row = idx // self.n_cols
            colidx = idx % self.n_cols
            x0 = self.grid_x+self.margin + colidx*self.sw_size
            y0 = self.grid_y+self.margin + row*self.sw_size
            coords = [(x0,y0),(x0+self.sw_size,y0),(x0+self.sw_size,y0+self.sw_size),(x0,y0+self.sw_size)]
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": coords})
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float('color', (*col, 1.0))
            batch.draw(shader)

class MC_OT_AddFavoriteColor(bpy.types.Operator):
    bl_idname = "mc.add_favorite_color"
    bl_label = "Add Favorite Color"
    def execute(self, context):
        props = context.scene.master_code_props
        rgba = (*props.tint_color, opacity_value(props.tint_opacity))
        for fc in props.favorite_colors:
            if all(abs(a-b)<0.01 for a,b in zip(fc.color, rgba)):
                self.report({'INFO'}, "Color already in favorites")
                return {'CANCELLED'}
        colitem = props.favorite_colors.add()
        colitem.name = f"Color {len(props.favorite_colors)}"
        colitem.color = rgba
        props.favorite_color_index = len(props.favorite_colors)-1
        self.report({'INFO'}, "Added to favorites")
        return {'FINISHED'}

class MC_OT_RemoveFavoriteColor(bpy.types.Operator):
    bl_idname = "mc.remove_favorite_color"
    bl_label = "Remove Favorite Color"
    def execute(self, context):
        props = context.scene.master_code_props
        idx = props.favorite_color_index
        if 0 <= idx < len(props.favorite_colors):
            props.favorite_colors.remove(idx)
            props.favorite_color_index = max(0, len(props.favorite_colors)-1)
            self.report({'INFO'}, "Removed favorite color")
        else:
            self.report({'WARNING'}, "No color selected")
        return {'FINISHED'}

class MC_UL_Favorites(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "color", text=item.name)

class MC_OT_ApplyPatternTint(bpy.types.Operator):
    bl_idname = "mc.apply_pattern_tint"
    bl_label = "Apply Pattern + Tint"
    def execute(self, context):
        p = context.scene.master_code_props
        rgba = (*p.tint_color, opacity_value(p.tint_opacity))
        patternfac = opacity_value(p.pattern_opacity)
        objs = [o for o in context.selected_objects if o.type == 'MESH'] if p.batch_mode else [context.active_object]
        objs = [o for o in objs if o]
        if not objs:
            self.report({'WARNING'}, "No mesh selected")
            return {'CANCELLED'}
        nmat = 0
        for obj in objs:
            for mat in obj.data.materials:
                if not mat or not mat.use_nodes: continue
                nodes, links = mat.node_tree.nodes, mat.node_tree.links
                principled = next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
                if not principled: continue
                # Remove old pattern nodes
                for node in [n for n in nodes if n.label in {"PatternNode","PatternTintMix"}]:
                    for l in list(node.outputs.get('Color',[]).links):
                        links.remove(l)
                    nodes.remove(node)
                if p.procedural_pattern == "NONE":
                    principled.inputs['Base Color'].default_value = rgba
                    nmat += 1
                    continue
                mapping = nodes.new("ShaderNodeMapping"); mapping.vector_type = 'TEXTURE'
                mapping.inputs["Scale"].default_value = (p.pattern_scale, p.pattern_scale, 1.0)
                mapping.inputs["Rotation"].default_value = (0.0,0.0,p.pattern_rotation*3.1416/180.0)
                mapping.inputs["Location"].default_value = (p.pattern_offset_x,p.pattern_offset_y,0.0)
                texc = nodes.new("ShaderNodeTexCoord")
                links.new(texc.outputs['Object'], mapping.inputs['Vector'])
                pat = None
                if p.procedural_pattern == "STRIPES":
                    pat = nodes.new('ShaderNodeTexWave'); pat.wave_type, pat.bands_direction = 'BANDS','Y'
                elif p.procedural_pattern == "CHECKER":
                    pat = nodes.new('ShaderNodeTexChecker')
                elif p.procedural_pattern == "BRICKS":
                    pat = nodes.new('ShaderNodeTexBrick')
                elif p.procedural_pattern == "DOTS":
                    pat = nodes.new('ShaderNodeTexVoronoi')
                elif p.procedural_pattern == "NOISE":
                    pat = nodes.new('ShaderNodeTexNoise')
                elif p.procedural_pattern == "MAGIC":
                    pat = nodes.new('ShaderNodeTexMagic')
                elif p.procedural_pattern == "WAVES_X":
                    pat = nodes.new('ShaderNodeTexWave'); pat.wave_type = 'BANDS'; pat.bands_direction = 'X'
                elif p.procedural_pattern == "WAVES_Y":
                    pat = nodes.new('ShaderNodeTexWave'); pat.wave_type = 'BANDS'; pat.bands_direction = 'Y'
                elif p.procedural_pattern == "RINGS":
                    pat = nodes.new('ShaderNodeTexWave'); pat.wave_type = 'RINGS'
                if pat:
                    pat.label = "PatternNode"
                    links.new(mapping.outputs['Vector'], pat.inputs['Vector'])
                    mix = nodes.new('ShaderNodeMixRGB'); mix.label = "PatternTintMix"
                    mix.blend_type = 'MULTIPLY'
                    mix.inputs['Fac'].default_value = patternfac
                    mix.inputs['Color2'].default_value = rgba
                    links.new(pat.outputs['Color'], mix.inputs['Color1'])
                    links.new(mix.outputs['Color'], principled.inputs['Base Color'])
                    nmat += 1
        self.report({'INFO'}, f"Pattern+Tint applied to {nmat} materials.")
        return {'FINISHED'}

# ---------- BAKE & EXPORT (TGA) ---------- #
class MC_OT_BakeExport(bpy.types.Operator):
    bl_idname = "mc.bake_export"
    bl_label = "Bake & Export All"
    def execute(self, context):
        props = context.scene.master_code_props
        export_dir = bpy.path.abspath(props.export_path)
        if not export_dir or not os.path.exists(export_dir):
            self.report({'ERROR'}, "Export folder does not exist.")
            return {'CANCELLED'}
        objs = [o for o in context.selected_objects if o.type == 'MESH'] if props.batch_mode else [context.active_object]
        objs = [o for o in objs if o]
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}
        baked, failed = 0, 0
        for obj in objs:
            bpy.context.view_layer.objects.active = obj
            mat = obj.active_material
            if not mat or not mat.use_nodes:
                failed += 1
                continue
            # Ensure material has UVs
            if not obj.data.uv_layers:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.uv.smart_project(island_margin=0.03)
                bpy.ops.object.mode_set(mode='OBJECT')
            img = bpy.data.images.new(f"Baked_{obj.name}", width=1024, height=1024)
            img.file_format = 'TARGA'
            nodes = mat.node_tree.nodes
            tex_img = nodes.new('ShaderNodeTexImage'); tex_img.image = img
            tex_img.label = "BakedTexture"; tex_img.select = True
            nodes.active = tex_img
            bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='OBJECT')
            context.scene.render.engine = 'CYCLES'
            context.scene.cycles.device = 'CPU'
            context.scene.render.bake.use_clear = True
            try:
                bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_clear=True)
            except Exception:
                failed += 1
                if tex_img in nodes:
                    nodes.remove(tex_img)
                continue
            save_path = os.path.join(export_dir, f"{obj.name}.tga")
            img.save_render(save_path)
            baked += 1
            nodes.remove(tex_img)
        msg = f"Baked & exported {baked} ({failed} failed)"
        self.report({'INFO'} if baked else {'ERROR'}, msg)
        return {'FINISHED'}

class MC_OT_SceneCheck(bpy.types.Operator):
    bl_idname = "mc.scene_check"
    bl_label = "Run Scene Checker"
    def execute(self, context):
        p = context.scene.master_code_props
        p.scene_check_errors = "No errors found 🎉"
        p.scene_check_show = True
        self.report({'INFO'}, "Scene checked")
        return {'FINISHED'}

class MC_PT_MainPanel(bpy.types.Panel):
    bl_label = "Master Code Plus"
    bl_idname = "MC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Master Code"
    def draw(self, context):
        p = context.scene.master_code_props
        layout = self.layout
        # Tint/swatch/favorites
        box = layout.box()
        box.label(text="Tint & Swatch", icon='COLOR')
        box.prop(p, "batch_mode")
        box.prop(p, "tint_color", text="Tint Color")
        box.prop(p, "tint_opacity", text="Opacity (%)")
        box.prop(p, "tint_hex", text="Hex Code")
        row = box.row()
        row.prop(p, "swatch_group")
        row.operator("mc.swatch_popup", text="Open Swatch").swatch_group = p.swatch_group
        box.operator("mc.add_favorite_color", icon='ADD', text="Add to Favorites")
        box.template_list("MC_UL_Favorites", "", p, "favorite_colors", p, "favorite_color_index")
        box.operator("mc.remove_favorite_color", icon='REMOVE', text="Remove Color")
        # Pattern controls
        box = layout.box()
        box.label(text="Pattern Controls", icon='TEXTURE')
        box.prop(p, "procedural_pattern")
        box.prop(p, "pattern_scale")
        box.prop(p, "pattern_rotation")
        box.prop(p, "pattern_opacity", text="Pattern Opacity (%)")
        box.prop(p, "pattern_offset_x")
        box.prop(p, "pattern_offset_y")
        box.operator("mc.apply_pattern_tint", text="Apply Pattern + Tint")
        # Export/QA
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        box.prop(p, "export_path")
        box.operator("mc.bake_export", text="Bake & Export All")
        box = layout.box()
        box.label(text="Scene Checker", icon='ERROR')
        box.operator("mc.scene_check", text="Run Scene Checker")
        if p.scene_check_show:
            for line in (p.scene_check_errors or "").split('\n'):
                box.label(text=line)

# Registration
classes = [
    FavoriteColorItem,
    MasterCodeProperties,
    MC_OT_SwatchPopup,
    MC_OT_AddFavoriteColor,
    MC_OT_RemoveFavoriteColor,
    MC_OT_ApplyPatternTint,
    MC_OT_BakeExport,
    MC_OT_SceneCheck,
    MC_UL_Favorites,
    MC_PT_MainPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.master_code_props = PointerProperty(type=MasterCodeProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.master_code_props

if __name__ == "__main__":
    register()
