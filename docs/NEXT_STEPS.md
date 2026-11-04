# Next steps

## Current priority: Repeat area step 2

The owner confirmed Record steps 1, 2, 2b and 3 on their PC, then approved the recording README and demo GIF in this chat.

- The owner approved this specification. It is now in [SPEC.md §2e](SPEC.md#2e-repeat-area--full-captures-of-one-fixed-rectangle).
- The owner confirmed step 1 on their PC: preview icon, fixed border and Esc/Finish.
- Build only step 2: PrtSc appends full images, with a joined clipboard image and count preview. Save, Draw and Retake integration stay in step 3. Stop for the owner's PC test and OK.
- MP4 is phase 2 and still needs the owner's explicit go-ahead. No push, tag or release without a request.

## Approved: capture a fixed rectangle by pressing a key

Requested and approved on 2026-11-04. SPEC.md §2e is the source of truth; the notes below retain the agreed planning decisions.

### Owner's chosen flow

1. Press **PrtSc** and choose a rectangle with two corners, as for a normal screenshot. This is image 1.
2. Click the new **Repeat area** icon on the preview: two overlapping rectangles.
3. Show the same rectangle's full dashed perimeter over the live screen. Its screen position and size stay fixed.
4. Scroll up or down normally, then press **PrtSc** to capture the entire rectangle again and append it below the earlier image.
5. Repeat. **Esc** finishes the joined image. Outside this mode, PrtSc takes a normal screenshot and Insert records, as before.

**Keep whole images, including repeated content.** There is no overlap removal or matching. Scrolling upward still appends the new image below, in capture order.

Example: image 1 contains lines 1–20; image 2 contains 11–30. The result contains 1–20 followed by 11–30, including the repeated lines.

Only read the screen when adding an image. For example, capturing lines 1–20 and then 61–80 cannot recover lines 21–60. No continuous screen reads or overlap-matching work are needed for this mode.

### Agreed finishing rules

- Needs **Show preview after capture** on, because the new icon lives on the normal screenshot preview. Place it between Add below and Draw. Hide it for recordings and finished stacks.
- The live screen stays clear and usable: only the fixed dashed amber rectangle is overlaid, with no dim layer. Mouse clicks, wheel, touchpad and ordinary typing go to the underlying app. Right-click keeps its normal app behavior.
- Each added image has the first image's real-pixel width and height. Join full images vertically, without resizing or gaps. Leave Snapclick's border and preview out of the screen read. Handle held PrtSc as a single press, as today.
- Reuse Stack's result handling: the clipboard holds the joined image after each addition; the preview stays open, shows the image count, and offers Finish and Retake while active.
- Finish through Esc or the preview's Finish button. Release the temporary Esc hotkey and start the normal preview timer. Draw and Save work on the final joined image.
- Reuse screenshot saving settings, including PNG/JPG. With screenshot auto-save on, keep one final joined file when the mode finishes, as Stack does. Entering the mode replaces any auto-saved file for image 1 with the final joined result.
- Reuse Stack's Retake rules: while active, remove only the last added image; with only image 1 left, use normal Retake. After finishing, normal Retake undoes the joined capture. Restore the old clipboard only if nothing newer was copied.

These rules do not change existing capture modes or authorize overlap removal.

### Build steps — one at a time

1. **Preview icon, fixed border and Esc**: start from a normal screenshot; the new icon shows the border over the live screen. Scroll and click in the app normally. Esc closes the border and keeps image 1. No repeated captures yet. Stop for the owner's test.
2. **PrtSc adds full images**: append the entire fixed box on each press, update the clipboard and image-count preview, then finish with Esc. Test three captures, including scrolling up and repeated content. Stop for the owner's test.
3. **Save, Draw and Retake**: verify the final joined file and editing; Retake removes the last image while active and preserves newer clipboard copies. Stop for the owner's test.
4. **README and fake-content demo GIF**: ask first. No release without a request.

### Earlier overlap-removal discussion

The owner chose to keep repeated content, so overlap removal is outside this mode. If considered later, compare only on keypress and measure CPU use, battery impact and delay on fake content. Repeated text, static bars and uncertain matches must be resolved before an overlap-removing version is approved.
