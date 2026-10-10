"""命令行入口：人人对战、人机对战、机机对战，以及本地实验。"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from gomoku_ai import GomokuAI
from gomoku_game import GomokuGame, format_board, load_gomoku_ai
from random_ai import GomokuAI as RandomAI


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="广义五子棋命令行")
    parser.add_argument("--mode", choices=("pvp", "pve", "eve"), default="pvp")
    parser.add_argument("--board", type=int, default=15, help="棋盘边长 N")
    parser.add_argument("--win", type=int, default=5, help="获胜连珠数 K")
    parser.add_argument("--time", type=float, default=5.0, help="每步时限（秒）")
    parser.add_argument("--human", type=int, choices=(1, 2), default=1, help="人机模式下人类执子")
    parser.add_argument("--ai1", default=str(Path(__file__).with_name("gomoku_ai.py")))
    parser.add_argument("--ai2", default=str(Path(__file__).with_name("random_ai.py")))
    parser.add_argument("--games", type=int, default=1, help="机机对战局数，偶数局交换先后手")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--bench", action="store_true", help="运行实验并打印汇总")
    args = parser.parse_args(argv)

    if args.win > args.board or args.board < 1 or args.win < 1:
        parser.error("需要满足 1 ≤ K ≤ N")
    if args.bench:
        run_bench()
        return
    if args.mode == "pvp":
        play_pvp(args.board, args.win)
    elif args.mode == "pve":
        play_pve(args.board, args.win, args.human, args.time)
    else:
        play_eve(args)


def play_pvp(n: int, k: int) -> None:
    game = GomokuGame(n, k)
    print(f"人人对战  N={n}  K={k}  黑棋 X 先手")
    while not game.is_over:
        print(format_board(game.board, game.last_move))
        print("黑方 X" if game.current == 1 else "白方 O", "落子")
        move = _read_human_move(game)
        game.place(*move)
    _announce(game)


def play_pve(n: int, k: int, human: int, time_limit: float) -> None:
    game = GomokuGame(n, k)
    ai = GomokuAI(3 - human, n, k)
    print(f"人机对战  N={n}  K={k}  人类执{'黑 X' if human == 1 else '白 O'}")
    while not game.is_over:
        print(format_board(game.board, game.last_move))
        if game.current == human:
            print("轮到你")
            move = _read_human_move(game)
        else:
            print("AI 思考中...")
            move = ai.get_move(game.clone_board(), game.last_move, time_limit)
            print(
                f"AI 落子 {move}  深度 {ai.last_depth}  "
                f"节点 {ai.last_nodes}  用时 {ai.last_time:.3f}s"
            )
        game.place(*move)
    print(format_board(game.board, game.last_move))
    _announce(game)


def play_eve(args) -> None:
    class_a = load_gomoku_ai(args.ai1)
    class_b = load_gomoku_ai(args.ai2)
    score_a = 0.0
    for index in range(args.games):
        if index % 2 == 0:
            black_cls, white_cls, a_is_black = class_a, class_b, True
        else:
            black_cls, white_cls, a_is_black = class_b, class_a, False
        result, moves, elapsed = play_ai_game(
            black_cls, white_cls, args.board, args.win, args.time, quiet=args.quiet
        )
        if result == 0:
            score_a += 0.5
            text = "和棋"
        elif (result == 1) == a_is_black:
            score_a += 1
            text = "AI1 胜"
        else:
            text = "AI2 胜"
        print(f"第 {index + 1} 局: {text}  步数 {moves}  用时 {elapsed:.1f}s")
    print(f"AI1 得分 {score_a} / {args.games}")


def play_ai_game(black_cls, white_cls, n, k, time_limit, quiet=True):
    game = GomokuGame(n, k)
    black = black_cls(1, n, k)
    white = white_cls(2, n, k)
    players = {1: black, 2: white}
    started = time.perf_counter()
    while not game.is_over:
        agent = players[game.current]
        board = game.clone_board()
        t0 = time.perf_counter()
        move = agent.get_move(board, game.last_move, time_limit)
        dt = time.perf_counter() - t0
        if board != game.board:
            raise RuntimeError("AI 修改了传入的棋盘")
        if not quiet:
            print(format_board(game.board, game.last_move))
            extra = ""
            if hasattr(agent, "last_depth"):
                extra = f"  depth {agent.last_depth} nodes {agent.last_nodes}"
            print(f"player {game.current} -> {move}  {dt:.3f}s{extra}")
        game.place(int(move[0]), int(move[1]))
    if not quiet:
        print(format_board(game.board, game.last_move))
        _announce(game)
    return game.winner, game.move_count, time.perf_counter() - started


def _read_human_move(game: GomokuGame) -> tuple[int, int]:
    while True:
        try:
            text = input("输入 行 列（从 0 开始），q 退出: ").strip()
        except EOFError:
            raise SystemExit(0) from None
        if text.lower() in {"q", "quit", "exit"}:
            raise SystemExit(0)
        parts = text.replace(",", " ").split()
        if len(parts) != 2:
            print("请输入两个整数")
            continue
        try:
            row, col = int(parts[0]), int(parts[1])
        except ValueError:
            print("请输入两个整数")
            continue
        if game.is_legal(row, col):
            return row, col
        print("这里不能落子")


def _announce(game: GomokuGame) -> None:
    if game.winner == 0:
        print("和棋")
    elif game.winner == 1:
        print("黑棋 X 获胜")
    else:
        print("白棋 O 获胜")


def run_bench() -> None:
    """本地实验：对随机 AI、自对战、两组 (N, K)、深度与评估函数对比。"""
    print("== 对 random，15x15 五连，每步 0.8s，各 10 局先后手 ==")
    _series(GomokuAI, RandomAI, 15, 5, 0.8, games=20, label="pattern")
    print("== 对 random，9x9 四连，每步 0.5s，各 10 局先后手 ==")
    _series(GomokuAI, RandomAI, 9, 4, 0.5, games=20, label="pattern-9")
    print("== 自对战，15x15 五连，每步 0.6s，8 局 ==")
    _self_play(15, 5, 0.6, games=8)
    print("== 深度 2 对 深度 4，11x11 五连，每步 1.0s，8 局 ==")
    _capped_match(2, 4, 11, 5, 1.0, games=8)
    print("== 棋型评估 对 简单评估，11x11 五连，每步 0.8s，8 局 ==")
    _eval_match(11, 5, 0.8, games=8)
    print("== 同一中盘局面在不同时限下的搜索规模 ==")
    _time_scale()


def _series(our_cls, opp_cls, n, k, time_limit, games, label):
    wins = losses = draws = 0
    lengths = []
    thinks = []
    depths = []

    class Timed:
        def __init__(self, player_id, board_size, win_length):
            self.agent = our_cls(player_id, board_size, win_length)

        def get_move(self, board, last_opponent_move, limit):
            t0 = time.perf_counter()
            move = self.agent.get_move(board, last_opponent_move, limit)
            thinks.append(time.perf_counter() - t0)
            depths.append(getattr(self.agent, "last_depth", 0))
            return move

    for index in range(games):
        random.seed(1000 + index)
        our_black = index % 2 == 0
        if our_black:
            result, length, _ = play_ai_game(Timed, opp_cls, n, k, time_limit)
            won = result == 1
            lost = result == 2
        else:
            result, length, _ = play_ai_game(opp_cls, Timed, n, k, time_limit)
            won = result == 2
            lost = result == 1
        lengths.append(length)
        if result == 0:
            draws += 1
        elif won:
            wins += 1
        elif lost:
            losses += 1
        print(
            f"  [{label}] {index + 1}/{games} result={result} len={length} black={our_black}",
            flush=True,
        )
    print(
        f"汇总 {label}: 胜 {wins} 负 {losses} 和 {draws} / {games}  "
        f"胜率 {wins / games:.1%}  平均步数 {sum(lengths) / len(lengths):.1f}  "
        f"平均每步 {sum(thinks) / len(thinks):.3f}s  平均深度 {sum(depths) / len(depths):.2f}"
    )


def _self_play(n, k, time_limit, games):
    lengths = []
    black_wins = white_wins = draws = 0
    thinks = []
    for index in range(games):
        random.seed(2000 + index)

        def factory(player_id, board_size, win_length, bucket=thinks):
            agent = GomokuAI(player_id, board_size, win_length)
            return _ThinkProxy(agent, bucket)

        result, length, _ = play_ai_game(factory, factory, n, k, time_limit)
        lengths.append(length)
        if result == 1:
            black_wins += 1
        elif result == 2:
            white_wins += 1
        else:
            draws += 1
        print(f"  [self] {index + 1}/{games} result={result} len={length}", flush=True)
    print(
        f"自对战: 黑胜 {black_wins} 白胜 {white_wins} 和 {draws}  "
        f"平均步数 {sum(lengths) / len(lengths):.1f}  "
        f"平均每步 {sum(thinks) / len(thinks):.3f}s"
    )


def _capped_match(depth_a, depth_b, n, k, time_limit, games):
    wins = {depth_a: 0, depth_b: 0}
    draws = 0
    for index in range(games):
        random.seed(3000 + index)
        a_black = index % 2 == 0
        black_depth = depth_a if a_black else depth_b
        white_depth = depth_b if a_black else depth_a

        def make(depth):
            def factory(player_id, board_size, win_length, cap=depth):
                agent = GomokuAI(player_id, board_size, win_length)
                agent.depth_cap = cap
                return agent

            return factory

        result, length, _ = play_ai_game(make(black_depth), make(white_depth), n, k, time_limit)
        if result == 0:
            draws += 1
        elif result == 1:
            wins[black_depth] += 1
        else:
            wins[white_depth] += 1
        print(f"  [depth] {index + 1}/{games} result={result} len={length}", flush=True)
    print(f"深度对比: {depth_a} 胜 {wins[depth_a]} ，{depth_b} 胜 {wins[depth_b]} ，和 {draws}")


def _eval_match(n, k, time_limit, games):
    pattern_wins = simple_wins = draws = 0
    for index in range(games):
        random.seed(4000 + index)
        pattern_black = index % 2 == 0

        def make(mode):
            def factory(player_id, board_size, win_length, eval_mode=mode):
                agent = GomokuAI(player_id, board_size, win_length)
                agent.eval_mode = eval_mode
                return agent

            return factory

        black_mode = "pattern" if pattern_black else "simple"
        white_mode = "simple" if pattern_black else "pattern"
        result, length, _ = play_ai_game(make(black_mode), make(white_mode), n, k, time_limit)
        if result == 0:
            draws += 1
        elif (result == 1 and pattern_black) or (result == 2 and not pattern_black):
            pattern_wins += 1
        else:
            simple_wins += 1
        print(f"  [eval] {index + 1}/{games} result={result} len={length}", flush=True)
    print(f"评估对比: 棋型评估胜 {pattern_wins} ，简单评估胜 {simple_wins} ，和 {draws}")


def _time_scale() -> None:
    n, k = 15, 5
    board = [[0 for _ in range(n)] for _ in range(n)]
    # 一个固定的中盘残局片段，双方各有连子，用来观察时限与深度的关系。
    stones = {
        (7, 7): 1,
        (7, 8): 2,
        (8, 7): 1,
        (6, 8): 2,
        (8, 8): 1,
        (8, 6): 2,
        (6, 6): 1,
        (9, 7): 2,
        (7, 6): 1,
        (9, 9): 2,
    }
    for (r, c), player in stones.items():
        board[r][c] = player
    for limit in (0.2, 0.5, 1.0, 2.0, 5.0):
        agent = GomokuAI(1, n, k)
        move = agent.get_move(board, (9, 9), limit)
        print(
            f"  limit {limit:.1f}s -> {move}  depth {agent.last_depth}  "
            f"nodes {agent.last_nodes}  time {agent.last_time:.3f}s"
        )


class _ThinkProxy:
    """记录被包装 AI 的实际墙钟时间。"""

    def __init__(self, agent, bucket):
        self.agent = agent
        self.bucket = bucket

    def get_move(self, board, last_opponent_move, time_limit):
        t0 = time.perf_counter()
        move = self.agent.get_move(board, last_opponent_move, time_limit)
        self.bucket.append(time.perf_counter() - t0)
        return move


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
