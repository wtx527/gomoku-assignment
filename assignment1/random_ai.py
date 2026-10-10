"""参考 AI：在所有空位中均匀随机选择。用于功能测试和实力基线。"""

import random

NAME = "random"


class GomokuAI:
    def __init__(self, player_id, board_size, win_length):
        self.player_id = player_id
        self.board_size = board_size
        self.win_length = win_length

    def get_move(self, board, last_opponent_move, time_limit):
        empties = [
            (r, c)
            for r in range(self.board_size)
            for c in range(self.board_size)
            if board[r][c] == 0
        ]
        return random.choice(empties)
