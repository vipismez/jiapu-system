#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据模型与全局常量。"""

from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path("data.json")
GENDER_ICON_FILE = Path("assets/gender_icons.png")
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 760
NODE_WIDTH = 156
NODE_HEIGHT = 76
LAYER_HEIGHT = 168
HORIZONTAL_GAP = 50


@dataclass
class Person:
    """人物实体。

    说明：兄弟姐妹、子女关系不直接存储，通过 father/mother 反推。
    """
    id: str
    name: str
    gender: str
    birth: str = ""
    death: str = ""
    father: str | None = None
    mother: str | None = None
    spouses: list[str] = field(default_factory=list)
    bio: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "birth": self.birth,
            "death": self.death,
            "father": self.father,
            "mother": self.mother,
            "spouses": self.spouses,
            "bio": self.bio,
        }

    @classmethod
    def from_dict(cls, data):
        spouses = data.get("spouses")
        if not isinstance(spouses, list):
            # Backward compatibility with legacy single spouse field.
            spouse = data.get("spouse")
            spouses = [spouse] if spouse else []

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            gender=data.get("gender", ""),
            birth=data.get("birth") or "",
            death=data.get("death") or "",
            father=data.get("father"),
            mother=data.get("mother"),
            spouses=spouses,
            bio=data.get("bio") or "",
        )
