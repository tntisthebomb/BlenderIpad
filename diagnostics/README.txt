Blender iPad startup check

1. Unzip this download in Files.
2. Copy ipad-startup.html into the WorldWideWeb folder already containing
   index.html, blender-core.js, blender-core.wasm and blender-core.data.
3. Close the previous Blender tab. Keep WorldWideWeb running beside Safari.
4. Open http://localhost:8080/ipad-startup.html in Safari. If your editor lives
   in a subfolder, preserve that subfolder before ipad-startup.html.
5. If it stalls or reports an error, tap Copy startup report and paste it into
   the chat. Startup details also show the report for manual selection/copy.

This diagnostic uses the existing engine files and the same project storage.
It records startup phases and the previous attempt if the page reloads. It is
not a new completed port. Its complete frontend source is ipad-startup.html.
The diagnostic is GPL-3.0-or-later; the existing engine's corresponding source
accompanies your original blender-editor-preview-with-source download.
