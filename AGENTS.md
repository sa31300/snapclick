# Snapclick — rules for the AI

## Who I am
- I build tools by **directing AI**. This repo is part of my public GitHub portfolio.
- Explain things to me in **very simple English, very short**. One concrete example beats a long explanation.

## What to build
- Read `docs/SPEC.md`. It is the source of truth.
- Do **not** add features that are not in the spec. Ask first.
- If the spec is unclear or wrong, stop and ask me.

## How to work
- Windows only. Python 3.12. Use a virtual environment in `.venv`.
- Keep the code simple and readable. Few files, clear names, short comments.
- Do not change my VS Code settings.
- Never write personal info into the repo: no real names, emails, user names, local paths like `C:\Users\...`, employer or job. Demo GIFs and screenshots use fake demo content only.
- Commit small steps with clear messages (e.g. `Add tray icon`).
- After each step, tell me in 1–2 lines what changed and how to test it.

## Hard rules (a past session broke these)
- **One step, then stop.** Do one step of the spec's "Next steps", then wait for my OK. Never do two steps in one go, even if they look easy.
- **Done = I tested it on my PC and said yes.** Passing unit tests or your own scripts is not "done".
- **No git history rewrites** (`reset`, `rebase`, `commit --amend`, force push) unless I ask.
- **No push, tag or release** unless I ask.
- **Test runs use throwaway settings only**: set `SNAPCLICK_SETTINGS` to a file in a temp folder (spec §6), and a temp save folder. Never touch my real `%APPDATA%\Snapclick\settings.json` or the Windows startup entry.
- **Antivirus (Bitdefender flags this app):** if a file write, build or run is blocked, stop and tell me. Do not work around it.
- **Spec vs code:** if they disagree, tell me which and where. Do not change the spec on your own.
- The Stack target is `docs/design/stack-flow.gif` + spec §2b. Check your work against both.

## The README must have
1. One-line pitch + a GIF of the capture flow.
2. Download (link to the latest GitHub Release `.exe`).
3. How to use (3 steps).
4. Settings list.
5. **How I built this** — short section: built by directing Claude Code from a written spec (`docs/SPEC.md`); key decisions and why.
6. License: MIT.
