"""Squarified treemap layout (Bruls et al.). Pure python, no GUI imports."""


def _worst(row, side):
    s = sum(row)
    return max(side * side * max(row) / (s * s), (s * s) / (side * side * min(row)))


def squarify(items, x, y, w, h):
    """items: [(value, payload)] with value > 0, sorted descending.
    Returns [(x, y, w, h, payload)] filling the rectangle."""
    items = [(v, p) for v, p in items if v > 0]
    if not items or w <= 0 or h <= 0:
        return []
    scale = w * h / sum(v for v, _ in items)
    rest = [(v * scale, p) for v, p in items]
    out = []
    while rest:
        side = min(w, h)
        row, i = [rest[0]], 1
        while i < len(rest) and _worst([a for a, _ in row + [rest[i]]], side) <= \
                _worst([a for a, _ in row], side):
            row.append(rest[i])
            i += 1
        rest = rest[i:]
        s = sum(a for a, _ in row)
        if w >= h:
            cw, yy = s / h, y
            for a, p in row:
                out.append((x, yy, cw, a / cw, p))
                yy += a / cw
            x, w = x + cw, w - cw
        else:
            rh, xx = s / w, x
            for a, p in row:
                out.append((xx, y, a / rh, rh, p))
                xx += a / rh
            y, h = y + rh, h - rh
    return out
