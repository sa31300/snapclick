# Snapclick — Specification v1

A tiny Windows tray app: press PrtSc, click two corners, the image is in your clipboard.

## 1. User flow

1. Snapclick runs in the Windows tray (optional: starts with Windows).
2. User presses the **hotkey** — **PrtSc** by default, changeable in Settings — (or left-clicks the tray icon).
3. A full-screen overlay appears on **all monitors**. The screen is dimmed.
4. **Click 1** (left button) = first corner of the rectangle.
5. Moving the mouse shows the live rectangle.
6. **Click 2** (left button) = opposite corner.
7. The selected area is copied to the **clipboard** as an image. If auto-save is on, it is also saved to disk.
8. The overlay closes. Done.

Rules:
- Corners can be clicked in any order or direction (top-left → bottom-right, or bottom-right → top-left, etc.). Always normalize.
- **Esc** or **right-click** cancels at any time. Nothing is copied.
- A selection of 0 px width or height cancels.
- The captured image is the screen **as it was when the hotkey was pressed** (freeze the screen first, then show the overlay on top of the frozen image).
- Capture in **real pixels**: correct on high-DPI screens (125%, 150% scaling) and across monitors with different scaling.

## 2. Overlay look (style "B · Utility")

| Element | Spec |
|---|---|
| Dim layer | Black at 62% opacity over everything outside the selection |
| Selection | Shows the frozen screen at full brightness; 1 px **dashed** border, accent color |
| Crosshair | One horizontal + one vertical line across the whole screen, following the cursor; 1 px, accent at 60% opacity |
| Start label | Above corner 1: `x 180  y 150` (mono, 12 px, accent color) |
| Size badge | Below the bottom-right of the selection: `380×240`, mono 12 px semibold, black text on accent background |
| Hint | Top-left of the screen where the mouse is: `[click] 2nd corner   [esc] cancel`; mono 12 px, `#C9C9C4` on `#0D0E10`, 1 px border `#34363B` |
| Magnifier | Square box (~120 px) next to the cursor, showing the pixels under the mouse zoomed 4× (sharp, no smoothing); background `#0D0E10`, 1 px border `#34363B`, thin amber (accent) crosshair in the middle. Sits bottom-right of the cursor; moves to the other side when near the screen edge. |
| Before click 1 | Only crosshair + magnifier + hint `[click] 1st corner   [esc] cancel` |

### Preview thumbnail (when "Show preview after capture" is on)

- Appears bottom-right for 3 s after a capture.
- Stays visible while the mouse is over it; closes 3 s after the mouse leaves.
- Layout: the image, and a one-line **label** below it (mono, muted `#A3A39E`). Default label: `copied to clipboard`, or `saved · <file name>` if auto-save wrote a file.
- Small square buttons in the top-right corner of the image (style B: `#0D0E10` background, 1 px `#34363B` border, `#C9C9C4` icon):

| Button | Icon | Hover | Click |
|---|---|---|---|
| **Save** (only when auto-save is **off**; left of Retake) | arrow into a tray | Button turns baby blue `#8FD3FF` (black icon); label shows the save folder (in baby blue) | Saves the file (same folder, name and format rules as auto-save). Feedback: a quick white flash on the image, the icon turns into a green `#3DDC97` check, one green glow pulse around the button, label shows `saved ✓ <file name>` in green. After that the button stays a green check and does nothing (no duplicate files). |
| **Retake** | back arrow | Button turns amber `#FFB000` (black icon); the image gets a light amber tint; label shows `retake · undo copy` (in amber) | **Undo and retake** (below) |

- **Undo and retake**:
  1. Restores the clipboard to what it was before this capture (only if nothing else was copied since — never overwrite a newer copy).
  2. Deletes the saved file, if one was written (by auto-save or by the Save button).
  3. Reopens the selection overlay on the **same frozen screen**, starting again from corner 1.
- **File name link**: whenever the label shows a saved file name (`saved ✓ <file name>` or `saved · <file name>`), the file name is a link: underlined on hover (hand cursor); click opens File Explorer with that file selected.
- If saving fails, the label shows `save failed` and the tray shows a warning.
- Starting a new capture closes the previous preview.

## 3. Tray

- Icon: **corner brackets** (4 L-shaped corners, square line caps).
  - Dark taskbar: stroke `#FFB000`.
  - Light taskbar: stroke `#7A4E00`.
  - Follow the Windows theme automatically and switch when it changes.
  - Must be crisp at 16 px (provide 16, 20, 24, 32 px sizes in the .ico).
- Left-click: start a capture.
- Right-click menu: **Capture** · **Settings…** · **Open save folder** · **Quit**.
- Tooltip: `Snapclick — <hotkey> to capture` (e.g. `Snapclick — PrtSc to capture`). If the hotkey could not be registered: `Snapclick — hotkey taken, click to capture`.

## 4. Settings window

Opened from the tray menu. Small fixed window (about 380 px wide), dark, style B.

| Setting | Type | Default |
|---|---|---|
| Auto-save each capture | toggle | off |
| Save folder | text + "Browse" button | `%USERPROFILE%\Pictures\Snapclick` |
| File name | read-only preview | `YYYY-MM-DD_HH-MM-SS.png`, e.g. `2026-10-14_18-12-05.png` |
| Format | PNG / JPG switch | PNG |
| Hotkey | chip + small **Reset** button | `PrtSc` — editable (see below) |
| Show preview after capture | toggle | off — when on, a small thumbnail appears bottom-right for 3 s |
| Start with Windows | toggle | off |

- Settings save immediately (no "Save" button).
- Stored in `%APPDATA%\Snapclick\settings.json`.
- If two captures land in the same second, add `_2`, `_3`.

### Editing the hotkey

1. Click the chip → it shows `press keys…` (accent border). The current hotkey is paused while recording.
2. Press the new combo. Modifier keys alone don't end recording; the first non-modifier key does.
3. **Esc** cancels (Esc itself can't be a hotkey). Clicking elsewhere also cancels.
4. **Allowed**: PrtSc or F1–F12 (alone or with any modifiers), or any other key together with **Ctrl, Alt or Win** (Shift may be added). **Refused**: plain keys (letters, numbers, symbols, Space…) and Shift + such a key (it would block typing). A refused combo shows `not allowed — add Ctrl, Alt or Win` under the chip; the old hotkey stays.
5. If Windows can't register the combo (used by another app or by Windows), show `taken by another app` under the chip and keep the old one.
6. On success the chip shows the new combo (e.g. `Ctrl+Shift+S`), it is saved to `settings.json`, and the tray tooltip updates.
7. **Reset** sets it back to `PrtSc` (same check as above).

## 5. Design tokens

| Token | Value |
|---|---|
| Background | `#0D0E10` |
| Panel | `#15161A` |
| Border | `#2E3035` |
| Divider | `#24262A` |
| Text | `#E7E7E4` |
| Text muted | `#A3A39E` |
| Accent | `#FFB000` |
| Mono font | JetBrains Mono (labels, numbers, badges) |
| UI font | IBM Plex Sans (settings text) |
| Corners | Square (0 radius) |

Both fonts are open-source (OFL): bundle them with the app.

## 6. Technical choices

- Python 3.12, Windows 10/11 only.
- **PySide6** (Qt) for overlay, tray and settings window.
- Global hotkey via Win32 `RegisterHotKey` (through `ctypes`). No admin rights needed.
- If the hotkey is PrtSc and Windows uses it for the Snipping Tool, show a one-time message explaining how to turn it off: *Settings → Accessibility → Keyboard → "Use the Print screen key to open screen capture" → Off*.
- Only one instance can run at a time.
- Package as a single `.exe` with PyInstaller; publish it as a GitHub Release.

## 7. Not in v1

Annotations, blur, scrolling capture, upload/sharing, OCR. (Ideas for later.)

## 8. Done when

- [ ] PrtSc → two clicks → paste into Paint/Word works.
- [ ] Works in any click direction.
- [ ] Esc and right-click cancel.
- [ ] Correct on a 150%-scaled screen and on two monitors.
- [ ] Auto-save writes `YYYY-MM-DD_HH-MM-SS.png` to the chosen folder.
- [ ] Settings survive a restart.
- [ ] Tray icon readable on dark and light taskbar.
- [ ] `.exe` runs on a PC without Python.
- [ ] README has a GIF of the flow.
