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

    tlm_atlas_total_area : FloatProperty(
        name="Total surface area",
        description="Cached world-space surface area (m²) of all objects assigned to this atlas. Use 'Refresh stats' to recompute",
        default=0.0)

    tlm_atlas_lighting_mode : EnumProperty(
        items = [('scene', 'Scene Default', 'Use the scene-wide Lighting Mode for this atlas'),
                 ('combined', 'Combined', 'Direct + indirect diffuse lighting only (no albedo); multiply against base color at runtime'),
                 ('indirect', 'Indirect', 'Indirect diffuse lighting only'),
                 ('ao', 'AO', 'Ambient occlusion only'),
                 ('complete', 'Complete', 'Full surface appearance baked down (albedo, mix shaders, procedurals, emission); use as an unlit texture at runtime')],
                name = "Lighting Mode",
                description="Per-atlas bake lighting mode. Overrides the scene Lighting Mode for objects in this atlas. Use 'Complete' to bake down complex/procedural materials to their final look",
                default='scene')

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

    tlm_atlas_pack_margin_auto : BoolProperty(
        name="Auto pack margin",
        description="Derive the pack margin from the bake Dilation Margin and this atlas's resolution (dilation / resolution; the pack margin is a per-island border, so this leaves a 2 x dilation pixel gap between islands) so their baked dilation can never bleed together. Turn off to set the margin manually.",
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

            area = item.tlm_atlas_total_area
            res = int(item.tlm_atlas_lightmap_resolution)
            td = (res / (area ** 0.5)) if area > 0.0 else 0.0

            split = layout.split(factor=0.4)
            split.prop(item, "name", text="", emboss=False, icon=custom_icon)
            metrics = split.row()
            metrics.label(text="%s px" % item.tlm_atlas_lightmap_resolution)
            metrics.label(text=("%.1f m²" % area) if area > 0.0 else "— m²")
            metrics.label(text=("%d px/m" % td) if td > 0.0 else "— px/m")

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)