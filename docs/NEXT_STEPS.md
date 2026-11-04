# Next steps

## Current priority: review the PNG recording documentation

The owner confirmed Record steps 1, 2, 2b and 3 on their PC in this chat.

- The owner approved the recording README/GIF step. Review the new instructions and `docs/record.gif` (fake content only), then stop for the owner's OK.
- MP4 is phase 2 and still needs the owner's explicit go-ahead. No push, tag or release without a request.

## Parked idea: capture a fixed rectangle by pressing a key

Requested on 2026-11-04. Discuss and specify this after the recording flow; it is not approved for implementation yet.

1. Press a key (to be decided) and choose a rectangle with two corners.
2. The rectangle becomes the first image. Its full dashed perimeter stays over the live screen.
3. Scroll up or down normally.
4. Press the key again to capture whatever is now inside that same rectangle and append it below the previous image.
5. Repeat. Esc finishes the joined image. Images are appended in capture order, including after scrolling upward.

### Decisions still open

- Which key or entry point starts this mode? PrtSc and Insert already have approved uses.
- Keep each full image, or remove overlapping content between captures?
- If overlap removal is chosen, how should it handle scrolling upward, static bars, repeated text and uncertain matches?

### Overlap removal and power use

Comparing images takes more CPU than simply appending them. A possible approach is to compare only when the key is pressed, with no continuous matching between captures. This could keep the work to short bursts; actual CPU use, battery impact and delay need a prototype and measurement.

Reliability is the main question: an incorrect match could remove legitimate lines. The matching rules and behavior when no reliable overlap is found must be decided before building this mode. No choice has been made yet.
