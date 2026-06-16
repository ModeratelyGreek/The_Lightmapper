import bpy


class TLM_PT_GLTFExport(bpy.types.Panel):
    """Viewport sidebar (N-panel) home for the OceanForever GLB export.

    Deliberately separate from the Render-properties 'GLTF material utilities'
    so it can grow its own export-time controls (object/collection tagging that
    the three.js runtime will respect, etc.) without cluttering the lightmapper.
    """
    bl_label = "GLTF Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GLTF Export"

    def draw(self, context):
        layout = self.layout
        sp = context.scene.TLM_SceneProperties

        box = layout.box()
        box.label(text="Nondestructive GLB export", icon="EXPORT")
        col = box.column(align=True)
        col.prop(sp, "tlm_export_glb_path")
        col.prop(sp, "tlm_export_embed_occlusion")
        box.operator("tlm.export_glb", icon="EXPORT")
