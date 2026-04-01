#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

DATA_FILE = Path("data.json")


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"members": {}, "relationships": []}


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    data = load_data()
    print("欢迎使用 家谱系统")
    print(f"当前成员数：{len(data['members'])}")
    print("请在后续开发中补充交互功能。")


if __name__ == '__main__':
    main()
