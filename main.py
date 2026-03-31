from __future__ import annotations

import tkinter as tk

from controller import create_controller


def main() -> None:
    root = tk.Tk()
    create_controller(root)
    root.mainloop()


if __name__ == "__main__":
    main()

