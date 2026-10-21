# Snapclick — Specification v1.5

v1.1 adds **Stack** (§2b): long captures made of several pieces, joined into one tall image.
v1.2 makes the Stack flow exact (owner's own words + a reference animation), adds test-only settings (§6), and a status / next-steps section (§2b). No new user features.
v1.4 (2026-10-16): while stacking, piece 1's **rows are no limit any more**, only its columns are. Stripes follow captured lines anywhere in the column; a click anywhere in the column ends the piece there; no dashed next-piece box. Owner found this on their PC (photos of the real app).
v1.5 (2026-10-21): adds **Draw** (§2c): mark up a capture (arrows, boxes, highlights, notes, blur, steps) before it goes to the clipboard. Stack: **↓** scrolls one notch (§2b, 4b).

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
| **Add below** (first button, left of Draw) | square with a plus under it | Button turns `#E7E7E4` (black icon); label shows `add below · start a stack` (in `#E7E7E4`) | Starts a **Stack** (§2b) |
| **Draw** (between Add below and Save) | pen | Button turns violet `#B197FC` (black icon); label shows `draw · mark up` (in `#B197FC`) | Opens the draw window (§2c) |

- **Undo and retake**:
  1. Restores the clipboard to what it was before this capture (only if nothing else was copied since — never overwrite a newer copy).
  2. Deletes the saved file, if one was written (by auto-save or by the Save button).
  3. Reopens the selection overlay on the **same frozen screen**, starting again from corner 1.
- **File name link**: whenever the label shows a saved file name (`saved ✓ <file name>` or `saved · <file name>`), the file name is a link: underlined on hover (hand cursor); click opens File Explorer with that file selected.
- If saving fails, the label shows `save failed` and the tray shows a warning.
- Starting a new capture closes the previous preview.

## 2b. Stack — long captures

For content taller than the screen, like long terminal output. The user takes piece 1, then scrolls and clicks. Snapclick joins all pieces into **one tall image**.

**Reference animations** (mockups with a fake terminal, not the real app; approved by the owner on 2026-10-16):
- [`docs/design/stack-flow.gif`](design/stack-flow.gif): the whole flow, guides top to bottom, no horizontal frame lines.
- [`docs/design/stack-no-limits.gif`](design/stack-no-limits.gif): **v1.4**. Piece 1 sits in the middle of the window; the stripes move past its old top and bottom, and a click below the old bottom ends the piece there. The red `old limit (gone)` marks only explain the change: **do not draw them**. The size badge sits next to the mouse; there is no dashed box.

Neither shows **Add above** (6b); the text covers that. Where a GIF and the text seem to disagree, stop and ask.

### The flow in the owner's words (this is the target)

After clicking **Add below**:

1. I see the previous piece as a rectangle with **yellow stripes**.
2. I scroll down or up. The striped part moves with the text and can **leave the screen**, but I still see the **yellow dashed guide lines** that show the edges.
3. I scroll back, and I see the striped part again.
4. I scroll anywhere, then **click**. The new piece goes from the end of the stripes to my click, **including everything in between**, even lines that are no longer on screen.
5. I can repeat 2–4 to add more pieces.

Needs **Show preview after capture** on: the Add below button lives on the preview.

### Flow (exact rules)

1. PrtSc, click two corners → piece 1 (normal capture, §1). Best drawn inside the text area, but it must also work with the scrollbar or title bar inside it.
2. On the preview, click **Add below**. The stack starts.
3. The screen is **not frozen** now. Snapclick shows the stack overlay over the live screen.
4. The user scrolls with the mouse wheel, as far as they want. Snapclick passes the wheel to the window under the cursor.
4b. **Down arrow** *(owner change, 2026-10-21: in browsers like Brave, touchpad scrolling never reaches the overlay)*: each press scrolls **one wheel notch down** in the window under piece 1. Snapclick sends a real wheel (`SendInput`) at the middle of piece 1, with the overlays click-through for that moment; the mouse goes back where it was. Works in every window, alongside the wheel or touchpad where those reach the overlay (e.g. terminals). **Down only, no Up arrow** (scrolling up has a known open issue, below). The key works while another app has the keyboard (a hotkey, like Esc), only during a stack.
5. **Left click** = end of the next piece. Everything from the end of the last piece to the click is added below, **including lines that already scrolled out of view**.
6. Repeat 4–5 for more pieces.
6b. **Add above** *(owner change, 2026-10-15)*: the user can also scroll **above** the striped part; Snapclick records those lines too. A **click above the top of the stripes** adds a piece from the click down to the top of the stripes, at the **top** of the joined image. A click inside the stripes does nothing. If piece 1 starts with static rows (a title bar), they stay at the very top of the joined image.
7. Finish with **✓** on the preview, **Esc**, or **right-click**. All pieces are kept.

Example: piece 1 shows lines 1–28. The user scrolls 40 lines and clicks at the bottom of the frame. Piece 2 = lines 29–68, even though lines 29–40 are no longer on screen.

### The frame

- Piece 1 sets the **column**: its left and right edges on screen. Every piece has the same width as piece 1.
- Piece 1's top and bottom rows are **not a limit** while stacking *(owner change, 2026-10-16)*. They only say where piece 1 is in the long image. Wherever this spec says "the frame" for the stack, read: **the column, from the top to the bottom of the visible text area of the window under it** (call it the *view*).
- A click anywhere in the view ends the piece **exactly at the click** (below the stripes: Add below; above the stripes: Add above, 6b). A click outside the view (above or below the window's text) counts as a click on the view's nearest edge. A click inside the captured part does nothing.
- Example: piece 1 = lines 9–18 in the middle of the window. The user scrolls 9 lines and clicks near the bottom of the window, on line 41. Piece 2 = lines 19–41, even though line 41 was far below piece 1's old bottom.

### How Snapclick follows the text

- While stacking, Snapclick reads the **view** (the whole column, not only piece 1's rows) from the screen at least 15 times per second. Its own windows (overlay, preview) are left out of these reads.
- It keeps a hidden **long image**: everything seen in the view, top to bottom, with no repeats. It grows at the bottom and at the top (lines above piece 1).
- Each new read is matched against the long image to find how far the text moved. New lines that enter the frame are added to the long image.
- Matching rules (tested in the prototype):
  - Cut each pixel row into **8 column blocks** and hash each block. Match by blocks, not whole rows, so a scrollbar inside the frame does not break the match.
  - Skip one-color (blank) blocks: they match everywhere.
  - Accept a position only if at least 70% of the overlapping non-blank blocks are equal.
  - **And** at least 60% of the overlapping text rows are fully equal (ignoring the rightmost block, where a scrollbar may be). This stops look-alike lines (logs that differ only in a number) from matching at the wrong place. *(Added in v1.2 to match the tested code.)*
  - Static edge **columns** (a strip of the window behind) are found on the first real movement and left out of matching.
  - On the first real movement, rows that stayed in the same place (title bar, padding, borders) are marked **static** and ignored from then on. Static rows at the bottom of piece 1 are cut off, so new lines join cleanly.
- If a read cannot be matched (a big jump: dragging the scrollbar, End, PgDn), the stack is **lost**: clicks do nothing until the user scrolls back and the text is found again.

### Stack overlay look (style B)

| Element | Spec |
|---|---|
| Outside the frame | Black at 62% opacity, **except** the frame's columns: from the top to the bottom of the display they stay clear (no shadow) while stacking. A click there, above or below the frame, still counts as a click on the frame's nearest edge. *(Owner change, 2026-10-15.)* |
| Frame (guide lines) | 1 px dashed, accent. It never moves. Only the 2 vertical lines (left and right edges), always from the top to the bottom of the display. No top or bottom dashed line (as in the reference GIF). *(Owner change, 2026-10-15.)* |
| Already captured | Every captured row that is on screen, **anywhere in the view**: black at 62% + thin diagonal accent stripes (~40% opacity). **Sticks to the text** and moves with it line by line when scrolling down or back up. It is cut only by the edges of the view (the window), **never at piece 1's old top or bottom**. *(Owner change, 2026-10-16: the real app cut the stripes at piece 1's old edges, so captured text there looked uncaptured.)* |
| End line | 1 px solid accent line where the captured part ends. Tag `already captured ↑` at its right end (mono 12 px semibold, black on accent). |
| Start line | Mirror of the end line, where the captured part starts, shown when it is below the view's top edge (the user scrolled up). Tag `already captured ↓` at its right end, under the line. |
| Next piece | **No dashed box** *(owner change, 2026-10-16: its bottom edge showed as a stray horizontal dashed line, stuck at piece 1's old bottom)*. The crosshair line marks where the piece will end. Size badge (§2) next to the mouse, below-left of it, shows the **full** height of the piece including the part off screen: `584×680`. |
| Above-screen tag | When the end line is above the view: tag `↑ + 340 px above, recorded while scrolling` at the view's top-left (accent text on `#0D0E10`, 1 px accent border). Mirror: when the start line is below the view, tag `↓ + 340 px below, recorded while scrolling` at the view's bottom-left. |
| Hint | `[wheel] [↓] scroll   [click] end of piece 3   [esc] done` (same box as §2) |
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

### Status (2026-10-21)

Built and released: the stack shipped in **v1.3.0**; v1.4 parts A and B (reads and stripes use the whole view; a click anywhere in the view ends the piece, no next-piece box) and matcher fixes followed. **v1.4.0** added the **↓** key (4b) after the owner found that touchpad scrolling never reaches the overlay in browsers (Brave).
Owner tests on their PC: §8 item "stripes stay when scrolling back up" accepted with the known flaw below (2026-10-16); stack in Brave with ↓ and in a terminal with the touchpad (2026-10-21).

### Still open (known issues, 2026-10-16)

- **Scrolling up fast can shift the stripes.** In some windows (seen in Claude Code), a fast swipe up can put the stripes a few lines off the captured text. A small scroll down and back up puts them back on the right lines.
- **Rare: lost lines after a half-drawn first scroll.** In apps that redraw their whole screen line by line, if the very first scroll of a stack is read while the screen is half drawn, some text lines can be taken for a fixed bar and left out of the image.

### Next steps (for the AI)

All build steps are done. Open: the owner confirms the §8 Stack items that are not ticked yet. Fix only what fails, one fix per step, then ask the owner to retest.

## 2c. Draw — annotations

*(Added in v1.5, 2026-10-21, owner approved.)* Mark up a capture before pasting it: arrows, boxes, highlights, notes, blur, numbered steps.

**Reference animation** (mockup with a fake ledger screen, not the real app; approved by the owner on 2026-10-21): [`docs/design/annotations-flow.gif`](design/annotations-flow.gif). Where the GIF and the text seem to disagree, stop and ask.

Needs **Show preview after capture** on: the Draw button lives on the preview. Not clicking Draw = no change from today.

### Draw button (on the preview)

| Button | Icon | Hover | Click |
|---|---|---|---|
| **Draw** (between Add below and Save) | pen | Button turns violet `#B197FC` (black icon); label shows `draw · mark up` (in `#B197FC`) | Opens the **draw window** (below) |

- Button order on the preview: **Add below · Draw · Save · Retake** (Save only when auto-save is off, as today).
- Shown for a single shot and after a stack is finished. **Hidden while stacking** (like Save and Add below).
- While the draw window is open, the preview stays open (no 3 s timer). After ✓ done or Esc, the normal 3 s timer starts again.

### Draw window

- Opens with the **captured picture** (the frozen image, not the live screen): the single shot, or the whole joined image after a stack.
- Its own window, style B: background `#0D0E10`, mono font, square corners, 1 px `#34363B` borders. Opens on the monitor of the preview, centered, at most about 90% of that monitor.
- **Header** (mono, muted): left `snapclick · draw`; right `shot · 810×282` for a single shot, or `stack · 3 pieces · 810×1050` after a stack (real pixels of the picture).
- **Picture** at 100% (real pixels). If it is bigger than the window, **scroll inside the window** (wheel, touchpad or the scrollbar) — e.g. a tall stack. The toolbar and header stay in place.
- **Toolbar** (one row, under the header), left to right:

| Item | What it does |
|---|---|
| **→ arrow** | Drag from start to end: a straight arrow with a head at the end. |
| **□ box** | Drag a rectangle: outline only. |
| **▬ mark** | Drag a rectangle: see-through **yellow** highlight over the picture (always yellow, ignores the color). |
| **T text** | Click to place a note, type it. Bold sans text in the color, on a white box with a 1 px border in the color. Enter or a click elsewhere ends the note. **Esc while typing cancels only that note** (a second Esc closes the window). |
| **▦ blur** | Drag a rectangle: the area becomes **big square pixels** in the final picture, so its text can't be read back. |
| **1 step** | Each click places a filled circle in the color with a white number: 1, 2, 3… (counts up per picture; undo takes the number back). |
| **3 colors** | Red (default), blue, green. Used by arrow, box, text and step. |
| **↶ undo** | Removes the last drawing. As many times as needed. |
| **✓ done** | Green (`#3DDC97`) text and border. Finishes (below). |

- The chosen tool shows **violet** (`#B197FC` background, black text). Start tool: **box**.
- Drawings are part of the picture in real pixels (same size as the capture, nothing cut or scaled).

### Finish or cancel

- **✓ done** or **Enter** (when not typing a note): the window closes. The **clipboard** gets the picture **with drawings**, the **thumbnail** shows it, the label shows `copied · with drawings` in green (`#3DDC97`).
- After that, **Save** saves the picture with drawings (same name and folder rules as today).
- If a file was already written for this capture (auto-save on, or Save clicked), ✓ done **overwrites that file** with the drawn picture (same file name).
- **Draw again** after ✓ done: the window opens with the drawings **still editable** (undo works), for this capture only.
- **Esc**: the window closes, nothing changes (clipboard, thumbnail and files stay as they were).
- **Retake** after drawing works as today (§2): the clipboard goes back to what it was before the capture, if nothing newer was copied.

### Decisions (owner, 2026-10-21)

1. Auto-save on, or Save already clicked: ✓ done **overwrites** that file with the drawn picture (same file name).
2. Draw again after ✓ done: the drawings are **still editable** (undo works), for this capture only.
3. After a stack, **Add below stays hidden** (§2b). The mockup GIF showing it there is wrong on this point.
4. Label after a stack: `copied · 3 pieces · 584×1256` (§2b). The mockup GIF's `stack · 3 pieces · copied` is wrong on this point.
5. Esc while typing a note cancels **only that note**; a second Esc closes the window.
6. Blur = **big square pixels** (text can't be read back).

### Status (2026-10-21)

Steps 1–7 built and **tested by the owner on their PC**. Step 8 (README + `docs/draw.gif`) done on the owner's go-ahead. **Released in v1.5.0**; the owner tested the release `.exe`.

Known limit: while drawing, dragging past the window's edge does not scroll the window (scroll first, then draw). Not in this spec; in the release notes.

### Build steps (for the AI) — one at a time, stop after each

1. **Draw button + empty draw window:** pen button with hover and label; click opens the window with header, toolbar (not working yet) and the picture; ✓ / Enter / Esc close it. ✓ copies the picture unchanged. *Test: single shot → Draw → Esc: nothing changes.*
2. **Box, arrow, colors, undo; ✓ copies with drawings:** clipboard, thumbnail and label `copied · with drawings`. *Test: draw a red box and a blue arrow, ✓, paste into Paint.*
3. **Mark and step.** *Test: highlight a number, place steps 1–3, undo one, add again → numbers stay in order.*
4. **Text** (Enter or a click elsewhere ends the note; Esc while typing cancels only that note). *Test: write a note, ✓, paste.*
5. **Blur.** *Test: blur a line of text, ✓, paste, zoom in: it can't be read.*
6. **Stack:** draw on a tall joined picture, scroll inside the window. *Test: 3-piece stack, Draw, scroll to the bottom, box a line, ✓, paste: the full tall picture with the box.*
7. **Save and auto-save with drawings** (✓ done overwrites a file already written), **Draw again keeps the drawings editable, Retake after drawing**. *Test: Draw → ✓ → Save → open the file; auto-save on → Draw → ✓ → the same file now has the drawings; Draw again → undo works; Retake → clipboard back.*
8. **README** (How to use + GIF of the draw flow, fake content only). Ask first.

**No release** until the owner has tested Draw on their own PC and said yes.

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
- **Test-only settings (for development, not a user feature):** if the environment variable `SNAPCLICK_SETTINGS` is set, it is the path of the settings file to use instead of `%APPDATA%\Snapclick\settings.json`. In that mode Snapclick must **never** write or delete the Windows startup entry (Run key): "Start with Windows" only changes the test file. Every test run by the AI uses this, with a file in a temp folder and a temp save folder. Not shown in the README's user sections.
- **Debug reads (for development, not a user feature):** *(added 2026-10-20, owner OK; to find why the stack gets lost in browsers)* if the environment variable `SNAPCLICK_DEBUG_DIR` is set, each stack writes a new subfolder there with piece 1, every view read that changed (PNG, at most 400 per stack), and a `log.txt` line per read (found or lost, position, static rows, matched columns) and per wheel event (deltas, posted or sent, target window class), a line per raw input message the overlay gets (wheel, horizontal wheel, pointer, gesture, touch; with the foreground window class), and an `end` line when the stack finishes. Separate switch: if `SNAPCLICK_DEBUG_NO_FOREGROUND=1` is set (with or without the debug folder), the stack does not make the window under piece 1 the active window (no `SetForegroundWindow`); the start line logs it. Each Down-arrow notch (§2b) is logged as `how=key`. Off when the variable is not set. Not shown in the README's user sections.
- Package as a single `.exe` with PyInstaller; publish it as a GitHub Release.
- Stack (§2b):
  - Leave Snapclick's own windows out of screen reads with `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` (Windows 10 2004+). If it is not available, hide the overlay for the moment of each read.
  - Pass the wheel to the window under the cursor (e.g. `PostMessage(WM_MOUSEWHEEL)` to the window found under the overlay, or `SendInput` while the overlay ignores the mouse). Pick what works in the spike. No keyboard or mouse **hooks**.
  - *(2026-10-21, owner plan)* Chromium windows (Brave, Chrome, Edge: window class `Chrome_WidgetWin_*`) ignore a posted `WM_MOUSEWHEEL`. For them, Snapclick sends a real wheel with `SendInput` at the mouse, and for that moment (~150 ms after the last wheel) the overlays let the mouse through (`WS_EX_TRANSPARENT`), so the wheel reaches the browser. Other windows (terminals) keep the posted message. The sent wheels are marked; if one comes back to the overlay, it is dropped.
  - Screen reads use the same real-pixel capture as §1, only the view rectangle (piece 1's columns × the visible text area of the window under it). Find the window with the same window-under-the-overlay lookup used for the wheel; clip to the monitor. Static rows (title bar, tab bar, padding) are still found on the first movement and ignored.
  - Antivirus may dislike passing input to other windows. If a build or run is blocked, stop and tell the owner; do not work around it.

## 7. Not in v1

Automatic scrolling capture (Snapclick scrolling by itself), horizontal stacking, editable hotkey, upload/sharing, OCR. (Ideas for later.)

## 8. Done when

*Ticked = the owner confirmed it on their PC (date in brackets), or it can be checked in the repo. Not ticked = not confirmed in writing yet; ask the owner.*

- [ ] PrtSc → two clicks → paste into Paint/Word works.
- [ ] Works in any click direction.
- [ ] Esc and right-click cancel.
- [ ] Correct on a 150%-scaled screen and on two monitors.
- [ ] Auto-save writes `YYYY-MM-DD_HH-MM-SS.png` to the chosen folder.
- [ ] Settings survive a restart.
- [ ] Tray icon readable on dark and light taskbar.
- [ ] `.exe` runs on a PC without Python.
- [x] README has a GIF of the flow.
- [ ] Stack: piece 1, scroll 3 screens with the wheel, click → one image with every line exactly once (Windows Terminal and classic console).
- [x] Stack: the stripes stay on the captured text when scrolling back up. *(2026-10-16, with the known flaw in §2b)*
- [ ] Stack: piece 1 in the middle of the window, scroll → the stripes move line by line past piece 1's old top and bottom; captured text never looks uncaptured.
- [ ] Stack: click near the bottom of the window, below piece 1's old bottom → the piece ends exactly at the click.
- [ ] Stack: no horizontal dashed line at any time (no frame top/bottom, no next-piece box).
- [ ] Stack: scroll down until the stripes leave the screen → the dashed guide lines stay; scroll back up → the stripes come back on the same lines.
- [ ] Stack: scroll far down, click → the new piece includes the lines that left the screen (no gap, no repeat). Repeat for a 3rd piece.
- [ ] Stack: works when piece 1 includes the scrollbar or the title bar.
- [ ] Stack: a scrollbar jump shows the red tag; scrolling back recovers.
- [ ] Stack: auto-save writes one file per stack, not one per piece.
- [x] Stack: in a browser (Brave), ↓ scrolls the page and the stripes follow; in a terminal the touchpad still works. *(2026-10-21)*
- [x] Draw: single shot → Draw → box, arrow, mark, text, blur, steps → ✓ → paste shows every drawing. *(2026-10-21)*
- [x] Draw: after a 3-piece stack, scroll inside the draw window, draw at the bottom → ✓ → paste shows the full tall picture with it. *(2026-10-21)*
- [x] Draw: Esc → nothing changes. Not clicking Draw → same as today. *(2026-10-21)*
- [x] Draw: Save after ✓ writes the picture with drawings. *(2026-10-21)*
