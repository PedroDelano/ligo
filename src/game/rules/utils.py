from game.rules.models import StoneColor


def invert_color(color: StoneColor) -> StoneColor:
    if isinstance(color, str):
        color = StoneColor(color)
    assert isinstance(color, StoneColor)
    if color == StoneColor.BLACK:
        return StoneColor.WHITE
    return StoneColor.BLACK
