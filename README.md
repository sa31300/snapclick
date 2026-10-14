# Snapclick

**Press PrtSc, click two corners — the picture is in your clipboard.** A tiny Windows tray app.

![Snapclick capture flow: PrtSc, click two corners, done](docs/demo.gif)

## Download

**[Download Snapclick.exe](https://github.com/sa31300/snapclick/releases/latest/download/Snapclick.exe)** (Windows 10/11, no install, no Python needed)

The `.exe` is not code-signed, so Windows may show *"Windows protected your PC"* the first time. Click **More info → Run anyway**.

## How to use

1. Run `Snapclick.exe`. The icon appears in the tray (bottom-right, maybe under `^`).
2. Press **PrtSc** (or left-click the tray icon). The screen freezes and dims.
3. Click one corner, then the opposite corner. Paste anywhere with **Ctrl+V**.

**Esc** or **right-click** cancels. A magnifier next to the cursor helps you hit the exact pixel.
With the preview on, the thumbnail has two buttons:
- **Retake** (back arrow): undoes the capture (clipboard and saved file) and lets you select again on the same frozen screen.
- **Save** (arrow into tray, only when auto-save is off): saves this one capture to your save folder.

When a capture is saved, click the **file name** under the thumbnail to open it in File Explorer.

> If PrtSc opens the Windows Snipping Tool instead, turn it off in
> *Settings → Accessibility → Keyboard → "Use the Print screen key to open screen capture"*.
> Other screenshot apps (Greenshot, ShareX, Lightshot) can also hold PrtSc — close them or change their hotkey.

## Settings

Right-click the tray icon → **Settings…**. Changes save instantly to `%APPDATA%\Snapclick\settings.json`.

| Setting | Default |
|---|---|
| Auto-save each capture | Off |
| Save folder | `%USERPROFILE%\Pictures\Snapclick` |
| File name | `YYYY-MM-DD_HH-MM-SS.png` (adds `_2`, `_3` within the same second) |
| Format | PNG (or JPG) |
| Hotkey | PrtSc (fixed) |
| Show preview after capture | Off — a thumbnail appears bottom-right for 3 s (stays while the mouse is on it; Save and Retake buttons) |
| Start with Windows | Off |

## How I built this

I built Snapclick by **directing Claude Code** from a written spec: [`docs/SPEC.md`](docs/SPEC.md). I wrote what the app must do and how it must look; the AI wrote the code in small, tested steps (see the commit history). When I wanted a new feature (the magnifier), it went into the spec first.

Key decisions and why:

- **Python + PySide6 (Qt)** — one toolkit for the tray, the overlay and the settings window; looks the same on every PC.
- **Freeze first, then select** — the screen is captured the moment you press PrtSc, so menus and tooltips don't vanish while you aim.
- **All math in real pixels** — correct on 125%/150% scaled screens and across two monitors with different scaling. Lines are drawn in real pixels too, so they stay sharp.
- **Win32 `RegisterHotKey`** — a global PrtSc hotkey without admin rights or a keyboard hook.
- **Settings save instantly, no Save button** — fewer clicks, nothing to forget.
- **Fonts bundled** (JetBrains Mono, IBM Plex Sans, both OFL) — the design looks the same even if they aren't installed.
- **One `.exe` with PyInstaller** — download and run, nothing to install.

### Build from source

Use Python 3.12 from [python.org](https://www.python.org/) (Anaconda's Python is too old for Qt 6.12).

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m snapclick       # run
.venv\Scripts\python build.py           # make dist\Snapclick.exe
.venv\Scripts\python tools\make_demo_gif.py   # remake docs/demo.gif
```

## License

[MIT](LICENSE). Bundled fonts: SIL Open Font License (see `snapclick/fonts/`).
