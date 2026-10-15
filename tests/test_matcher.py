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


def make_document(lines=150, seed=1):
    """Made-up terminal text: lines of random 'glyphs', some lines empty."""
    rng = random.Random(seed)
    rows = []
    for _ in range(lines):
        length = 0 if rng.random() < 0.15 else rng.randint(8, WIDTH)
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

    def __init__(self, document, title=0, padding=0, scrollbar=False):
        self.document = document
        self.title = make_title(title) if title else []
        self.padding = padding
        self.scrollbar = scrollbar

    def view(self, top):
        top = max(0, min(top, len(self.document) - CONTENT))
        rows = self.document[top:top + CONTENT] + [BG * WIDTH] * self.padding
        if self.scrollbar:
            area = len(rows)
            thumb_start = top * area // len(self.document)
            thumb_end = thumb_start + CONTENT * area // len(self.document)
            rows = [row[:-SCROLLBAR * 4] + (THUMB if thumb_start <= y < thumb_end else TRACK) * SCROLLBAR
                    for y, row in enumerate(rows)]
        return self.title + rows

    def expected(self, last_top):
        """The perfect long image after scrolling down to `last_top`."""
        return self.title + self.document[:last_top + CONTENT]


def strip(rows):
    """Rows without the scrollbar columns."""
    return [row[:-SCROLLBAR * 4] for row in rows]


class MatcherTest(unittest.TestCase):
    def run_scroll(self, terminal, tops):
        long = LongImage(terminal.view(tops[0]))
        for top in tops[1:]:
            self.assertTrue(long.add_read(terminal.view(top)), f"lost at top={top}")
        return long

    def assert_joined(self, long, terminal, last_top, slack=0):
        """Every line exactly once, in order. `slack` = rows that may be missing at the very end."""
        expected = strip(terminal.expected(last_top))
        got = strip(long.rows)
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

    def test_image_round_trip(self):
        rows = make_document(lines=4)
        self.assertEqual(image_rows(rows_image(rows, WIDTH)), rows)


if __name__ == "__main__":
    unittest.main()
