# Snapclick — Specification v1.1

v1.1 adds **Stack** (§2b): long captures made of several pieces, joined into one tall image.

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
| **Add below** (first button, left of Save) | square with a plus under it | Button turns `#E7E7E4` (black icon); label shows `add below · start a stack` (in `#E7E7E4`) | Starts a **Stack** (§2b) |

- **Undo and retake**:
  1. Restores the clipboard to what it was before this capture (only if nothing else was copied since — never overwrite a newer copy).
  2. Deletes the saved file, if one was written (by auto-save or by the Save button).
  3. Reopens the selection overlay on the **same frozen screen**, starting again from corner 1.
- **File name link**: whenever the label shows a saved file name (`saved ✓ <file name>` or `saved · <file name>`), the file name is a link: underlined on hover (hand cursor); click opens File Explorer with that file selected.
- If saving fails, the label shows `save failed` and the tray shows a warning.
- Starting a new capture closes the previous preview.

## 2b. Stack — long captures

For content taller than the screen, like long terminal output. The user takes piece 1, then scrolls and clicks. Snapclick joins all pieces into **one tall image**.

### Flow

1. PrtSc, click two corners → piece 1 (normal capture, §1). Best drawn inside the text area, but it must also work with the scrollbar or title bar inside it.
2. On the preview, click **Add below**. The stack starts.
3. The screen is **not frozen** now. Snapclick shows the stack overlay over the live screen.
4. The user scrolls with the mouse wheel, as far as they want. Snapclick passes the wheel to the window under the cursor.
5. **Left click** = end of the next piece. Everything from the end of the last piece to the click is added below, **including lines that already scrolled out of view**.
6. Repeat 4–5 for more pieces.
7. Finish with **✓** on the preview, **Esc**, or **right-click**. All pieces are kept.

Example: piece 1 shows lines 1–28. The user scrolls 40 lines and clicks at the bottom of the frame. Piece 2 = lines 29–68, even though lines 29–40 are no longer on screen.

### The frame

- Piece 1 sets the **frame**: its columns (left/right edges) and its rows (top/bottom edges) on screen.
- Every piece has the same width as piece 1.
- A click below the frame counts as a click on the frame's bottom edge. A click above the end of the captured part does nothing.

### How Snapclick follows the text

- While stacking, Snapclick reads the frame from the screen at least 15 times per second. Its own windows (overlay, preview) are left out of these reads.
- It keeps a hidden **long image**: everything seen in the frame, top to bottom, with no repeats.
- Each new read is matched against the long image to find how far the text moved. New lines that enter the frame are added to the long image.
- Matching rules (tested in the prototype):
  - Cut each pixel row into **8 column blocks** and hash each block. Match by blocks, not whole rows, so a scrollbar inside the frame does not break the match.
  - Skip one-color (blank) blocks: they match everywhere.
  - Accept a position only if at least 70% of the overlapping non-blank blocks are equal.
  - On the first real movement, rows that stayed in the same place (title bar, padding, borders) are marked **static** and ignored from then on. Static rows at the bottom of piece 1 are cut off, so new lines join cleanly.
- If a read cannot be matched (a big jump: dragging the scrollbar, End, PgDn), the stack is **lost**: clicks do nothing until the user scrolls back and the text is found again.

### Stack overlay look (style B)

| Element | Spec |
|---|---|
| Outside the frame | Black at 62% opacity |
| Frame | 1 px dashed rectangle, accent |
| Already captured | The captured rows that are on screen: black at 62% + thin diagonal accent stripes (~40% opacity). **Sticks to the text** when scrolling down or back up. |
| End line | 1 px solid accent line where the captured part ends. Tag `already captured ↑` at its right end (mono 12 px semibold, black on accent). |
| Next piece | 1 px dashed accent rectangle from the end line to the mouse. Size badge (§2) shows the **full** height of the piece, including the part above the screen: `584×680`. |
| Above-screen tag | When the end line is above the frame: tag `↑ + 340 px above, recorded while scrolling` at the frame's top-left (accent text on `#0D0E10`, 1 px accent border). |
| Hint | `[wheel] scroll   [click] end of piece 3   [esc] done` (same box as §2) |
| Lost | Tag `jumped too far · scroll back to the shade` in `#FF6B6B` (text and border) on `#0D0E10`. Hint: `[wheel] scroll back   [esc] done`. |
| Crosshair, magnifier | As in §2, on the live screen |

### Preview while stacking

- Stays open (no 3 s timer) until the stack is finished. It is never part of a screen read.
- Shows the joined image so far, with a count badge top-left (mono 11 px semibold, black on accent): `3`.
- Label: `stack · 3 · scroll, then click the end` (accent).
- Buttons: **Finish** (check icon; hover `#3DDC97` with black icon; label `finish · stop adding` in green) and **Retake**.
- Retake while stacking removes **only the last piece** (label `retake · remove piece 3`). With only piece 1 left, it works like the normal Retake (§2).
- **Save** and **Add below** are hidden while stacking.
- After finishing: label `copied · 3 pieces · 584×1256` (green), the normal 3 s timer starts, Save shows again and saves the joined image. Add below stays hidden for this capture.

### Clipboard and files

- After every piece, the clipboard holds the full joined image, so pasting works at any time.
- The undo-copy rule (§2) covers the whole stack: Retake back to piece 1 restores the clipboard from before piece 1.
- Auto-save on: save **only the final joined image**, once, when the stack is finished. No files for single pieces.

### Build order (for the AI)

1. **Spike first:** pass the wheel to the window under the overlay and leave Snapclick's windows out of screen reads. Test on Windows Terminal and the classic console. If antivirus blocks it, stop and ask.
2. Long-image matcher as plain functions (no UI) + unit tests with made-up images: scrollbar in the frame, title bar in the frame, bottom padding, fast scroll, scroll back up, big jump.
3. Stack overlay.
4. Preview changes, clipboard, auto-save.
5. README (settings, how to use, GIF) — fake demo content only.

After each step: stop, tell the owner how to test it, and wait for an OK before the next step.
**No release** (no new `.exe` on GitHub Releases, no version tag, no push of release files) until the owner has tested the stack on their own PC and said yes.

## 3. Tray

- Icon: **corner brackets** (4 L-shaped corners, square line caps).
  - Dark taskbar: stroke `#FFB000`.
  - Light taskbar: stroke `#7A4E00`.
  - Follow the Windows theme automatically and switch when it changes.
  - Must be crisp at 16 px (provide 16, 20, 24, 32 px sizes in the .ico).
- Left-click: start a capture.
- Right-click menu: **Capture** · **Settings…** · **Open save folder** · **Quit**.
- Tooltip: `Snapclick — PrtSc to capture`. If PrtSc could not be registered: `Snapclick — hotkey taken, click to capture`.

## 4. Settings window

Opened from the tray menu. Small fixed window (about 380 px wide), dark, style B.

| Setting | Type | Default |
|---|---|---|
| Auto-save each capture | toggle | off — in a stack, only the final joined image is saved |
| Save folder | text + "Browse" button | `%USERPROFILE%\Pictures\Snapclick` |
| File name | read-only preview | `YYYY-MM-DD_HH-MM-SS.png`, e.g. `2026-10-14_18-12-05.png` |
| Format | PNG / JPG switch | PNG |
| Hotkey | shown as chip | `PrtSc` (fixed, not editable) |
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
- If PrtSc is used by Windows for the Snipping Tool, show a one-time message explaining how to turn it off: *Settings → Accessibility → Keyboard → "Use the Print screen key to open screen capture" → Off*. If another app holds PrtSc, a one-time message says so (capture still works from the tray icon).
- The hotkey is fixed to PrtSc on purpose: an editable hotkey was built and then dropped (antivirus software blocked changes to the hotkey code, and it added risk for little gain).
- Only one instance can run at a time.
- Package as a single `.exe` with PyInstaller; publish it as a GitHub Release.
- Stack (§2b):
  - Leave Snapclick's own windows out of screen reads with `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` (Windows 10 2004+). If it is not available, hide the overlay for the moment of each read.
  - Pass the wheel to the window under the cursor (e.g. `PostMessage(WM_MOUSEWHEEL)` to the window found under the overlay, or `SendInput` while the overlay ignores the mouse). Pick what works in the spike. No keyboard or mouse **hooks**.
  - Screen reads use the same real-pixel capture as §1, only the frame rectangle.
  - Antivirus may dislike passing input to other windows. If a build or run is blocked, stop and tell the owner; do not work around it.

## 7. Not in v1

Annotations, blur, automatic scrolling capture (Snapclick scrolling by itself), horizontal stacking, editable hotkey, upload/sharing, OCR. (Ideas for later.)

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
- [ ] Stack: piece 1, scroll 3 screens with the wheel, click → one image with every line exactly once (Windows Terminal and classic console).
- [ ] Stack: the stripes stay on the captured text when scrolling back up.
- [ ] Stack: works when piece 1 includes the scrollbar or the title bar.
- [ ] Stack: a scrollbar jump shows the red tag; scrolling back recovers.
- [ ] Stack: auto-save writes one file per stack, not one per piece.
