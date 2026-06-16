import bpy, importlib, math
from bpy.props import *
from bpy.types import Menu, Panel
from .. utility import icon
from .. properties.denoiser import oidn, optix

class TLM_PT_Panel(bpy.types.Panel):
    bl_label = "The Lightmapper"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties

class TLM_PT_Groups(bpy.types.Panel):
    bl_label = "Lightmap Groups"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    #bl_parent_id = "TLM_PT_Panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties

        if sceneProperties.tlm_lightmap_engine == "Cycles":

            rows = 2
            #if len(atlasList) > 1:
            #    rows = 4

            row = layout.row(align=True)
            row.label(text="Lightmap Group List")
            row = layout.row(align=True)
            row.template_list("TLM_UL_GroupList", "Lightmap Groups", scene, "TLM_GroupList", scene, "TLM_GroupListItem", rows=rows)
            col = row.column(align=True)
            col.operator("tlm_atlaslist.new_item", icon='ADD', text="")
            #col.operator("tlm_atlaslist.delete_item", icon='REMOVE', text="")
            #col.menu("TLM_MT_AtlasListSpecials", icon='DOWNARROW_HLT', text="")

class TLM_PT_Settings(bpy.types.Panel):
    bl_label = "Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties

        row = layout.row(align=True)

        #We list LuxCoreRender as available, by default we assume Cycles exists
        row.prop(sceneProperties, "tlm_lightmap_engine")

        if sceneProperties.tlm_lightmap_engine == "Cycles":

            #CYCLES SETTINGS HERE
            engineProperties = scene.TLM_EngineProperties

            row = layout.row(align=True)
            row.label(text="General Settings")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_apply_on_unwrap")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_alert_on_finish")

            if sceneProperties.tlm_alert_on_finish:
                row = layout.row(align=True)
                row.prop(sceneProperties, "tlm_alert_sound")

            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_verbose")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_only_prepare")
            #row = layout.row(align=True)
            #row.prop(sceneProperties, "tlm_compile_statistics")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_override_bg_color")
            if sceneProperties.tlm_override_bg_color:
                row = layout.row(align=True)
                row.prop(sceneProperties, "tlm_override_color")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_reset_uv")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_apply_modifiers")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_keep_baked_files")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_repartition_on_clean")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_save_preprocess_lightmaps")

            row = layout.row(align=True)
            try:
                if bpy.context.scene["TLM_Buildstat"] is not None:
                    row.label(text="Last build completed in: " + str(bpy.context.scene["TLM_Buildstat"][0]))
            except:
                pass
            
            row = layout.row(align=True)
            row.label(text="Cycles Settings")

            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_mode")
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Baking uses the scene's Cycles", icon='INFO')
            col.label(text="Render settings (not Viewport):")
            col.label(text="- Samples + Adaptive Sampling")
            col.label(text="- Max & per-type Bounces")
            col.label(text="- Clamping / Caustics / Light Paths")
            col.label(text="- Fast GI / Light Tree")
            col.label(text="Edit them in Properties > Render.")
            col.label(text="Device (above) sets the Cycles device.")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_resolution_scale")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_bake_mode")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_target")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_lighting_mode")
            # if scene.TLM_EngineProperties.tlm_lighting_mode == "combinedao" or scene.TLM_EngineProperties.tlm_lighting_mode == "indirectao":
            #     row = layout.row(align=True)
            #     row.prop(engineProperties, "tlm_premultiply_ao")
            if scene.TLM_EngineProperties.tlm_bake_mode == "Background":
                row = layout.row(align=True)
                row.label(text="Warning! Background mode is currently unstable", icon_value=2)
                row = layout.row(align=True)
                row.prop(sceneProperties, "tlm_network_render")
                if sceneProperties.tlm_network_render:
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_network_paths")
                    #row = layout.row(align=True)
                    #row.prop(sceneProperties, "tlm_network_dir")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_caching_mode")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_directional_mode")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_lightmap_savedir")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_dilation_margin")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_exposure_multiplier")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_setting_supersample")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_metallic_clamp")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_texture_interpolation")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_texture_extrapolation")

        
        
        # elif sceneProperties.tlm_lightmap_engine == "LuxCoreRender":

        #     engineProperties = scene.TLM_Engine2Properties
        #     row = layout.row(align=True)
        #     row.prop(engineProperties, "tlm_luxcore_dir")
        #     row = layout.row(align=True)
        #     row.operator("tlm.build_lightmaps")
        #     #LUXCORE SETTINGS HERE
        #     #luxcore_available = False

        #     #Look for Luxcorerender in the renderengine classes
        #     # for engine in bpy.types.RenderEngine.__subclasses__():
        #     #     if engine.bl_idname == "LUXCORE":
        #     #         luxcore_available = True
        #     #         break

        #     # row = layout.row(align=True)
        #     # if not luxcore_available:
        #     #     row.label(text="Please install BlendLuxCore.")
        #     # else:
        #     #     row.label(text="LuxCoreRender not yet available.")

        elif sceneProperties.tlm_lightmap_engine == "OctaneRender":

            engineProperties = scene.TLM_Engine3Properties

            #LUXCORE SETTINGS HERE
            octane_available = True

            

            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_verbose")
            row = layout.row(align=True)
            row.prop(engineProperties, "tlm_lightmap_savedir")
            row = layout.row(align=True)

class TLM_PT_Denoise(bpy.types.Panel):
    bl_label = "Denoise"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw_header(self, context):
        scene = context.scene
        sceneProperties = scene.TLM_SceneProperties
        self.layout.prop(sceneProperties, "tlm_denoise_use", text="")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties
        layout.active = sceneProperties.tlm_denoise_use

        row = layout.row(align=True)

        #row.prop(sceneProperties, "tlm_denoiser", expand=True)
        #row = layout.row(align=True)
        row.prop(sceneProperties, "tlm_denoise_engine", expand=True)
        row = layout.row(align=True)

        if sceneProperties.tlm_denoise_engine == "Integrated":
            row.label(text="Built-in OpenImageDenoise - no setup needed.", icon='INFO')
        elif sceneProperties.tlm_denoise_engine == "OIDN":
            denoiseProperties = scene.TLM_OIDNEngineProperties
            row.label(text="Needs a standalone OIDN binary:", icon='ERROR')
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_oidn_path")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_oidn_verbose")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_oidn_threads")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_oidn_maxmem")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_oidn_affinity")
            # row = layout.row(align=True)
            # row.prop(denoiseProperties, "tlm_denoise_ao")
        elif sceneProperties.tlm_denoise_engine == "Optix":
            denoiseProperties = scene.TLM_OptixEngineProperties
            row.label(text="Needs a standalone OptiX binary:", icon='ERROR')
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_optix_path")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_optix_verbose")
            row = layout.row(align=True)
            row.prop(denoiseProperties, "tlm_optix_maxmem")
            #row = layout.row(align=True)
            #row.prop(denoiseProperties, "tlm_denoise_ao")

class TLM_PT_Filtering(bpy.types.Panel):
    bl_label = "Filtering"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw_header(self, context):
        scene = context.scene
        sceneProperties = scene.TLM_SceneProperties
        self.layout.prop(sceneProperties, "tlm_filtering_use", text="")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties
        layout.active = sceneProperties.tlm_filtering_use
        #row = layout.row(align=True)
        #row.label(text="TODO MAKE CHECK")
        #row = layout.row(align=True)
        #row.prop(sceneProperties, "tlm_filtering_engine", expand=True)
        row = layout.row(align=True)

        if sceneProperties.tlm_filtering_engine == "OpenCV":

            cv2 = importlib.util.find_spec("cv2")

            if cv2 is None:
                row = layout.row(align=True)
                row.label(text="OpenCV is not installed. Install it through preferences.")
            else:
                row = layout.row(align=True)
                row.prop(scene.TLM_SceneProperties, "tlm_filtering_mode")
                row = layout.row(align=True)
                if scene.TLM_SceneProperties.tlm_filtering_mode == "Gaussian":
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_gaussian_strength")
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_iterations")
                elif scene.TLM_SceneProperties.tlm_filtering_mode == "Box":
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_box_strength")
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_iterations")

                elif scene.TLM_SceneProperties.tlm_filtering_mode == "Bilateral":
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_bilateral_diameter")
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_bilateral_color_deviation")
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_bilateral_coordinate_deviation")
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_iterations")
                else:
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_median_kernel", expand=True)
                    row = layout.row(align=True)
                    row.prop(scene.TLM_SceneProperties, "tlm_filtering_iterations")
        else:
            row = layout.row(align=True)
            row.prop(scene.TLM_SceneProperties, "tlm_numpy_filtering_mode")


class TLM_PT_Encoding(bpy.types.Panel):
    bl_label = "Encoding"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw_header(self, context):
        scene = context.scene
        sceneProperties = scene.TLM_SceneProperties
        self.layout.prop(sceneProperties, "tlm_encoding_use", text="")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties
        layout.active = sceneProperties.tlm_encoding_use

        sceneProperties = scene.TLM_SceneProperties
        row = layout.row(align=True)

        if scene.TLM_EngineProperties.tlm_bake_mode == "Background":
            row.label(text="Encoding options disabled in background mode")
            row = layout.row(align=True)

        else:

            row.prop(sceneProperties, "tlm_encoding_device", expand=True)
            row = layout.row(align=True)

            if sceneProperties.tlm_encoding_device == "CPU":
                row.prop(sceneProperties, "tlm_encoding_mode_a", expand=True)
            else:
                row.prop(sceneProperties, "tlm_encoding_mode_b", expand=True)

            if sceneProperties.tlm_encoding_device == "CPU":
                if sceneProperties.tlm_encoding_mode_a == "RGBM":
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_encoding_range")
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_decoder_setup")
                if sceneProperties.tlm_encoding_mode_a == "RGBD":
                    pass
                if sceneProperties.tlm_encoding_mode_a == "HDR":
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_format")

                    if(sceneProperties.tlm_format == "KTX"):
                        row = layout.row(align=True)
                        row.prop(sceneProperties, "tlm_ktx_path")
            else:

                if sceneProperties.tlm_encoding_mode_b == "RGBM":
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_encoding_range")
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_decoder_setup")

                if sceneProperties.tlm_encoding_mode_b == "LogLuv" and sceneProperties.tlm_encoding_device == "GPU":
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_decoder_setup")
                    if sceneProperties.tlm_decoder_setup:
                        row = layout.row(align=True)
                        row.prop(sceneProperties, "tlm_split_premultiplied")
                if sceneProperties.tlm_encoding_mode_b == "HDR":
                    row = layout.row(align=True)
                    row.prop(sceneProperties, "tlm_format")

class TLM_PT_Utility(bpy.types.Panel):
    bl_label = "Utilities"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties

        row = layout.row(align=True)
        row.label(text="Enable Lightmaps for set")
        row = layout.row(align=True)
        row.prop(sceneProperties, "tlm_utility_context")
        row = layout.row(align=True)

        if sceneProperties.tlm_utility_context == "SetBatching":

            row.operator("tlm.enable_set")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_utility_set")
            row = layout.row(align=True)
            #row.label(text="ABCD")
            row.prop(sceneProperties, "tlm_mesh_lightmap_unwrap_mode")

            if sceneProperties.tlm_mesh_lightmap_unwrap_mode == "AtlasGroupA":

                if scene.TLM_AtlasListItem >= 0 and len(scene.TLM_AtlasList) > 0:
                    row = layout.row()
                    item = scene.TLM_AtlasList[scene.TLM_AtlasListItem]
                    row.prop_search(sceneProperties, "tlm_atlas_pointer", scene, "TLM_AtlasList", text='Atlas Group')
                else:
                    row = layout.label(text="Add Atlas Groups from the scene lightmapping settings.")

            else:
                row = layout.row()
                row.prop(sceneProperties, "tlm_mesh_unwrap_margin")
                row = layout.row()
                row.prop(sceneProperties, "tlm_resolution_weight")

                if sceneProperties.tlm_resolution_weight == "Single":
                    row = layout.row()
                    row.prop(sceneProperties, "tlm_mesh_lightmap_resolution")
                else:
                    row = layout.row()
                    row.prop(sceneProperties, "tlm_resolution_min")
                    row = layout.row()
                    row.prop(sceneProperties, "tlm_resolution_max")

            row = layout.row()
            row.operator("tlm.disable_selection")
            row = layout.row(align=True)
            row.operator("tlm.select_lightmapped_objects")
            row = layout.row(align=True)
            row.operator("tlm.remove_uv_selection")
        
        elif sceneProperties.tlm_utility_context == "EnvironmentProbes":

            row.label(text="Environment Probes")
            row = layout.row()
            row.operator("tlm.build_environmentprobe")
            row = layout.row()
            row.operator("tlm.clean_environmentprobe")
            row = layout.row()
            row.prop(sceneProperties, "tlm_environment_probe_engine")
            row = layout.row()
            row.prop(sceneProperties, "tlm_cmft_path")
            row = layout.row()
            row.prop(sceneProperties, "tlm_environment_probe_resolution")
            row = layout.row()
            row.prop(sceneProperties, "tlm_create_spherical")

            if sceneProperties.tlm_create_spherical:

                row = layout.row()
                row.prop(sceneProperties, "tlm_invert_direction")
                row = layout.row()
                row.prop(sceneProperties, "tlm_write_sh")
                row = layout.row()
                row.prop(sceneProperties, "tlm_write_radiance")

        elif sceneProperties.tlm_utility_context == "LoadLightmaps":

            row = layout.row(align=True)
            row.label(text="Load lightmaps")
            row = layout.row()
            row.prop(sceneProperties, "tlm_load_folder")
            row = layout.row()
            row.operator("tlm.load_lightmaps")
            row = layout.row()
            row.prop(sceneProperties, "tlm_load_atlas")

        elif sceneProperties.tlm_utility_context == "LoadLightmaps2":

            row.operator("tlm.load_lightmaps_runtime")
        
        elif sceneProperties.tlm_utility_context == "MaterialAdjustment":
        
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_utility_set")
            row = layout.row(align=True)
            row.operator("tlm.disable_specularity")
            row.operator("tlm.disable_metallic")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_remove_met_spec_link")
            row = layout.row(align=True)
            row.operator("tlm.remove_empty_images")
            row = layout.row(align=True)
            row.operator("tlm.convert_unlit")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_isolate_lightmap_uv")
            row = layout.row(align=True)
            row.operator("tlm.adjust_exposure")
            row = layout.row(align=True)
            row.prop(sceneProperties, "tlm_adjust_exposure")
            row = layout.row(align=True) 

        elif sceneProperties.tlm_utility_context == "NetworkRender":

            row.label(text="Network Rendering")
            row = layout.row()
            row.operator("tlm.start_server")
            layout.label(text="Atlas Groups")

        elif sceneProperties.tlm_utility_context == "TexelDensity":

            row.label(text="Texel Density Utilies")
            row = layout.row()

        elif sceneProperties.tlm_utility_context == "GLTFUtil":

            row.label(text="GLTF material utilities")
            row = layout.row()
            row.operator("tlm.add_gltf_node")
            row = layout.row()
            row.operator("tlm.shift_multiply_links")
            row = layout.row()
            row.prop(sceneProperties, "tlm_gltf_iterate_all")

            row = layout.row()
            row.label(text="GLB export moved to the viewport sidebar (N) ▸ GLTF Export", icon="INFO")

class TLM_PT_Selection(bpy.types.Panel):
    bl_label = "Selection"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = True
        layout.use_property_decorate = False
        sceneProperties = scene.TLM_SceneProperties

        row = layout.row(align=True)
        row.operator("tlm.enable_selection")
        row = layout.row(align=True)
        row.operator("tlm.disable_selection")
        row = layout.row(align=True)
        row.prop(sceneProperties, "tlm_override_object_settings")

        if sceneProperties.tlm_override_object_settings:

            row = layout.row(align=True)
            row = layout.row()
            row.prop(sceneProperties, "tlm_mesh_lightmap_unwrap_mode")
            row = layout.row()

            if sceneProperties.tlm_mesh_lightmap_unwrap_mode == "AtlasGroupA":

                if scene.TLM_AtlasListItem >= 0 and len(scene.TLM_AtlasList) > 0:
                    row = layout.row()
                    item = scene.TLM_AtlasList[scene.TLM_AtlasListItem]
                    row.prop_search(sceneProperties, "tlm_atlas_pointer", scene, "TLM_AtlasList", text='Atlas Group')
                else:
                    row = layout.label(text="Add Atlas Groups from the scene lightmapping settings.")

            else:
                row = layout.row()

            if sceneProperties.tlm_mesh_lightmap_unwrap_mode != "AtlasGroupA":
                row.prop(sceneProperties, "tlm_mesh_lightmap_resolution")
                row = layout.row()
                row.prop(sceneProperties, "tlm_mesh_unwrap_margin")

        row = layout.row(align=True)
        row.operator("tlm.remove_uv_selection")
        row = layout.row(align=True)
        row.operator("tlm.select_lightmapped_objects")
        # row = layout.row(align=True)
        # for addon in bpy.context.preferences.addons.keys():
        #     if addon.startswith("Texel_Density"):
        #         row.operator("tlm.toggle_texel_density")
        #         row = layout.row(align=True)

class TLM_PT_Additional(bpy.types.Panel):
    bl_label = "Additional"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "TLM_PT_Panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sceneProperties = scene.TLM_SceneProperties
        atlasListItem = scene.TLM_AtlasListItem
        atlasList = scene.TLM_AtlasList
        rows = 2
        if len(atlasList) > 1:
            rows = 4
        row = layout.row()
        row.template_list("TLM_UL_AtlasList", "Atlas List", scene, "TLM_AtlasList", scene, "TLM_AtlasListItem", rows=rows)
        col = row.column(align=True)
        col.operator("tlm_atlaslist.new_item", icon='ADD', text="")
        col.operator("tlm_atlaslist.delete_item", icon='REMOVE', text="")
        col.menu("TLM_MT_AtlasListSpecials", icon='DOWNARROW_HLT', text="")

        row = layout.row(align=True)
        row.operator("tlm.atlas_assign_selected", icon='IMPORT')
        row.operator("tlm.atlas_select_objects", icon='RESTRICT_SELECT_OFF')
        row.operator("tlm.atlas_refresh_stats", icon='FILE_REFRESH', text="")

        row = layout.row(align=True)
        row.operator("tlm.atlas_select_non_atlased", icon='STICKY_UVS_DISABLE')

        if atlasListItem >= 0 and len(atlasList) > 0:
            item = atlasList[atlasListItem]
            layout.prop(item, "tlm_atlas_lighting_mode")
            layout.prop(item, "tlm_atlas_lightmap_unwrap_mode")
            layout.prop(item, "tlm_atlas_lightmap_resolution")
            layout.prop(item, "tlm_atlas_unwrap_margin")
            layout.prop(item, "tlm_atlas_repack")
            if item.tlm_atlas_repack:
                layout.prop(item, "tlm_atlas_pack_margin_auto")
                if item.tlm_atlas_pack_margin_auto:
                    d = scene.TLM_EngineProperties.tlm_dilation_margin
                    res = int(item.tlm_atlas_lightmap_resolution)
                    m = min(float(d) / res, 0.2) if res else 0.0
                    row = layout.row()
                    row.enabled = False
                    row.label(text="Pack margin %.5f  (→ %dpx gap = 2 × %dpx dilation)"
                              % (m, round(2 * m * res), d))
                else:
                    layout.prop(item, "tlm_atlas_pack_margin")
                layout.prop(item, "tlm_atlas_pack_shape")

            area = item.tlm_atlas_total_area
            res = int(item.tlm_atlas_lightmap_resolution)
            td = (res / (area ** 0.5)) if area > 0.0 else 0.0
            box = layout.box()
            box.label(text="Surface area: %.2f m²" % area)
            if td > 0.0:
                box.label(text="Texel density: %d px/m" % td)
            else:
                box.label(text="Texel density: refresh stats to compute")
            layout.prop(item, "tlm_atlas_merge_samemat")

            # layout.prop(item, "tlm_use_uv_packer")
            # layout.prop(item, "tlm_uv_packer_padding")
            # layout.prop(item, "tlm_uv_packer_packing_engine")
