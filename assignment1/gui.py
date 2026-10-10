"""广义五子棋图形界面。三种模式都在同一窗口里开始。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from gomoku_ai import GomokuAI
from gomoku_game import GomokuGame
from random_ai import GomokuAI as RandomAI


class GomokuApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("广义五子棋")
        self.root.minsize(760, 640)
        self.game: GomokuGame | None = None
        self.agents: dict[int, object] = {}
        self.human_players: set[int] = set()
        self.thinking = False
        self.generation = 0
        self.hover: tuple[int, int] | None = None
        self.results: queue.Queue = queue.Queue()
        self._polling = False
        self._build()
        self.new_game()

    def _build(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        self.n_var = tk.IntVar(value=15)
        self.k_var = tk.IntVar(value=5)
        self.mode_var = tk.StringVar(value="pve")
        self.human_var = tk.StringVar(value="1")
        self.time_var = tk.DoubleVar(value=2.0)
        self.opponent_var = tk.StringVar(value="random")

        ttk.Label(bar, text="棋盘 N").pack(side=tk.LEFT)
        n_box = ttk.Spinbox(bar, from_=5, to=15, textvariable=self.n_var, width=4, command=self._sync_k)
        n_box.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(bar, text="连珠 K").pack(side=tk.LEFT)
        self.k_box = ttk.Spinbox(bar, from_=3, to=15, textvariable=self.k_var, width=4)
        self.k_box.pack(side=tk.LEFT, padx=(2, 8))

        ttk.Radiobutton(bar, text="人人", value="pvp", variable=self.mode_var).pack(side=tk.LEFT)
        ttk.Radiobutton(bar, text="人机", value="pve", variable=self.mode_var).pack(side=tk.LEFT)
        ttk.Radiobutton(bar, text="机机", value="eve", variable=self.mode_var).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(bar, text="我执").pack(side=tk.LEFT)
        ttk.Combobox(bar, textvariable=self.human_var, values=("1", "2"), width=3, state="readonly").pack(
            side=tk.LEFT, padx=(2, 8)
        )
        ttk.Label(bar, text="时限").pack(side=tk.LEFT)
        ttk.Spinbox(bar, from_=0.2, to=10, increment=0.2, textvariable=self.time_var, width=5).pack(
            side=tk.LEFT, padx=(2, 8)
        )
        ttk.Label(bar, text="机机对手").pack(side=tk.LEFT)
        ttk.Combobox(
            bar,
            textvariable=self.opponent_var,
            values=("random", "self"),
            width=8,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(bar, text="开始新局", command=self.new_game).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status, padding=(8, 0, 8, 8)).pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(self.root, bg="#e4b56a", highlightthickness=0)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(None))
        self.canvas.bind("<Configure>", lambda _e: self._draw())

    def _sync_k(self) -> None:
        try:
            n = int(self.n_var.get())
            k = int(self.k_var.get())
        except (tk.TclError, ValueError):
            return
        if k > n:
            self.k_var.set(n)

    def new_game(self) -> None:
        try:
            n = int(self.n_var.get())
            k = int(self.k_var.get())
            time_limit = float(self.time_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("参数错误", "N、K 和时限需要是数字")
            return
        if not 5 <= n <= 15 or not 3 <= k <= n or time_limit <= 0:
            messagebox.showerror("参数错误", "需要 5 ≤ N ≤ 15，3 ≤ K ≤ N，且时限为正数")
            return
        self.generation += 1
        self.thinking = False
        while True:
            try:
                self.results.get_nowait()
            except queue.Empty:
                break
        self.hover = None
        self.game = GomokuGame(n, k)
        mode = self.mode_var.get()
        human = int(self.human_var.get())
        self.agents = {}
        self.human_players = set()
        try:
            if mode == "pvp":
                self.human_players = {1, 2}
            elif mode == "pve":
                self.human_players = {human}
                self.agents[3 - human] = GomokuAI(3 - human, n, k)
            else:
                second = RandomAI if self.opponent_var.get() == "random" else GomokuAI
                self.agents[1] = GomokuAI(1, n, k)
                self.agents[2] = second(2, n, k)
        except Exception as exc:
            messagebox.showerror("AI 加载失败", str(exc))
            return
        self._draw()
        self._refresh_status()
        self._maybe_ai()

    def _on_click(self, event) -> None:
        if self.game is None or self.game.is_over or self.thinking:
            return
        if self.game.current not in self.human_players:
            return
        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return
        row, col = cell
        if not self.game.is_legal(row, col):
            return
        self.game.place(row, col)
        self._draw()
        self._refresh_status()
        self._maybe_ai()

    def _on_motion(self, event) -> None:
        self._set_hover(self._cell_at(event.x, event.y))

    def _set_hover(self, cell) -> None:
        if cell == self.hover:
            return
        self.hover = cell
        self._draw()

    def _maybe_ai(self) -> None:
        game = self.game
        if game is None or game.is_over:
            return
        if game.current in self.human_players:
            return
        agent = self.agents[game.current]
        board = game.clone_board()
        last = game.last_move
        limit = float(self.time_var.get())
        generation = self.generation
        self.thinking = True
        self.status.set(self.status.get() + "  思考中...")

        def work():
            error = None
            move = None
            try:
                move = agent.get_move(board, last, limit)
            except Exception as exc:
                error = exc
            self.results.put((generation, agent, move, error))

        threading.Thread(target=work, daemon=True).start()
        self._schedule_poll()

    def _schedule_poll(self) -> None:
        if self._polling:
            return
        self._polling = True
        self.root.after(30, self._poll)

    def _poll(self) -> None:
        self._polling = False
        pending = []
        while True:
            try:
                pending.append(self.results.get_nowait())
            except queue.Empty:
                break
        for item in pending:
            self._apply_ai(*item)
        if self.thinking and not self._polling:
            self._schedule_poll()

    def _apply_ai(self, generation, agent, move, error) -> None:
        if generation != self.generation or self.game is None:
            return
        self.thinking = False
        if error is not None or move is None or not self.game.is_legal(move[0], move[1]):
            reason = "运行异常" if error is not None else f"非法落子 {move}"
            self.game.winner = 3 - self.game.current
            self.status.set(f"AI 判负：{reason}")
            self._draw()
            return
        self.game.place(move[0], move[1])
        depth = getattr(agent, "last_depth", None)
        used = getattr(agent, "last_time", None)
        note = ""
        if depth:
            note = f"  深度 {depth}"
        if used is not None:
            note += f"  {used:.2f}s"
        self._draw()
        self._refresh_status(note)
        self._maybe_ai()

    def _refresh_status(self, extra: str = "") -> None:
        game = self.game
        if game is None:
            return
        if game.winner == 0:
            text = "和棋"
        elif game.winner in (1, 2):
            name = "黑棋" if game.winner == 1 else "白棋"
            text = f"{name}获胜"
        else:
            name = "黑棋" if game.current == 1 else "白棋"
            who = "你" if game.current in self.human_players else "AI"
            text = f"轮到{name}（{who}）"
        self.status.set(
            f"N={game.board_size}  K={game.win_length}  {text}  "
            f"已下 {game.move_count} 手{extra}"
        )

    def _geometry(self):
        game = self.game
        n = game.board_size if game else 15
        width = max(self.canvas.winfo_width(), 640)
        height = max(self.canvas.winfo_height(), 560)
        margin = 36
        span = min(width, height) - margin * 2
        cell = span / n
        origin_x = (width - cell * n) / 2
        origin_y = (height - cell * n) / 2
        return n, cell, origin_x, origin_y

    def _cell_at(self, x, y):
        if self.game is None:
            return None
        n, cell, ox, oy = self._geometry()
        col = int((x - ox) / cell)
        row = int((y - oy) / cell)
        if 0 <= row < n and 0 <= col < n:
            return row, col
        return None

    def _draw(self) -> None:
        self.canvas.delete("all")
        game = self.game
        if game is None:
            return
        n, cell, ox, oy = self._geometry()
        x0, y0 = ox, oy
        x1, y1 = ox + cell * n, oy + cell * n
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#e8c27a", outline="")
        for i in range(n + 1):
            self.canvas.create_line(x0 + i * cell, y0, x0 + i * cell, y1, fill="#6b4423")
            self.canvas.create_line(x0, y0 + i * cell, x1, y0 + i * cell, fill="#6b4423")
        for i in range(n):
            self.canvas.create_text(x0 - 14, y0 + (i + 0.5) * cell, text=str(i), fill="#3d2914", font=("Consolas", 9))
            self.canvas.create_text(x0 + (i + 0.5) * cell, y0 - 14, text=str(i), fill="#3d2914", font=("Consolas", 9))

        if (
            self.hover
            and not game.is_over
            and not self.thinking
            and game.current in self.human_players
            and game.is_legal(*self.hover)
        ):
            r, c = self.hover
            self._stone(ox, oy, cell, r, c, "#f3e2b8", "")

        win = set(game.win_cells)
        for r in range(n):
            for c in range(n):
                player = game.board[r][c]
                if player == 0:
                    continue
                color = "#1c1c1c" if player == 1 else "#f7f4ee"
                outline = "#c0392b" if (r, c) in win else "#333333"
                self._stone(ox, oy, cell, r, c, color, outline)
        if game.last_move and game.board[game.last_move[0]][game.last_move[1]] != 0:
            r, c = game.last_move
            cx = ox + (c + 0.5) * cell
            cy = oy + (r + 0.5) * cell
            rad = max(3, cell * 0.08)
            mark = "#e74c3c" if game.board[r][c] == 1 else "#c0392b"
            self.canvas.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=mark, outline="")

    def _stone(self, ox, oy, cell, r, c, fill, outline) -> None:
        pad = cell * 0.12
        x0 = ox + c * cell + pad
        y0 = oy + r * cell + pad
        x1 = ox + (c + 1) * cell - pad
        y1 = oy + (r + 1) * cell - pad
        self.canvas.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=2)


def main() -> None:
    root = tk.Tk()
    GomokuApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
