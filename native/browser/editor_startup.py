"""Browser defaults for Blender's own single-window editor."""
import bpy

# Temporary editors stay inside the browser canvas, including file selection,
# preferences and render results. These use Blender's existing editor spaces.
view = bpy.context.preferences.view
view.filebrowser_display_type = 'SCREEN'
view.preferences_display_type = 'SCREEN'
view.render_display_type = 'SCREEN'
