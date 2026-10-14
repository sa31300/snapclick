# Snapclick — Specification v1

A tiny Windows tray app: press PrtSc, click two corners, the image is in your clipboard.

## 1. User flow

1. Snapclick runs in the Windows tray (optional: starts with Windows).
2. User presses **PrtSc** (or left-clicks the tray icon).
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
- The captured image is the screen **as it was when PrtSc was pressed** (freeze the screen first, then show the overlay on top of the frozen image).
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
| Before click 1 | Only crosshair + hint `[click] 1st corner   [esc] cancel` |

## 3. Tray

- Icon: **corner brackets** (4 L-shaped corners, square line caps).
  - Dark taskbar: stroke `#FFB000`.
  - Light taskbar: stroke `#7A4E00`.
  - Follow the Windows theme automatically and switch when it changes.
  - Must be crisp at 16 px (provide 16, 20, 24, 32 px sizes in the .ico).
- Left-click: start a capture.
- Right-click menu: **Capture** · **Settings…** · **Open save folder** · **Quit**.
- Tooltip: `Snapclick — PrtSc to capture`.

## 4. Settings window

Opened from the tray menu. Small fixed window (about 380 px wide), dark, style B.

| Setting | Type | Default |
|---|---|---|
| Auto-save each capture | toggle | off |
| Save folder | text + "Browse" button | `%USERPROFILE%\Pictures\Snapclick` |
| File name | read-only preview | `YYYY-MM-DD_HH-MM-SS.png`, e.g. `2026-10-14_18-12-05.png` |
| Format | PNG / JPG switch | PNG |
| Hotkey | shown as chip | `PrtSc` (not editable in v1) |
| Show preview after capture | toggle | off — when on, a small thumbnail appears bottom-right for 3 s |
| Start with Windows | toggle | off |

- Settings save immediately (no "Save" button).
- Stored in `%APPDATA%\Snapclick\settings.json`.
- If two captures land in the same second, add `_2`, `_3`.

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
- If PrtSc is already taken by Windows (Snipping Tool), show a one-time message explaining how to turn it off: *Settings → Accessibility → Keyboard → "Use the Print screen key to open screen capture" → Off*.
- Only one instance can run at a time.
- Package as a single `.exe` with PyInstaller; publish it as a GitHub Release.

## 7. Not in v1

Annotations, blur, scrolling capture, editable hotkey, upload/sharing, OCR. (Ideas for later.)

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
