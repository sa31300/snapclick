"""Long-image matcher for the Stack (docs/SPEC.md §2b). No UI.

A screen read of the frame is a list of pixel rows (bytes, 4 bytes per pixel).
LongImage keeps everything seen in the frame, top to bottom, with no repeats,
and knows which long-image row each frame row shows right now.
"""
from PySide6.QtGui import QImage

BLOCKS = 8  # column blocks per row: a scrollbar only spoils one of them
MIN_SCORE = 0.7  # share of equal blocks needed to accept a position
MIN_BLOCKS = 8  # fewer compared blocks than this is too little to trust
COMMON = 32  # a block found in more places than this says nothing about position
CANDIDATES = 5  # best-voted positions that get a full check


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


def edge_runs(sigs, last):
    """How many rows at the top and at the bottom did not change between two reads."""
    height = len(sigs)
    top = 0
    while top < height and same_place(sigs[top], last[top]):
        top += 1
    bottom = 0
    while bottom < height - top and same_place(sigs[height - 1 - bottom], last[height - 1 - bottom]):
        bottom += 1
    return top, bottom


class LongImage:
    """Everything seen in the frame so far. Frame row r shows long row `pos + r`."""

    def __init__(self, first):
        """`first` = the frame's pixel rows at the start (piece 1)."""
        self.rows = list(first)
        self.sigs = [row_blocks(row) for row in first]
        self.height = len(first)  # frame height in rows
        self.top = 0  # static rows at the top of the frame (title bar, padding)
        self.bottom = 0  # static rows at the bottom; cut off the end of piece 1
        self.static_known = False  # set on the first real movement
        self.pos = 0
        self.lost = False
        self.last = self.sigs  # the last read that was found
        self.index = {}  # (block column, hash) -> long rows that have it
        for q, sig in enumerate(self.sigs):
            self._index(q, sig)

    def _index(self, q, sig):
        for column, h in enumerate(sig):
            if h is not None:
                self.index.setdefault((column, h), []).append(q)

    def add_read(self, rows):
        """Match a new read of the frame and add the new lines. Returns True if found."""
        sigs = [row_blocks(row) for row in rows]
        if sigs == self.last:  # nothing moved
            self.lost = False
            return True

        # Rows that kept their place since the last read may be static.
        top, bottom = edge_runs(sigs, self.last)
        if self.static_known:
            # Blank lines can look static by chance; a row that changed is not static.
            top, bottom = min(top, self.top), min(bottom, self.bottom)
        moving = range(top, self.height - bottom)
        # Long rows to compare with. Until the static rows are known, leave
        # out the maybe-static ones at the bottom of piece 1.
        long_end = len(self.sigs) if self.static_known else self.height - bottom

        best, best_score = None, 0
        for p in self._candidates(sigs, moving):
            if p == self.pos and not self.static_known:
                score = self._score(sigs, range(self.height), p, 0, len(self.sigs))
            else:
                score = self._score(sigs, moving, p, top, long_end)
            closer = best is not None and abs(p - self.pos) < abs(best - self.pos)
            if score > best_score or (score == best_score and closer):
                best, best_score = p, score
        if best is None or best_score < MIN_SCORE:
            self.lost = True
            return False

        if best != self.pos:
            if self.static_known:
                self.top, self.bottom = top, bottom
            else:
                self._set_static(top, bottom)
        self.pos = best
        self.last = sigs
        self.lost = False
        # Frame rows below the end of the long image are new lines: add them.
        start = max(len(self.rows) - best, self.top)
        for r in range(start, self.height - self.bottom):
            self.rows.append(rows[r])
            self.sigs.append(sigs[r])
            self._index(len(self.sigs) - 1, sigs[r])
        return True

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
        """Share of equal blocks when frame row r is long row p + r."""
        equal = compared = 0
        for r in rows:
            q = p + r
            if long_start <= q < long_end:
                e, c = compare(sigs[r], self.sigs[q])
                equal += e
                compared += c
        return equal / compared if compared >= MIN_BLOCKS else 0

    def _set_static(self, top, bottom):
        """First real movement: ignore static rows from now on, and cut the
        static rows off the bottom of piece 1 so new lines join cleanly."""
        if top + bottom >= self.height:
            return
        self.static_known = True
        self.top, self.bottom = top, bottom
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
