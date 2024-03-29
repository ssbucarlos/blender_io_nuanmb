# DEPRECATED
* This repo is now deprecated! 
* Please use smash_ultimate_blender for importing/exporting models/animations!
* This repo will be kept around for legacy version support, but the latest features + bug fixes will not be back ported here.
* https://github.com/ssbucarlos/smash-ultimate-blender
# blender_io_nuanmb
A set of blender scripts to import and export smash animations. Contains a modified version of the .nuanmb importer script from https://gitlab.com/Worldblender/io_scene_numdlb , these modifications are to enable importing of camera animations and also to keyframe materials.

# PreRequisites
1. The model.numdlb importer script (pls only install the .NUMDLB character MODEL importer) https://gitlab.com/Worldblender/io_scene_numdlb

# How to use
## Camera Tracks:
1. Uninstall existing .nuanmb importer if it isn't this one.
2. Install the included modified .nuanmb importer
3. Select the blender camera in the viewport.
4. Import -> .nuanmb -> Find the camera animation
5. Make your modifications 
6. Export -> .nuanmb

## Character Tracks:
0. Uninstall existing .nuanmb importer if it isn't this one.
1. Install the included modified .nuanmb importer
2. First import the character model using the .numdlb import script (The download page for it has instructions if ur unsure how to use it)
3. Select the model's armature
4. Import -> .nuanmb -> find the character animation
5. Make your modifications
6. Export -> .nuanmb

# Current Use Case
1. Custom Camera Tracks
3. Avoid quaternion-rotation StudioSB Export Issue 
4. Easier VIS Mesh visibility editing
5. Correctly preview and modify animations with scaling
6. Preview animations with helper bone influence

# Current Limitations
3. Camera Track FOV can't be properly keyframed
4. Camera Track FOV preview is only approximately correct if u dont change it

# Credits
1. Carlos 
2. Richard Qian aka WorldBlender (For making the original .nuanmb importer and the .numdlb importer)
3. Ploaj (For making the StudioSB export code)

# Included Scripts
1. A modified version of the importer script from WorldBlender. (Recommended)
2. The exporter script
