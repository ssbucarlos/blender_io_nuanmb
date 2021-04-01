# blender_io_nuanmb
A set of blender scripts to import and export smash animations

Early alpha release so that people who want to avoid the Quaternion-Rotation bug in StudioSB output have an option.
Or if u want to make simple camera track edits.

# PreRequisites
1. The model.numdlb importer script (pls only install the .NUMDLB character MODEL importer) https://gitlab.com/Worldblender/io_scene_numdlb

# How to use
##Camera Tracks:
1. Uninstall existing .nuanmb importer if it isn't this one.
2. Install the included modified .nuanmb importer
3. Select the blender camera in the viewport.
4. Import -> .nuanmb -> Find the camera animation
5. Make your modifications 
6. Export -> .nuanmb

##Character Tracks:
0. Uninstall existing .nuanmb importer if it isn't this one.
1. First import the character model using the .numdlb import script (The download page for it has instructions if ur unsure how to use it)
2. Select the model's armature
3. Import -> .nuanmb -> find the character animation
4. Make your modifications
5. Export -> .nuanmb

# Current Use Case
1. Custom Camera Tracks
2. Adding bone scaling to an animation.
3. Avoid Quaternion-rotation StudioSB Export Issue 
4. Exporting mesh visibility

# Current Limitations
1. No compression (Currently working on this for 1.0 release)
2. Material Track Keyframes not properly imported
3. Camera Track FOV can't be properly keyframed
4. Camera Track FOV preview is only approximately correct if u dont change it
5. Importing an animation with existing scaling previews the animation correctly, but does not export that same animation correctly.

# Credits
1. Carlos 
2. Richard Qian aka WorldBlender (For making the original .nuanmb importer and the .numdlb importer)
3. Ploaj (For making the StudioSB export code)

# Included Scripts
1. A modified version of the importer script from WorldBlender. (Recommended)
2. The exporter script
