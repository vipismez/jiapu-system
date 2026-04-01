#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""程序入口。"""

import tkinter as tk

from app import GenealogyApp
from storage import save_data


def main():
    root = tk.Tk()
    app = GenealogyApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (save_data(app.members), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
