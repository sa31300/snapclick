"""Long-image matcher for the Stack (docs/SPEC.md §2b). No UI.

A screen read of the frame is a list of pixel rows (bytes, 4 bytes per pixel).
LongImage keeps everything seen in the frame, top to bottom, with no repeats,
and knows which long-image row each frame row shows right now.
"""
from PySide6.QtGui import QImage

BLOCKS = 8  # column blocks per row: a scrollbar only spoils one of them
MIN_SCORE = 0.7  # share of equal blocks needed to accept a position
MIN_ROWS = 0.6  # and share of rows that must be fully equal (but the rightmost block)
MIN_BLOCKS = 8  # fewer compared blocks than this is too little to trust
COMMON = 32  # a block found in more places than this says nothing about position
CANDIDATES = 5  # best-voted positions that get a full check
MOVED_ROWS = 0.15  # share of rows that must change to count as a real movement
MIN_WIDTH = 16  # px: never shrink the matched columns below this
STATIC_SHARE = 0.9  # share of marked pixels that must stay put for a static column
STATIC_ROW = 0.75  # share of blocks that must stay put for a static row


def row_blocks(row):
    """A hash for each column block of one pixel row; None for a one-color block."""
    pixels = len(row) // 4
    count = min(BLOCKS, pixels)
    blocks = []
    for i in range(count):
        start, end = pixels * i // count * 4, pixels * (i + 1) // count * 4
        block = row[start:end]
        blank = block.count(block[:4]) == (end - start) // 4
        blocks.append(None if blank else hash(block))
    return tuple(blocks)


def compare(a, b):
    """(equal, compared) blocks of two rows. Blocks blank on both sides are skipped."""
    equal = compared = 0
    for x, y in zip(a, b):
        if x is None and y is None:
            continue
        compared += 1
        equal += x == y
    return equal, compared


def same_place(a, b):
    """Two rows look the same, ignoring the rightmost block (a scrollbar may sit there)."""
    return a[:-1] == b[:-1] if len(a) > 1 else a == b


def kept_place(a, b):
    """A row kept its place between two reads. A few blocks may have changed:
    at the frame's edge it may show a window behind that changes now and then."""
    if same_place(a, b):
        return True
    equal, compared = compare(a[:-1], b[:-1])
    return equal >= STATIC_ROW * compared


def edge_runs(sigs, last):
    """How many rows at the top and at the bottom kept their place between two reads."""
    height = len(sigs)
    top = 0
    while top < height and kept_place(sigs[top], last[top]):
        top += 1
    bottom = 0
    while bottom < height - top and kept_place(sigs[height - 1 - bottom], last[height - 1 - bottom]):
        bottom += 1
    return top, bottom


def static_columns(rows, last):
    """Pixel columns at the left and right edge that did not change between two
    reads but are not one color, like a strip of the window behind. They would
    spoil every match. Returns (left, right): the columns to keep matching.
    One-color columns are kept: they never spoil a match, and text may show
    up there later."""
    width = len(rows[0]) // 4

    def kind(x):
        """'blank' (one color), 'static' or 'moving'. A window behind may change a
        little between two reads, so 'static' allows a few changed pixels; text
        that scrolled changes most of its pixels."""
        now = [row[4 * x:4 * x + 4] for row in rows]
        before = [row[4 * x:4 * x + 4] for row in last]
        background = max(set(now), key=now.count)
        marked = [(a, b) for a, b in zip(now, before) if a != background or b != background]
        if not marked:
            return "blank"
        unchanged = sum(a == b for a, b in marked)
        return "static" if unchanged >= STATIC_SHARE * len(marked) else "moving"

    left = x = 0
    while x < width and (k := kind(x)) != "moving":
        if k == "static":
            left = x + 1
        x += 1
    right = x = width
    while x > left and (k := kind(x - 1)) != "moving":
        if k == "static":
            right = x - 1
        x -= 1
    return left, right


class LongImage:
    """Everything seen in the frame so far. Frame row r shows long row `pos + r`."""

    def __init__(self, first):
        """`first` = the frame's pixel rows at the start (piece 1)."""
        self.rows = list(first)
        self.height = len(first)  # frame height in rows
        self.left, self.right = 0, len(first[0]) // 4  # pixel columns used for matching
        self.top = 0  # static rows at the top of the frame (title bar, padding)
        self.bottom = 0  # static rows at the bottom; cut off the end of piece 1
        self.static_known = False  # set on the first real movement
        self.piece1_end = self.height  # long row where piece 1 ends
        self.pos = 0
        self.lost = False
        self.last_rows = first  # the last read that was found
        self._hash_all()

    def _sig(self, row):
        return row_blocks(row[4 * self.left:4 * self.right])

    def _hash_all(self):
        self.sigs = [self._sig(row) for row in self.rows]
        self.last = [self._sig(row) for row in self.last_rows]
        self.index = {}  # (block column, hash) -> long rows that have it
        for q, sig in enumerate(self.sigs):
            self._index(q, sig)

    def _index(self, q, sig):
        for column, h in enumerate(sig):
            if h is not None:
                self.index.setdefault((column, h), []).append(q)

    def add_read(self, rows):
        """Match a new read of the frame and add the new lines. Returns True if found."""
        sigs = [self._sig(row) for row in rows]
        if sigs == self.last:  # nothing moved
            self.lost = False
            return True

        if self.static_known:
            top, bottom = self._static_now(sigs)
        else:
            # Rows that kept their place since the last read may be static.
            top, bottom = edge_runs(sigs, self.last)
            if self.height - top - bottom >= MOVED_ROWS * self.height:
                # Looks like the first real movement: leave out static edge columns.
                moved = [r for r in range(top, self.height - bottom) if not kept_place(sigs[r], self.last[r])]
                left, right = static_columns([rows[r] for r in moved], [self.last_rows[r] for r in moved])
                if right - left >= MIN_WIDTH and (left, right) != (self.left, self.right):
                    self.left, self.right = left, right
                    self._hash_all()
                    sigs = [self._sig(row) for row in rows]
                    top, bottom = edge_runs(sigs, self.last)
        moving = range(top, self.height - bottom)
        # Long rows to compare with. Until the static rows are known, leave
        # out the maybe-static ones at the bottom of piece 1.
        long_end = len(self.sigs) if self.static_known else self.height - bottom

        best, best_score = None, (0, 0)
        for p in self._candidates(sigs, moving):
            if p == self.pos and not self.static_known:
                score = self._score(sigs, range(self.height), p, 0, len(self.sigs))
            else:
                score = self._score(sigs, moving, p, top, long_end)
            closer = best is not None and abs(p - self.pos) < abs(best - self.pos)
            if score > best_score or (score == best_score and closer):
                best, best_score = p, score
        rows_share, blocks_share = best_score
        if best is None or rows_share < MIN_ROWS or blocks_share < MIN_SCORE:
            self.lost = True
            return False

        if best != self.pos:
            if self.static_known:
                self.top, self.bottom = top, bottom
            else:
                # Blank rows under the title bar are not worth ignoring: text may come there.
                while top > 0 and all(b is None for b in sigs[top - 1]):
                    top -= 1
                self._set_static(top, bottom)
        self.pos = best
        self.last, self.last_rows = sigs, rows
        self.lost = False
        # Frame rows below the end of the long image are new lines: add them.
        start = max(len(self.rows) - best, self.top)
        for r in range(start, self.height - self.bottom):
            self.rows.append(rows[r])
            self.sigs.append(sigs[r])
            self._index(len(self.sigs) - 1, sigs[r])
        return True

    def _static_now(self, sigs):
        """The static rows, minus rows at their inner side that changed: blank
        lines can look static by chance on the first movement. Only the inner
        side counts: the outer edge may show a window behind that changes."""
        top = self.top
        while top > 0 and not same_place(sigs[top - 1], self.last[top - 1]):
            top -= 1
        bottom = self.bottom
        while bottom > 0 and not same_place(sigs[self.height - bottom], self.last[self.height - bottom]):
            bottom -= 1
        return top, bottom

    def _candidates(self, sigs, rows):
        """Positions where many blocks of the read are found, plus the current one."""
        votes = {}
        for r in rows:
            for column, h in enumerate(sigs[r]):
                if h is None:
                    continue
                places = self.index.get((column, h), ())
                if len(places) > COMMON:
                    continue
                for q in places:
                    votes[q - r] = votes.get(q - r, 0) + 1
        ranked = sorted(votes, key=lambda p: (-votes[p], abs(p - self.pos)))
        return [self.pos] + [p for p in ranked[:CANDIDATES] if p != self.pos]

    def _score(self, sigs, rows, p, long_start, long_end):
        """(share of fully equal rows, share of equal blocks) when frame row r is
        long row p + r. Blocks find the place even with a scrollbar in the frame;
        rows make sure it is the right place when lines differ only a little
        (like a line number): at a wrong place almost no row is fully equal."""
        equal = compared = rows_equal = rows_compared = 0
        for r in rows:
            q = p + r
            if long_start <= q < long_end:
                a, b = sigs[r], self.sigs[q]
                e, c = compare(a, b)
                equal += e
                compared += c
                if compare(a[:-1], b[:-1])[1]:  # the row has text (besides a scrollbar)
                    rows_compared += 1
                    rows_equal += same_place(a, b)
        if compared < MIN_BLOCKS or not rows_compared:
            return 0, 0
        return rows_equal / rows_compared, equal / compared

    def _set_static(self, top, bottom):
        """First real movement: ignore static rows from now on, and cut the
        static rows off the bottom of piece 1 so new lines join cleanly."""
        if top + bottom >= self.height:
            return
        self.static_known = True
        self.top, self.bottom = top, bottom
        self.piece1_end = self.height - bottom
        if bottom:
            del self.rows[self.height - bottom:]
            del self.sigs[self.height - bottom:]
            self.index = {}
            for q, sig in enumerate(self.sigs):
                self._index(q, sig)


def image_rows(image):
    """Pixel rows of a QImage, as a list of bytes."""
    image = image.convertToFormat(QImage.Format.Format_RGB32)
    data = bytes(image.constBits())
    stride, width = image.bytesPerLine(), image.width() * 4
    return [data[y * stride:y * stride + width] for y in range(image.height())]


def rows_image(rows, width):
    """A QImage from pixel rows (the opposite of image_rows)."""
    data = b"".join(rows)
    return QImage(data, width, len(rows), width * 4, QImage.Format.Format_RGB32).copy()
