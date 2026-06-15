import bpy

from .. utility.cycles import export


class TLM_OT_ExportGLB(bpy.types.Operator):
    bl_idname = "tlm.export_glb"
    bl_label = "Export Lightmapped GLB"
    bl_description = ("Nondestructively duplicate the scene, bake lightmaps, and "
                      "export a .glb with HDR lightmap sidecars + a manifest")
    bl_options = {'REGISTER'}

    def execute(self, context):
        return export.export_glb(self, context)
