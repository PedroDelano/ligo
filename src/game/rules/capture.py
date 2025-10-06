from typing import List, Tuple

from django.db.models import Q

from ..models import Board as BoardDB
from ..models import Move as MoveDB
from .groups import Groups
from .models import Game, Move, StoneColor
from .utils import invert_color as _invert_color


class Capture:
    @classmethod
    def remove_captured_stones(
        cls,
        game: Game,
        last_played_color: StoneColor,
        invert_color: bool = False,
        debug: bool = False,
    ) -> Tuple[Game, List[Move]]:
        assert isinstance(game, Game)
        assert isinstance(debug, bool)
        assert isinstance(invert_color, bool)
        captured_stones: List[Move] = []
        last_played_color = StoneColor(last_played_color)

        if invert_color is True:
            check_color = _invert_color(last_played_color)
        else:
            check_color = last_played_color

        current_move_state = [
            move
            for group in Groups.get_groups(game, last_played_color)
            for move in group.stones
        ]

        if debug:
            print(
                f"Last played color: {last_played_color}, checking for captures of {check_color}"
            )

        if len(game.moves) == 0:
            return game, captured_stones

        check_groups = Groups.get_groups(game, check_color)

        if debug:
            for group in check_groups:
                print(
                    f"Group color: {group.color}, alive: {group.alive}, liberties: {group.liberties}, size: {group.size}"
                )
                for stone in group.stones:
                    print(f"  Stone at ({stone.x}, {stone.y})")

        for group in check_groups:
            if group.alive is True:
                if debug:
                    print(
                        f"Keeping group of color {group.color} with stones at {[(s.x, s.y) for s in group.stones]}"
                    )
                current_move_state.extend(group.stones)
            else:
                if debug:
                    print(
                        f"Capturing group of color {group.color} with stones at {[(s.x, s.y) for s in group.stones]}"
                    )
                captured_stones.extend(group.stones)

        assert all(isinstance(m, Move) for m in current_move_state)
        assert all(isinstance(m, Move) for m in captured_stones)
        return Game(board=game.board, moves=current_move_state), captured_stones

    def mark_captured(board: BoardDB, stones: List[Move]) -> int:
        assert isinstance(board, BoardDB)
        assert all(isinstance(s, Move) for s in stones)

        if not stones:
            return 0

        q = Q()
        for s in stones:
            q |= Q(x=s.x, y=s.y)

        captured_color = stones[0].color
        assert all([stone.color == captured_color for stone in stones])

        # Update the moves in the database to mark them as dead
        count = MoveDB.objects.filter(board=board).filter(q).update(alive=False)

        # Update the capture count on the board
        # When white stones are captured, black gets the capture points
        # When black stones are captured, white gets the capture points
        if captured_color == StoneColor.WHITE:
            board.black_captures += len(stones)
        elif captured_color == StoneColor.BLACK:
            board.white_captures += len(stones)

        board.save(update_fields=["white_captures", "black_captures"])

        return count
