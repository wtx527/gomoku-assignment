"""广义五子棋规则：(N, K)-game。

棋盘为 N×N，0 空、1 黑、2 白。黑先。横、竖、两条斜线上连续至少 K 子即胜，
长连也算胜，无禁手。棋盘下满仍无 K 连则为和棋。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


class GomokuGame:
    def __init__(self, board_size: int = 15, win_length: int = 5):
        if board_size < 1:
            raise ValueError("board_size 必须为正整数")
        if not 1 <= win_length <= board_size:
            raise ValueError("win_length 必须满足 1 ≤ K ≤ N")
        self.board_size = board_size
        self.win_length = win_length
        self.board = [[0 for _ in range(board_size)] for _ in range(board_size)]
        self.current = 1
        self.last_move: tuple[int, int] | None = None
        self.winner: int | None = None  # 1 或 2；和棋时为 0；进行中为 None
        self.win_cells: list[tuple[int, int]] = []
        self.move_count = 0

    @property
    def is_over(self) -> bool:
        return self.winner is not None

    def clone_board(self) -> list[list[int]]:
        return [row[:] for row in self.board]

    def place(self, row: int, col: int) -> None:
        if self.winner is not None:
            raise ValueError("对局已结束")
        if not self.is_legal(row, col):
            raise ValueError(f"非法落子 ({row}, {col})")
        player = self.current
        self.board[row][col] = player
        self.last_move = (row, col)
        self.move_count += 1
        cells = winning_run(self.board, row, col, self.win_length)
        if cells:
            self.winner = player
            self.win_cells = cells
        elif self.move_count >= self.board_size * self.board_size:
            self.winner = 0
        else:
            self.current = 3 - player

    def is_legal(self, row: int, col: int) -> bool:
        n = self.board_size
        return 0 <= row < n and 0 <= col < n and self.board[row][col] == 0


def winning_run(
    board: list[list[int]], row: int, col: int, win_length: int
) -> list[tuple[int, int]]:
    """若 (row, col) 上的棋子所在连续段长度 ≥ K，返回该段坐标，否则返回空列表。"""
    n = len(board)
    player = board[row][col]
    if player == 0:
        return []
    directions = ((0, 1), (1, 0), (1, 1), (1, -1))
    for dr, dc in directions:
        cells = [(row, col)]
        for sign in (1, -1):
            r, c = row + sign * dr, col + sign * dc
            while 0 <= r < n and 0 <= c < n and board[r][c] == player:
                cells.append((r, c))
                r += sign * dr
                c += sign * dc
        if len(cells) >= win_length:
            return cells
    return []


def format_board(board: list[list[int]], last_move: tuple[int, int] | None = None) -> str:
    n = len(board)
    mark = {0: ".", 1: "X", 2: "O"}
    header = "   " + " ".join(f"{c:>2}" for c in range(n))
    lines = [header]
    for r in range(n):
        cells = []
        for c in range(n):
            text = mark[board[r][c]]
            if last_move == (r, c):
                text = text.lower() if text != "." else text
            cells.append(f"{text:>2}")
        lines.append(f"{r:>2} " + " ".join(cells))
    return "\n".join(lines)


def load_gomoku_ai(path: str | Path):
    """从任意路径加载符合统一协议的 GomokuAI 类。"""
    file_path = Path(path).resolve()
    module_name = "gomoku_ai_dyn_" + str(abs(hash(str(file_path))))
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 AI 文件: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "GomokuAI"):
        raise ImportError(f"{file_path} 中没有 GomokuAI 类")
    return module.GomokuAI
