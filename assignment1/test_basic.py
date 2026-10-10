"""规则与 AI 的基本检查。直接运行：python test_basic.py"""

import copy
import os
import random

from gomoku_ai import GomokuAI
from gomoku_game import GomokuGame, winning_run

os.environ["GOMOKU_DEBUG"] = "1"


def test_rules():
    game = GomokuGame(5, 5)
    for col in range(5):
        game.place(0, col)
        if col < 4:
            game.place(1, col)
    assert game.winner == 1
    assert len(game.win_cells) == 5

    board = [[0] * 6 for _ in range(6)]
    for col in range(6):
        board[2][col] = 1
    assert len(winning_run(board, 2, 0, 5)) == 6

    game = GomokuGame(5, 4)
    for row in range(3):
        game.place(row, row)
        game.place(row, 0 if row != 0 else 1)
    game.place(3, 3)
    assert game.winner == 1

    # 3×3、K=3 的一种和棋走法（黑先）。
    game = GomokuGame(3, 3)
    for r, c in (
        (0, 0), (0, 1), (0, 2),
        (2, 0), (1, 0), (1, 1),
        (2, 1), (1, 2), (2, 2),
    ):
        assert not game.is_over
        game.place(r, c)
    assert game.winner == 0

    try:
        game.place(0, 0)
        raise AssertionError("ended game should reject")
    except ValueError:
        pass


def test_ai_tactics():
    n, k = 9, 5
    board = [[0] * n for _ in range(n)]
    for c in range(2, 6):
        board[4][c] = 1
    ai = GomokuAI(1, n, k)
    move = ai.get_move(copy.deepcopy(board), None, 1.0)
    assert move in {(4, 1), (4, 6)}, move

    ai = GomokuAI(2, n, k)
    move = ai.get_move(copy.deepcopy(board), (4, 5), 1.0)
    assert move in {(4, 1), (4, 6)}, move

    board = [[0] * n for _ in range(n)]
    for c, col in enumerate((1, 2, 4, 5)):
        board[3][col] = 1
    ai = GomokuAI(1, n, k)
    assert ai.get_move(copy.deepcopy(board), None, 1.0) == (3, 3)

    original = copy.deepcopy(board)
    ai.get_move(board, None, 0.5)
    assert board == original


def test_sizes_and_legality():
    random.seed(1)
    for n, k, limit in ((5, 3, 0.2), (7, 4, 0.25), (9, 5, 0.3), (15, 5, 0.35)):
        game = GomokuGame(n, k)
        agents = {1: GomokuAI(1, n, k), 2: GomokuAI(2, n, k)}
        agents[1].depth_cap = 3
        agents[2].depth_cap = 2
        guard = 0
        while not game.is_over:
            agent = agents[game.current]
            board = game.clone_board()
            move = agent.get_move(board, game.last_move, limit)
            assert board == game.board
            assert game.is_legal(*move), move
            game.place(*move)
            guard += 1
            assert guard <= n * n
        assert game.winner in (0, 1, 2)


def test_beats_obvious_random_slice():
    from random_ai import GomokuAI as RandomAI

    wins = 0
    for index in range(4):
        random.seed(index)
        our_black = index % 2 == 0
        game = GomokuGame(9, 5)
        our = GomokuAI(1 if our_black else 2, 9, 5)
        opp = RandomAI(2 if our_black else 1, 9, 5)
        while not game.is_over:
            actor = our if game.current == our.player_id else opp
            game.place(*actor.get_move(game.clone_board(), game.last_move, 0.4))
        if game.winner == our.player_id:
            wins += 1
    assert wins == 4, wins


if __name__ == "__main__":
    test_rules()
    test_ai_tactics()
    test_sizes_and_legality()
    test_beats_obvious_random_slice()
    print("ok")
