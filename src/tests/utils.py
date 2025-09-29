def ascii_go_board(moves, size=None, show_coords=True, mark_last=True):
    """
    Render a Go board as ASCII.

    Args:
        moves: iterable of dicts/objects with fields x, y, color ("B"/"W"), move_number.
               Assumed to be the *alive* stones you want to display.
        size:  board size (e.g., 19, 13, 9). If None, inferred from max x/y in moves.
        show_coords: print numeric axes around the board.
        mark_last: mark last move as lowercase ('b' or 'w').

    Returns:
        str with the ASCII board.
    """

    def getv(m, k):
        # supports dicts and simple objects
        return m[k] if isinstance(m, dict) else getattr(m, k)

    if not moves:
        if size is None:
            size = 19  # default if nothing to infer from
    else:
        if size is None:
            mx = max(getv(m, "x") for m in moves)
            my = max(getv(m, "y") for m in moves)
            size = max(mx, my) + 1

    # Grid uses '+' for empty, 'B' for black, 'W' for white.
    grid = [["+" for _ in range(size)] for _ in range(size)]

    # Place stones; keep track of last move number to mark it later.
    last_idx = None
    last_num = -1
    for idx, m in enumerate(moves):
        x = int(getv(m, "x"))
        y = int(getv(m, "y"))
        c = str(getv(m, "color")).upper()
        grid[y][x] = "B" if c == "B" else "W"
        num = int(getv(m, "move_number"))
        if num > last_num:
            last_num = num
            last_idx = (x, y, c)

    # Mark last move in lowercase for quick spotting
    if mark_last and last_idx is not None:
        lx, ly, lc = last_idx
        grid[ly][lx] = "b" if lc == "B" else "w"

    # Build string
    lines = []
    if show_coords:
        header = "   " + " ".join(f"{i:2d}" for i in range(size))
        lines.append(header)

    for row in range(size):
        # y=0 at top (matches common matrix/array visualizations)
        if show_coords:
            prefix = f"{row:2d} "
        else:
            prefix = ""
        lines.append(prefix + " ".join(f"{cell:>2s}" for cell in grid[row]))

    return "\n".join(lines)
