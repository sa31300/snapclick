# Next steps

## Current priority: define fixed-rectangle capture

The owner confirmed Record steps 1, 2, 2b and 3 on their PC, then approved the recording README and demo GIF in this chat.

- The next task is to decide and specify the fixed-rectangle mode below. Planning is authorized; implementation still waits for the owner's decisions and an approved spec.
- MP4 is phase 2 and still needs the owner's explicit go-ahead. No push, tag or release without a request.

## Draft: capture a fixed rectangle by pressing a key

Requested on 2026-11-04. The owner has now asked to define this mode. The following is a planning draft, not an addition to the approved specification yet.

1. Press a key (to be decided) and choose a rectangle with two corners.
2. The rectangle becomes the first image. Its full dashed perimeter stays over the live screen.
3. Scroll up or down normally.
4. Press the key again to capture whatever is now inside that same rectangle and append it below the previous image.
5. Repeat. Esc finishes the joined image. Images are appended in capture order, including after scrolling upward.

There are no continuous screen reads in this proposed flow. Content is captured only on a keypress. For example, capturing lines 1–20 and then 61–80 cannot recover lines 21–60, even with overlap removal.

### Key choice: awaiting the owner

PrtSc currently captures a screenshot and Insert starts recording. Proposed choices:

- Shift+PrtSc starts the new mode; plain PrtSc adds each piece while it is active.
- Shift+PrtSc starts the mode and adds each piece.

### Overlap choice: awaiting the owner

- Try removing overlap: lines 1–20 followed by 11–30 should become lines 1–30 once each.
- Keep full images: those captures become lines 1–20 followed by 11–30, with the overlap repeated.

If overlap removal is chosen, start with a small test on fake content and measure its cost before adding it to the app.

### Remaining decisions before implementation

- With overlap removal, what should scrolling upward do? Example: capture 21–40, then 11–30. Keep capture order, or put the new lines above the earlier content to preserve reading order?
- What should happen if there is no overlap or several plausible matches? Do not silently remove uncertain content.
- How should matching handle static bars, blank areas and look-alike text rows?
- Confirm which existing clipboard, preview, saving and Retake rules should apply to this mode.

### Overlap removal and power use

Comparing images takes more CPU than simply appending them. A possible approach is to compare only when the key is pressed, with no continuous matching between captures. This could keep the work to short bursts; actual CPU use, battery impact and delay need a prototype and measurement.

Reliability is the main question: an incorrect match could remove legitimate lines. The matching rules and behavior when no reliable overlap is found must be decided before building this mode. No choice has been made yet.
