from typing import List, Tuple

import pydantic
from django.contrib.auth import get_user_model
from pydantic import BaseModel, Field

from player_queue.models import PlayerRating

from ..models import GAME_STATUS, Board, Game, Move
from ..rules import models, scoring

User = get_user_model()


class TerritoryData(BaseModel):
    black: List[Tuple[int, int]] = Field(default_factory=list)
    white: List[Tuple[int, int]] = Field(default_factory=list)
    neutral: List[Tuple[int, int]] = Field(default_factory=list)


class ScoreData(pydantic.BaseModel):
    black_stones: int
    black_territory: int
    black_total: float
    white_stones: int
    white_territory: int
    white_total: float
    komi: float
    winner: models.StoneColor
    margin: float


class FinishGame:
    @staticmethod
    def _update_user_rating(user, new_rating: int) -> None:
        user = User.objects.get(username=user)
        PlayerRating.objects.create(
            user=user,
            skill_level=new_rating,
        )

    @staticmethod
    def _get_user_rating(user) -> int:
        user_rating = PlayerRating.objects.filter(user=user).first()
        if not user_rating:
            return 400
        return user_rating.skill_level

    @staticmethod
    def get_score_data(board_id: int) -> Tuple[ScoreData, TerritoryData]:
        assert isinstance(board_id, int)
        board = Board.objects.filter(id=board_id).first()

        moves = list(
            Move.objects.filter(board=board, alive=True)
            .order_by("move_number")
            .values("x", "y", "color", "move_number")
        )
        game_model = models.Game(
            board=models.Board(size=board.size),
            moves=[models.Move(**move) for move in moves],
        )

        score = scoring.Scoring.calculate_score(game_model)
        territories = scoring.Scoring._find_territories(
            game_model, {(m.x, m.y): m.color for m in game_model.moves}
        )

        territory_data = {"black": [], "white": [], "neutral": []}

        for territory in territories:
            points_list = [(x, y) for x, y in territory.points]
            if territory.owner == scoring.TerritoryOwner.BLACK:
                territory_data["black"].extend(points_list)
            elif territory.owner == scoring.TerritoryOwner.WHITE:
                territory_data["white"].extend(points_list)
            else:
                territory_data["neutral"].extend(points_list)

        score_data = {
            "black_stones": score.black_stones,
            "black_territory": score.black_territory,
            "black_total": score.black_total,
            "white_stones": score.white_stones,
            "white_territory": score.white_territory,
            "white_total": score.white_total,
            "komi": score.komi,
            "winner": (
                models.StoneColor.BLACK
                if score.black_total > score.white_total
                else models.StoneColor.WHITE
            ),
            "margin": score.margin,
        }

        return ScoreData(**score_data), TerritoryData(**territory_data)

    @classmethod
    def finish_game(cls, board_id: int) -> Tuple[ScoreData, TerritoryData]:
        board = Board.objects.filter(id=board_id).first()
        game = Game.objects.filter(id=board.game_id).first()

        score, territory_data = cls.get_score_data(board_id)
        assert isinstance(score, ScoreData)

        # Update game status
        game.status = (
            GAME_STATUS.BLACK_WON.value
            if score.winner == models.StoneColor.BLACK
            else GAME_STATUS.WHITE_WON.value
        )
        game.save()

        winner = (
            game.user_black
            if score.winner == models.StoneColor.BLACK
            else game.user_white
        )
        loser = game.user_black if winner == game.user_white else game.user_white

        winner_rating = cls._get_user_rating(winner)
        loser_rating = cls._get_user_rating(loser)

        assert isinstance(winner_rating, int)
        assert isinstance(loser_rating, int)

        rating_diff = abs(winner_rating - loser_rating)
        rating_gain_lost = max(min(rating_diff, 25), 5)

        cls._update_user_rating(winner, winner_rating + rating_gain_lost)
        cls._update_user_rating(loser, loser_rating - rating_gain_lost)

        return score, territory_data
