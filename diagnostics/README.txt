Blender iPad device check v2 (engine-free)

This replaces the earlier ipad-startup-v1 page, which automatically started
Blender. Do not retry that old page on an iPad that became unresponsive.

Unzip this download. Copy ipad-startup.html into the WorldWideWeb folder if you
still have it, replacing the old file. You can also serve this two-file folder
by itself. No Blender engine or original preview download is required.

Keep WorldWideWeb and Safari visible together. Open
http://localhost:8080/ipad-startup.html
Preserve your actual server port/folder path if different. The report should
identify itself as ipad-preflight-v2 and say engineStarted: false.

Browser details appear immediately. Check graphics support only asks for an
adapter; it does not create a GPU device, load the engine, allocate Blender's
memory, or register/install an offline worker. Copy report has selectable text
as a fallback; Download report saves JSON. Do not launch Blender from another
tab while checking. If the device is sluggish, close its existing Blender tab.

This small preflight does not prove that the full port can run on your iPad.
Safari does not expose available RAM. No physical device retry is needed until
you choose to provide this preflight report; the affected engine remains unverified.

SPDX-License-Identifier: GPL-3.0-or-later
The complete source of this diagnostic is the readable ipad-startup.html file.
