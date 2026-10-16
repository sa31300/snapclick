"""Tests for the long-image matcher. Run: .venv\\Scripts\\python -m unittest discover tests"""
import random
import unittest

from snapclick.matcher import LongImage, image_rows, row_blocks, rows_image

WIDTH = 160  # 8 blocks of 20 px
CONTENT = 200  # rows of text visible in the frame
LINE = 16  # rows per text line
BG = b"\x1e\x1e\x1e\xff"
INK = b"\xe0\xe0\xe0\xff"
SCROLLBAR = 6  # px at the right edge
TRACK, THUMB = b"\x2a\x2a\x2a\xff", b"\x80\x80\x80\xff"


def make_document(lines=150, seed=1, longest=WIDTH, shortest=8, empty=0.15):
    """Made-up terminal text: lines of random 'glyphs', some lines empty."""
    rng = random.Random(seed)
    rows = []
    for _ in range(lines):
        length = 0 if rng.random() < empty else rng.randint(shortest, longest)
        rows += [BG * WIDTH] * 3
        for _ in range(LINE - 6):
            rows.append(b"".join(INK if x < length and rng.random() < 0.3 else BG for x in range(WIDTH)))
        rows += [BG * WIDTH] * 3
    return rows


def make_title(height=24):
    rng = random.Random(99)
    return [b"".join(bytes((40 + rng.randrange(60), 40, 60, 255)) for _ in range(WIDTH)) for _ in range(height)]


class Terminal:
    """A frame over the document, scrolled to `top`."""

    def __init__(self, document, title=0, padding=0, scrollbar=False, edge=0):
        self.document = document
        self.title = make_title(title) if title else []
        self.padding = padding
        self.scrollbar = scrollbar
        self.edge = edge  # px at the left showing the window behind: never scrolls, sometimes changes
        self.edge_rng = random.Random(5)
        self.behind = self.make_behind()

    def make_behind(self):
        return [bytes(self.edge_rng.randrange(256) for _ in range(4 * self.edge)) for _ in range(500)]

    def view(self, top):
        top = max(0, min(top, len(self.document) - CONTENT))
        rows = self.document[top:top + CONTENT] + [BG * WIDTH] * self.padding
        if self.scrollbar:
            area = len(rows)
            thumb_start = top * area // len(self.document)
            thumb_end = thumb_start + CONTENT * area // len(self.document)
            rows = [row[:-SCROLLBAR * 4] + (THUMB if thumb_start <= y < thumb_end else TRACK) * SCROLLBAR
                    for y, row in enumerate(rows)]
        rows = self.title + rows
        if self.edge:
            if self.edge_rng.random() < 0.1:  # the window behind changes now and then
                self.behind[self.edge_rng.randrange(len(rows))] = bytes(4 * self.edge)
            rows = [self.behind[y] + row[4 * self.edge:] for y, row in enumerate(rows)]
        return rows

    def expected(self, last_top):
        """The perfect long image after scrolling down to `last_top`."""
        return self.title + self.document[:last_top + CONTENT]


def strip(rows, edge=0):
    """Rows without the scrollbar columns (and the left edge strip)."""
    return [row[4 * edge:-SCROLLBAR * 4] for row in rows]


class MatcherTest(unittest.TestCase):
    def run_scroll(self, terminal, tops):
        long = LongImage(terminal.view(tops[0]))
        for top in tops[1:]:
            self.assertTrue(long.add_read(terminal.view(top)), f"lost at top={top}")
        return long

    def assert_joined(self, long, terminal, last_top, slack=0):
        """Every line exactly once, in order. `slack` = rows that may be missing at the very end."""
        expected = strip(terminal.expected(last_top), terminal.edge)
        got = strip(long.rows, terminal.edge)
        self.assertGreaterEqual(len(got), len(expected) - slack)
        self.assertLessEqual(len(got), len(expected))
        self.assertEqual(got, expected[:len(got)])

    def test_blank_block(self):
        row = BG * WIDTH
        self.assertEqual(row_blocks(row), (None,) * 8)
        self.assertIsNotNone(row_blocks(INK + BG * (WIDTH - 1))[0])

    def test_no_movement(self):
        terminal = Terminal(make_document())
        long = self.run_scroll(terminal, [0, 0, 0])
        self.assertEqual(long.rows, terminal.view(0))
        self.assertFalse(long.lost)

    def test_cursor_blink_is_not_a_move(self):
        terminal = Terminal(make_document())
        first = terminal.view(0)
        long = LongImage(first)
        blink = list(first)
        blink[100] = INK * 10 + first[100][40:]
        self.assertTrue(long.add_read(blink))
        self.assertEqual(long.pos, 0)
        self.assertFalse(long.static_known)

    def test_slow_scroll(self):
        terminal = Terminal(make_document())
        tops = list(range(0, 1500, 3))
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_fast_scroll(self):
        terminal = Terminal(make_document())
        tops = list(range(0, 2000, CONTENT // 2))  # half the frame per read
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_wheel_steps(self):
        """3 lines per wheel notch, like Windows default."""
        terminal = Terminal(make_document())
        tops = list(range(0, 1800, 3 * LINE))
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_scrollbar_in_frame(self):
        terminal = Terminal(make_document(), scrollbar=True)
        tops = list(range(0, 1500, 37))
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_title_bar_in_frame(self):
        terminal = Terminal(make_document(), title=30)
        tops = list(range(0, 1500, 41))
        long = self.run_scroll(terminal, tops)
        self.assertGreaterEqual(long.top, 30)  # title rows are static
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_bottom_padding(self):
        terminal = Terminal(make_document(), padding=12)
        tops = list(range(0, 1500, 29))
        long = self.run_scroll(terminal, tops)
        self.assertGreaterEqual(long.bottom, 12)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)  # no padding rows in the middle

    def test_everything_in_frame_first_move_fast(self):
        terminal = Terminal(make_document(), title=30, padding=12, scrollbar=True)
        tops = [0, 150] + list(range(300, 1500, 50))
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_changing_strip_at_the_edge(self):
        """Whole window selected: a strip of the window behind at the left, short lines."""
        terminal = Terminal(make_document(longest=30), title=30, scrollbar=True, edge=7)
        tops = list(range(0, 1500, 23))
        long = self.run_scroll(terminal, tops)
        self.assertGreaterEqual(long.left, 7)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_lines_that_differ_only_in_a_number(self):
        """Like a log: lines repeat every 30 lines, only the number at the left differs.
        A fast flick must give 'lost', never a wrong position."""
        rng = random.Random(3)
        pattern = make_document(lines=30, seed=7, shortest=140, empty=0)
        document = []
        for n in range(300):
            number = [b"".join(INK if rng.random() < 0.4 else BG for _ in range(16)) for _ in range(LINE)]
            document += [num + row[16 * 4:] for num, row in zip(number, pattern[(n % 30) * LINE:(n % 30 + 1) * LINE])]
        terminal = Terminal(document)
        long = LongImage(terminal.view(0))
        top = 0
        for step in [40] * 10 + [190] * 8 + [40] * 20:  # normal, then a flick, then normal
            top += step
            long.add_read(terminal.view(top))
            if not long.lost:
                self.assertEqual(long.rows[long.pos], document[top], f"wrong position at top={top}")

    def test_same_lines_but_the_number_are_not_static(self):
        """Like `line 13  some test text`: every line is the same but the number,
        so after a scroll most blocks of each row are where they were. That must
        not make the text look static (it got lost, or the stripes slid)."""
        rng = random.Random(4)
        text = make_document(lines=1, seed=8, shortest=80, longest=80, empty=0)
        document = []
        for n in range(200):
            number = [b"".join(INK if 3 <= y < LINE - 3 and rng.random() < 0.4 else BG for _ in range(16))
                      for y in range(LINE)]  # ink only where the text has ink, like digits
            document += [row[:4] + num + row[17 * 4:] for num, row in zip(number, text)]
        for title in (0, 30):
            terminal = Terminal(document, title=title)
            long = LongImage(terminal.view(400))
            for top in [448, 496, 544, 448, 352, 304, 400, 448, 544]:  # wheel notches of 3 lines
                self.assertTrue(long.add_read(terminal.view(top)), f"lost at top={top}")
                self.assertEqual(long.top, title)
                self.assertEqual(long.rows[long.pos + title], document[top], f"wrong position at top={top}")

    def test_part_not_redrawn_yet(self):
        """The console moves the old pixels first, then draws the lines that scrolled
        into view: a read in between shows old lines there. They must not be added
        (they were: lines 111-113 twice, no 114-116)."""
        terminal = Terminal(make_document(), title=30)
        late = LINE  # rows not redrawn yet (the real console: 3 lines of 26)
        long = self.run_scroll(terminal, [400, 448])  # the first move finds the title bar
        last_top = 448
        for top in [496, 544, 592, 640, 592, 544, 496, 448, 400, 352, 304, 256, 304, 352]:
            before, now = terminal.view(last_top), terminal.view(top)
            if top > last_top:  # scrolled down: old pixels at the bottom
                torn = now[:-late] + before[-late:]
            else:  # up: old pixels at the top, under the title bar
                torn = now[:30] + before[30:30 + late] + now[30 + late:]
            self.assertTrue(long.add_read(torn), f"lost at top={top} (not redrawn)")
            self.assertTrue(long.add_read(now), f"lost at top={top}")
            last_top = top
        self.assert_above(long, terminal, 400, 256, 640)

    def test_scroll_back_up(self):
        terminal = Terminal(make_document())
        tops = list(range(0, 600, 7)) + list(range(600, 100, -9)) + list(range(100, 1200, 11))
        long = self.run_scroll(terminal, tops)
        self.assert_joined(long, terminal, tops[-1], slack=LINE)

    def test_position_follows_text(self):
        terminal = Terminal(make_document(), title=30)
        long = self.run_scroll(terminal, list(range(0, 900, 20)) + [500])
        # Frame row 30 (first row under the title) shows document row 500.
        self.assertEqual(long.rows[long.pos + 30], terminal.document[500])

    def test_big_jump_is_lost_then_found(self):
        terminal = Terminal(make_document())
        long = self.run_scroll(terminal, list(range(0, 300, 20)))
        size = len(long.rows)
        self.assertFalse(long.add_read(terminal.view(1400)))  # dragged the scrollbar
        self.assertTrue(long.lost)
        self.assertFalse(long.add_read(terminal.view(1450)))
        self.assertEqual(len(long.rows), size)  # nothing added while lost
        self.assertTrue(long.add_read(terminal.view(330)))  # scrolled back to the shade
        self.assertFalse(long.lost)
        for top in range(330, 900, 20):
            self.assertTrue(long.add_read(terminal.view(top)))
        self.assert_joined(long, terminal, 890, slack=LINE)

    def assert_above(self, long, terminal, first, highest, lowest, slack=LINE):
        """Piece 1 was shown at `first`; then the user scrolled up to `highest` and down
        to `lowest`. Long image = piece 1's rows before its first text row (title bar,
        blank rows), then the document from there on, every line once."""
        doc, edge = terminal.document, terminal.edge
        title = len(terminal.title)
        blank = long.header - title  # piece 1's blank rows above its first text row
        self.assertGreaterEqual(blank, 0)
        self.assertEqual(long.above, first - highest)
        got = strip(long.rows, edge)
        self.assertEqual(got[:long.header], strip(terminal.title + doc[first:first + blank], edge))
        expected = strip(doc[highest + blank:lowest + CONTENT], edge)
        rest = got[long.header:]
        self.assertGreaterEqual(len(rest), len(expected) - slack)
        self.assertEqual(rest, expected[:len(rest)])

    def test_scroll_up_above_piece_1(self):
        terminal = Terminal(make_document())
        tops = list(range(800, 300, -9)) + list(range(300, 1200, 11))
        long = self.run_scroll(terminal, tops)
        self.assert_above(long, terminal, 800, 300, tops[-1])

    def test_scroll_up_with_title_bar_and_scrollbar(self):
        """The title bar stays at the top; lines from above go under it."""
        terminal = Terminal(make_document(), title=30, scrollbar=True)
        tops = list(range(900, 100, -3 * LINE)) + list(range(100, 1300, 3 * LINE))
        long = self.run_scroll(terminal, tops)
        self.assertGreaterEqual(long.header, 30)
        self.assert_above(long, terminal, 900, 100, tops[-1])

    def test_scroll_up_with_blank_rows_under_the_title_bar(self):
        """Blank padding under the title bar never scrolls: lines from above go under it."""
        terminal = Terminal(make_document())
        terminal.title = make_title(20) + [BG * WIDTH] * 10
        tops = list(range(900, 200, -3 * LINE)) + list(range(200, 1100, 3 * LINE))
        long = self.run_scroll(terminal, tops)
        self.assertGreaterEqual(long.header, 30)
        self.assert_above(long, terminal, 900, 200, tops[-1])

    def test_scroll_up_then_back_down_adds_nothing_twice(self):
        terminal = Terminal(make_document())
        tops = list(range(600, 400, -10)) + list(range(400, 700, 10)) + list(range(700, 300, -10))
        long = self.run_scroll(terminal, tops)
        self.assert_above(long, terminal, 600, 310, 700)

    def check_piece1_follows(self, terminal, first, piece1, tops):
        """The view is the whole window; piece 1 = view rows `piece1` at `first`.
        After every read, the long image still knows piece 1's rows, and the
        screen row where piece 1 starts is right, also past its old top and bottom."""
        title = len(terminal.title)
        doc_top = first + piece1[0] - title  # document row where piece 1 starts
        height = piece1[1] - piece1[0]
        long = LongImage(terminal.view(first), piece1)
        for top in tops:
            self.assertTrue(long.add_read(terminal.view(top)), f"lost at top={top}")
            got = strip(long.rows[long.piece1_top:long.piece1_end], terminal.edge)
            self.assertEqual(got, strip(terminal.document[doc_top:doc_top + height], terminal.edge))
            row = long.piece1_top - long.pos  # view row that shows piece 1's first line
            if title <= row < len(terminal.title) + CONTENT:
                self.assertEqual(strip([terminal.view(top)[row]], terminal.edge),
                                 strip([terminal.document[doc_top]], terminal.edge), f"top={top}")
        return long

    def test_piece1_in_the_middle_scroll_down_and_up(self):
        terminal = Terminal(make_document())
        tops = list(range(600, 900, 3 * LINE)) + list(range(900, 400, -3 * LINE)) + list(range(400, 700, 3 * LINE))
        self.check_piece1_follows(terminal, 600, (80, 120), tops)

    def test_piece1_in_the_middle_with_title_bar(self):
        terminal = Terminal(make_document(), title=30, scrollbar=True)
        tops = list(range(600, 1000, 41)) + list(range(1000, 300, -37))
        long = self.check_piece1_follows(terminal, 600, (110, 150), tops)
        self.assertGreaterEqual(long.header, 30)
        self.assertGreaterEqual(long.piece1_top, long.header)  # the title bar is not part of piece 1

    def test_image_round_trip(self):
        rows = make_document(lines=4)
        self.assertEqual(image_rows(rows_image(rows, WIDTH)), rows)


if __name__ == "__main__":
    unittest.main()
