v1.1.26
- Fixed Model Rotate Back-Forth Loop for object items.
- From/To angles now apply directly, so -22 to 22 creates -22 -> 22 -> -22 instead of accumulating from the current object rotation.

v1.1.25
- Added an Ease In/Out checkbox for Back-Forth Loop.
- When enabled, Back-Forth Loop keyframes use Bezier interpolation for smoother acceleration and deceleration.
- The setting applies to both Camera Rotate and Model Rotate.

v1.1.24
- Camera Rotate now creates/updates the camera on the -Y side of the target.
- New cameras start from the front view direction instead of the +X side.

v1.1.23
- Moved Camera Rotate start and clear buttons into an Actions box.
- Camera Rotate and Model Rotate now use matching Actions layout.

v1.1.22
- Moved Rotation Style and Back-Forth range settings into the top Preset/Timing area.
- Rotation Style now applies to both Camera Rotate and Model Rotate.
- Camera Rotate now supports Back-Forth Loop using the same From/To angle settings.
- Camera Rotate and Model Rotate buttons now reflect the selected rotation style.

v1.1.21
- Added Back-Forth Loop for Model Rotate animations.
- Back-Forth Loop defaults to swinging from -22 degrees to 22 degrees.
- Added Rotation Style in the Actions panel: Full 360 Turntable or Back-Forth Loop.
- Back-Forth Loop works with both object items and collection items.
- The rotate button now changes label based on the selected rotation style.

v1.1.20
- Added Grid Layout to Model Rotate mode using the existing model list.
- Apply Grid Layout moves original objects and collections directly; it does not create linked duplicates.
- Added Grid Type options: Type 1 - Rightward Rows and Type 2 - Legacy Direction.
- Added Axis options: Ground Grid and Vertical Stack.
- Fixed Horizontal layout so item #2 moves to the right on the +X axis.
- Fixed Vertical Stack + Type 2 so new rows continue on +X instead of moving backward on Y.
- Added collapsible Create Label options inside Grid Layout.
- Labels can now include number, name, custom font size, gap, and top/bottom placement.
- Added list numbering so Model Rotate items show their sequence clearly.
- Preset changes now update FPS and Frames immediately; the Apply button was removed.
- Removed preset description text from the panel for a cleaner UI.
- Moved the grid Result preview directly under the Grid Layout title.
- Placed Axis and Type controls on the same row.

v1.1.11
- Improved spacing between Tilt settings and the Create / Update Camera button.

v1.1.9
- Added collapsible Camera settings for Distance, Height, Tilt, and Create Camera.

v1.1.7
- Added word wrapping in the update popup so long changelog lines stay readable.

v1.1.4
- Added GitHub changelog loading in the update popup.

v1.1.3
- Fixed Blender crash risk during update by removing automatic script reload.

v1.1.2
- Removed Reload Scripts from the main UI for a cleaner panel.

v1.1.1
- Added GitHub update checking and addon file download.
- Fixed Collection rotation pivot parenting issues.
- Fixed multi-collection rotation grouping bugs.
- Added support for adding selected Outliner collections to the Model Rotate list.
- Renamed Camera Orbit mode to Camera Rotate for clarity.
