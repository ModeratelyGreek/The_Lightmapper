import bpy
from bpy.props import *

class TLM_AtlasListItem(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object, description="The object to bake")
    tlm_atlas_lightmap_resolution : EnumProperty(
        items = [('32', '32', 'TODO'),
                 ('64', '64', 'TODO'),
                 ('128', '128', 'TODO'),
                 ('256', '256', 'TODO'),
                 ('512', '512', 'TODO'),
                 ('1024', '1024', 'TODO'),
                 ('2048', '2048', 'TODO'),
                 ('4096', '4096', 'TODO'),
                 ('8192', '8192', 'TODO')],
                name = "Atlas Lightmap Resolution", 
                description="TODO",
                default='256')

    tlm_atlas_unwrap_margin : FloatProperty(
        name="Unwrap Margin", 
        default=0.1, 
        min=0.0, 
        max=1.0, 
        subtype='FACTOR')

    unwrap_modes = [('Lightmap', 'Lightmap', 'Use Blender Lightmap Pack algorithm'),
                 ('SmartProject', 'Smart Project', 'Use Blender Smart Project algorithm'),
                 ('Copy', 'Copy existing', 'Use the existing UV channel')]

    if "blender_xatlas" in bpy.context.preferences.addons.keys():
        unwrap_modes.append(('Xatlas', 'Xatlas', 'Use Xatlas addon packing algorithm'))

    tlm_atlas_lightmap_unwrap_mode : EnumProperty(
        items = unwrap_modes,
                name = "Unwrap Mode", 
                description="Atlas unwrapping method", 
                default='SmartProject')

    tlm_atlas_merge_samemat : BoolProperty(
        name="Merge materials",
        description="Merge objects with same materials.",
        default=True)

    tlm_atlas_repack : BoolProperty(
        name="Average + pack islands",
        description="After unwrapping, equalize island scale (uniform texel density) and tightly pack the atlas to use as much space as possible.",
        default=True)

    tlm_atlas_pack_margin : FloatProperty(
        name="Pack Margin",
        description="Gap between islands after packing, in UV space. Keep small to maximize space, but large enough (>= bake dilation) to avoid lightmap bleed between islands.",
        default=0.003,
        min=0.0,
        max=0.2,
        precision=4,
        subtype='FACTOR')

    tlm_atlas_pack_shape : EnumProperty(
        items = [('AABB', 'Bounding box (fast)', 'Pack by island bounding box. Fast and scales to many islands.'),
                 ('CONCAVE', 'Exact shape (tight, slow)', 'Pack by exact island shape. Tightest fit but can be very slow on atlases with many islands.')],
        name = "Pack Shape",
        description="Island packing method. Bounding box is fast; exact shape packs tighter but can hang on large atlases.",
        default='AABB')

    tlm_use_uv_packer : BoolProperty(
        name="Use UV Packer",
        description="UV Packer will be utilized after initial UV mapping for optimized packing.", 
        default=False)

    tlm_uv_packer_padding : FloatProperty(
        name="Padding", 
        default=2.0, 
        min=0.0, 
        max=100.0, 
        subtype='FACTOR')

    tlm_uv_packer_packing_engine : EnumProperty(
        items = [('OP0', 'Efficient', 'Best compromise for speed and space usage.'),
                ('OP1', 'High Quality', 'Slowest, but maximum space usage.')],
                name = "Packing Engine", 
                description="Which UV Packer engine to use.", 
                default='OP0')

class TLM_UL_AtlasList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'OBJECT_DATAMODE'

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            amount = 0

            for obj in bpy.context.scene.objects:
                if obj.TLM_ObjectProperties.tlm_mesh_lightmap_use:
                    if obj.TLM_ObjectProperties.tlm_mesh_lightmap_unwrap_mode == "AtlasGroupA":
                        if obj.TLM_ObjectProperties.tlm_atlas_pointer == item.name:
                            amount = amount + 1

            row = layout.row()
            row.prop(item, "name", text="", emboss=False, icon=custom_icon)
            col = row.column()
            col.label(text=item.tlm_atlas_lightmap_resolution)
            col = row.column()
            col.alignment = 'RIGHT'
            col.label(text=str(amount))

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)