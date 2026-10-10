"""广义五子棋入口。

直接运行打开图形界面：
    python main.py

带参数则进入命令行，例如：
    python main.py --mode pve --board 15 --win 5
    python main.py --mode eve --ai2 random_ai.py --games 2
    python main.py --bench
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    if len(sys.argv) > 1:
        from main_cli import main as cli_main

        cli_main()
    else:
        from gui import main as gui_main

        gui_main()


if __name__ == "__main__":
    main()
