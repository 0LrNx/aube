import re

from standup_core.logo import LOGO, render

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_render_without_color_is_the_plain_logo():
    assert render(color=False) == LOGO
    assert "\x1b" not in LOGO
    assert "a u b e" in LOGO


def test_render_with_color_wraps_each_line_in_a_truecolor_escape_and_resets():
    colored = render(color=True)

    assert "\x1b[38;2;" in colored
    assert colored.endswith("\x1b[0m")
    assert _ANSI.sub("", colored) == LOGO
