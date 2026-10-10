"""统一对战协议 v1：Minimax + Alpha-Beta 的广义五子棋 AI。

决策来自运行时搜索，而不是固定开局库或针对特定对手的策略。
N 与 K 只从构造参数读取。本文件不依赖同目录下的其他模块，裁判可单独加载。
"""

from __future__ import annotations

import os
import random
import time
import traceback

NAME = "minimax-ab"

# 终局分数必须高于任何静态评估的累加，又低于搜索用的无穷大。
WIN = 5_000_000
INF = 10**9
_DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))


class SearchTimeout(Exception):
    pass


def pattern_score(length: int, open_ends: int, win_length: int) -> int:
    """连续棋段的启发式分数。以距离胜利还差几子（K - length）分档，因此随 K 变化。

    open_ends 为 2 表示两端都能延伸（活连），为 1 表示只有一端（眠连），为 0 表示死连。
    """
    if length >= win_length:
        return 100_000
    if length <= 0 or open_ends <= 0:
        return 0
    gap = win_length - length
    if gap == 1:
        return 200_000 if open_ends == 2 else 50_000
    if gap == 2:
        return 2_000 if open_ends == 2 else 200
    if gap == 3:
        return 200 if open_ends == 2 else 20
    return 10 if open_ends == 2 else 2


class GomokuAI:
    """课程裁判按此接口加载。每局一个新实例。"""

    def __init__(self, player_id: int, board_size: int, win_length: int):
        self.player_id = int(player_id)
        self.board_size = int(board_size)
        self.win_length = int(win_length)
        self.lines = _build_lines(self.board_size)
        # 下面两个属性只给本地对比实验用，裁判不会设置它们。
        self.depth_cap: int | None = None
        self.eval_mode = "pattern"
        self.last_depth = 0
        self.last_nodes = 0
        self.last_time = 0.0
        self.last_score = 0
        self.board: list[list[int]] = []
        self.stones: list[tuple[int, int]] = []
        self.empty = 0
        self.history: dict[tuple[int, int], int] = {}
        self.nodes = 0
        self.me = self.player_id
        self.opp = 3 - self.player_id

    def get_move(self, board, last_opponent_move, time_limit):
        try:
            move = self._decide(board, last_opponent_move, float(time_limit))
        except Exception:
            if os.environ.get("GOMOKU_DEBUG"):
                traceback.print_exc()
            move = None
        if not _is_legal_move(board, move):
            move = _fallback_move(board)
        return (int(move[0]), int(move[1]))

    def _decide(self, board, last_opponent_move, time_limit: float):
        self._load(board)
        self.history = {}
        self.nodes = 0
        self.last_depth = 0
        self.last_score = 0
        started = time.perf_counter()
        reserve = min(0.30, max(0.04, time_limit * 0.10))
        deadline = started + max(0.01, time_limit - reserve)

        focal = _as_cell(last_opponent_move)
        ordered = self._ordered_moves(self.me, focal, rich=True)
        if not ordered:
            self.last_time = time.perf_counter() - started
            return _fallback_move(board)
        # 只有一步可下（开局中心，或唯一的取胜/防守点）时不必再搜索。
        if len(ordered) == 1:
            self.last_nodes = 0
            self.last_time = time.perf_counter() - started
            return ordered[0]

        best = ordered[0]
        best_score = None
        max_depth = self.depth_cap if self.depth_cap else _default_max_depth(self.board_size)
        last_iter = 0.0

        if time.perf_counter() < deadline:
            for depth in range(1, max_depth + 1):
                now = time.perf_counter()
                # 上一层耗时 × 分支估计若已放不进剩余时间，就不再开新的一层。
                if last_iter > 0.02 and now + last_iter * 2 > deadline:
                    break
                if now >= deadline:
                    break
                moves = self._ordered_moves(self.me, focal, rich=True)
                if best in moves:
                    moves.remove(best)
                    moves.insert(0, best)
                t1 = time.perf_counter()
                try:
                    mv, score, complete = self._search_root(depth, deadline, moves)
                except SearchTimeout:
                    break
                last_iter = time.perf_counter() - t1
                best, best_score = mv, score
                self.last_score = score
                if complete or score >= WIN // 2:
                    self.last_depth = depth
                if (not complete) or score >= WIN // 2 or score <= -(WIN // 2):
                    break

        self.last_nodes = self.nodes
        self.last_time = time.perf_counter() - started
        return best

    def _load(self, board) -> None:
        n = self.board_size
        self.board = [list(board[r]) for r in range(n)]
        self.stones = [
            (r, c) for r in range(n) for c in range(n) if self.board[r][c] != 0
        ]
        self.empty = n * n - len(self.stones)
        self.me = self.player_id
        self.opp = 3 - self.player_id

    def _search_root(self, depth: int, deadline: float, moves: list[tuple[int, int]]):
        alpha = -INF
        best_score = -INF
        best_moves: list[tuple[int, int]] = []
        completed = False
        complete = True
        for r, c in moves:
            if time.perf_counter() >= deadline:
                if not completed:
                    raise SearchTimeout
                complete = False
                break
            self._place(r, c, self.me)
            score = None
            try:
                if self._is_win(r, c):
                    score = WIN - 1
                else:
                    score = self._minimax(
                        depth - 1, alpha, INF, self.opp, (r, c), 1, deadline
                    )
            except SearchTimeout:
                score = None
            finally:
                self._undo(r, c)
            if score is None:
                if not completed:
                    raise SearchTimeout
                complete = False
                break
            completed = True
            if score > best_score:
                best_score = score
                best_moves = [(r, c)]
                alpha = score
            elif score == best_score:
                best_moves.append((r, c))
            if score >= WIN // 2:
                break
        if not best_moves:
            raise SearchTimeout
        return random.choice(best_moves), best_score, complete

    def _minimax(self, depth, alpha, beta, to_move, last, ply, deadline) -> int:
        self.nodes += 1
        if (self.nodes & 63) == 0 and time.perf_counter() >= deadline:
            raise SearchTimeout

        if last is not None and self._is_win(last[0], last[1]):
            winner = self.board[last[0]][last[1]]
            return (WIN - ply) if winner == self.me else -(WIN - ply)
        if self.empty == 0:
            return 0
        if depth == 0:
            return self._evaluate()

        moves = self._ordered_moves(to_move, last, rich=False)
        if not moves:
            return 0

        opponent = 3 - to_move
        if to_move == self.me:
            value = -INF
            for r, c in moves:
                self._place(r, c, to_move)
                try:
                    value = max(
                        value,
                        self._minimax(
                            depth - 1, alpha, beta, opponent, (r, c), ply + 1, deadline
                        ),
                    )
                finally:
                    self._undo(r, c)
                if value > alpha:
                    alpha = value
                if alpha >= beta:
                    self.history[(r, c)] = self.history.get((r, c), 0) + depth * depth
                    break
            return value

        value = INF
        for r, c in moves:
            self._place(r, c, to_move)
            try:
                value = min(
                    value,
                    self._minimax(
                        depth - 1, alpha, beta, opponent, (r, c), ply + 1, deadline
                    ),
                )
            finally:
                self._undo(r, c)
            if value < beta:
                beta = value
            if alpha >= beta:
                self.history[(r, c)] = self.history.get((r, c), 0) + depth * depth
                break
        return value

    def _ordered_moves(self, player: int, focal, rich: bool) -> list[tuple[int, int]]:
        """候选着法：紧邻已有棋子的空位；立即取胜或必须防守的点始终保留。"""
        candidates = self._nearby_empties(focal)
        if not candidates:
            return []
        opponent = 3 - player
        blocks: list[tuple[int, int]] = []
        rest: list[tuple[int, int]] = []
        for r, c in candidates:
            if self._wins_if(r, c, player):
                return [(r, c)]
            if self._wins_if(r, c, opponent):
                blocks.append((r, c))
            else:
                rest.append((r, c))
        if len(blocks) == 1:
            return blocks
        if len(blocks) > 1:
            return blocks

        if rich:
            rest.sort(key=lambda m: self._local_heuristic(m[0], m[1], player), reverse=True)
        else:
            rest.sort(
                key=lambda m: (self.history.get(m, 0), -_manhattan(m, focal)),
                reverse=True,
            )
        limit = _branch_limit(self.board_size)
        if len(rest) > limit:
            rest = rest[:limit]
        return rest

    def _nearby_empties(self, focal) -> list[tuple[int, int]]:
        n = self.board_size
        board = self.board
        if not self.stones:
            return [(n // 2, n // 2)]
        radius = 2
        found: set[tuple[int, int]] = set()
        for r, c in self.stones:
            r0 = r - radius if r - radius > 0 else 0
            c0 = c - radius if c - radius > 0 else 0
            r1 = r + radius if r + radius < n else n - 1
            c1 = c + radius if c + radius < n else n - 1
            for rr in range(r0, r1 + 1):
                row = board[rr]
                for cc in range(c0, c1 + 1):
                    if row[cc] == 0:
                        found.add((rr, cc))
        if not found:
            found = {
                (r, c)
                for r in range(n)
                for c in range(n)
                if board[r][c] == 0
            }
        ordered = list(found)
        if focal is not None:
            ordered.sort(key=lambda m: _manhattan(m, focal))
        return ordered

    def _wins_if(self, r: int, c: int, player: int) -> bool:
        self.board[r][c] = player
        won = self._is_win(r, c)
        self.board[r][c] = 0
        return won

    def _is_win(self, r: int, c: int) -> bool:
        board = self.board
        player = board[r][c]
        n = self.board_size
        k = self.win_length
        for dr, dc in _DIRS:
            count = 1
            rr, cc = r + dr, c + dc
            while 0 <= rr < n and 0 <= cc < n and board[rr][cc] == player:
                count += 1
                rr += dr
                cc += dc
            rr, cc = r - dr, c - dc
            while 0 <= rr < n and 0 <= cc < n and board[rr][cc] == player:
                count += 1
                rr -= dr
                cc -= dc
            if count >= k:
                return True
        return False

    def _local_heuristic(self, r: int, c: int, player: int) -> int:
        attack = self._imagine(r, c, player)
        block = self._imagine(r, c, 3 - player)
        mid = (self.board_size - 1) * 0.5
        center = 30 - int(8 * (abs(r - mid) + abs(c - mid)))
        return attack + block // 2 + center

    def _imagine(self, r: int, c: int, player: int) -> int:
        """假设 (r, c) 落子为 player，只看穿过该点的四条线，用于着法排序。"""
        board = self.board
        n = self.board_size
        k = self.win_length
        total = 0
        for dr, dc in _DIRS:
            length = 1
            opens = 0
            for sdr, sdc in ((dr, dc), (-dr, -dc)):
                rr, cc = r + sdr, c + sdc
                while 0 <= rr < n and 0 <= cc < n and board[rr][cc] == player:
                    length += 1
                    rr += sdr
                    cc += sdc
                if 0 <= rr < n and 0 <= cc < n and board[rr][cc] == 0:
                    opens += 1
            total += pattern_score(length, opens, k)
        return total

    def _evaluate(self) -> int:
        score = 0
        use_simple = self.eval_mode == "simple"
        for line in self.lines:
            score += self._score_line(line, use_simple)
        # 静态评估封顶，避免棋型分数被当成已经搜到的胜负。
        bound = 900_000
        if score > bound:
            return bound
        if score < -bound:
            return -bound
        return score

    def _score_line(self, cells: list[tuple[int, int]], simple: bool) -> int:
        board = self.board
        me = self.me
        k = self.win_length
        n = len(cells)
        score = 0
        i = 0
        while i < n:
            r, c = cells[i]
            player = board[r][c]
            if player == 0:
                i += 1
                continue
            j = i + 1
            while j < n and board[cells[j][0]][cells[j][1]] == player:
                j += 1
            length = j - i
            if simple:
                value = length * length
            else:
                left_open = i > 0 and board[cells[i - 1][0]][cells[i - 1][1]] == 0
                right_open = j < n and board[cells[j][0]][cells[j][1]] == 0
                value = pattern_score(length, int(left_open) + int(right_open), k)
            # 略偏向防守：同等棋型下，先处理对方的威胁。
            if player == me:
                score += value
            else:
                score -= value + value // 10
            i = j
        return score

    def _place(self, r: int, c: int, player: int) -> None:
        self.board[r][c] = player
        self.stones.append((r, c))
        self.empty -= 1

    def _undo(self, r: int, c: int) -> None:
        self.board[r][c] = 0
        self.stones.pop()
        self.empty += 1


def _default_max_depth(board_size: int) -> int:
    # 实际上限交给时限；这里只避免在分支突然变小时无限加深。
    if board_size <= 6:
        return 16
    if board_size <= 9:
        return 12
    return 10


def _branch_limit(board_size: int) -> int:
    if board_size <= 6:
        return 30
    if board_size <= 9:
        return 14
    return 12


def _build_lines(n: int) -> list[list[tuple[int, int]]]:
    lines: list[list[tuple[int, int]]] = []
    for r in range(n):
        lines.append([(r, c) for c in range(n)])
    for c in range(n):
        lines.append([(r, c) for r in range(n)])
    for c in range(n):
        lines.append(_ray(0, c, 1, 1, n))
        lines.append(_ray(0, c, 1, -1, n))
    for r in range(1, n):
        lines.append(_ray(r, 0, 1, 1, n))
        lines.append(_ray(r, n - 1, 1, -1, n))
    return [line for line in lines if len(line) >= 2]


def _ray(r: int, c: int, dr: int, dc: int, n: int) -> list[tuple[int, int]]:
    cells = []
    while 0 <= r < n and 0 <= c < n:
        cells.append((r, c))
        r += dr
        c += dc
    return cells


def _manhattan(cell, focal) -> int:
    if focal is None:
        return 0
    return abs(cell[0] - focal[0]) + abs(cell[1] - focal[1])


def _as_cell(move):
    if not move or len(move) != 2:
        return None
    try:
        return (int(move[0]), int(move[1]))
    except (TypeError, ValueError):
        return None


def _is_legal_move(board, move) -> bool:
    if not isinstance(move, tuple) or len(move) != 2:
        return False
    try:
        r, c = int(move[0]), int(move[1])
    except (TypeError, ValueError):
        return False
    n = len(board)
    return 0 <= r < n and 0 <= c < n and board[r][c] == 0


def _fallback_move(board):
    n = len(board)
    empties = [(r, c) for r in range(n) for c in range(n) if board[r][c] == 0]
    if not empties:
        return (0, 0)
    mid = (n - 1) / 2
    empties.sort(key=lambda rc: abs(rc[0] - mid) + abs(rc[1] - mid))
    return empties[0]
