"""Split long text into overlapping chunks, preferring paragraph then sentence boundaries."""


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[tuple[int, int, str]]:
    """Return (char_start, char_end, text) triples. Offsets point into the original string."""
    if size <= overlap:
        raise ValueError("size must be larger than overlap")
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            floor = start + size // 2
            cut = text.rfind("\n\n", floor, end)
            if cut != -1:
                end = cut
            else:
                cut = text.rfind(". ", floor, end)
                if cut != -1:
                    end = cut + 1
        piece = text[start:end].strip()
        if piece:
            out.append((start, end, piece))
        if end >= n:
            break
        nxt = end - overlap
        start = nxt if nxt > start else end  # always make progress
    return out
