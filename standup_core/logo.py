"""The Aube sunrise logo, shown when standup.py starts in an interactive terminal."""

LOGO = r"""
                 |
         \       |       /
    `.    \      |      /    .'
      `.   \     :     /   .'
 `-.    `.    .-'''-.    .'    .-'
    `-.     /         \     .-'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     ━━━━━━━━━━━━━━━━━━━━━━━━━
         ━━━━━━━━━━━━━━━━━
              ━━━━━━━

              a u b e
""".strip("\n")

# Same dawn gradient as images/logo.svg: golden rays at the top, pink reflection at the bottom.
_TOP = (0xFF, 0xC2, 0x7A)
_BOTTOM = (0xFF, 0x5E, 0x8A)
_RESET = "\x1b[0m"


def _color_at(t: float) -> tuple[int, int, int]:
    return tuple(round(a + (b - a) * t) for a, b in zip(_TOP, _BOTTOM, strict=True))


def render(color: bool) -> str:
    """Return the logo, optionally coloured line by line with 24-bit ANSI escapes."""
    if not color:
        return LOGO
    lines = LOGO.splitlines()
    last = max(len(lines) - 1, 1)
    colored = []
    for i, line in enumerate(lines):
        r, g, b = _color_at(i / last)
        colored.append(f"\x1b[38;2;{r};{g};{b}m{line}")
    return "\n".join(colored) + _RESET
