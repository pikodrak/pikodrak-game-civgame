"""Hex grid math for odd-r offset (pointy-top) coordinates."""


def hex_neighbors(q, r):
    """Return the 6 neighbors of hex (q, r) in odd-r offset coords."""
    if r & 1:  # odd row
        return [
            (q, r-1), (q+1, r-1), (q+1, r),
            (q, r+1), (q+1, r+1), (q-1, r)
        ]
    else:  # even row
        return [
            (q-1, r-1), (q, r-1), (q+1, r),
            (q, r+1), (q-1, r+1), (q-1, r)
        ]


def offset_to_cube(q, r):
    """Convert odd-r offset coords to cube coords (x, y, z)."""
    x = q - (r - (r & 1)) // 2
    z = r
    y = -x - z
    return x, y, z


def hex_distance(q1, r1, q2, r2):
    """Hex distance between two offset coords using cube coord max-axis."""
    x1, y1, z1 = offset_to_cube(q1, r1)
    x2, y2, z2 = offset_to_cube(q2, r2)
    return max(abs(x1-x2), abs(y1-y2), abs(z1-z2))
