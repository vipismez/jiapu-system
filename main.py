#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import uuid
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

DATA_FILE = Path("data.json")
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 760
NODE_WIDTH = 120
NODE_HEIGHT = 56
LAYER_HEIGHT = 130
HORIZONTAL_GAP = 36


@dataclass
class Person:
    id: str
    name: str
    gender: str
    birth: str = ""
    death: str = ""
    father: str | None = None
    mother: str | None = None
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
            "bio": self.bio,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            gender=data.get("gender", ""),
            birth=data.get("birth") or "",
            death=data.get("death") or "",
            father=data.get("father"),
            mother=data.get("mother"),
            bio=data.get("bio") or "",
        )


def save_data(members):
    raw = {"members": {member_id: member.to_dict() for member_id, member in members.items()}}
    DATA_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def build_sample_data():
    members = {}

    def add_person(person_id, name, gender, birth, death="", father=None, mother=None, bio=""):
        members[person_id] = Person(person_id, name, gender, birth, death, father, mother, bio)

    add_person("G1F", "赵先祖", "男", "1920-01-01", "1990-01-01", bio="第1代祖先")
    add_person("G1M", "王母祖", "女", "1925-02-02", "2000-02-02", bio="第1代祖先")

    previous_child = None
    for generation in range(2, 12):
        father_id = f"G{generation}F"
        mother_id = f"G{generation}M"
        child_id = f"G{generation}C"

        parent_father = previous_child or "G1F"
        parent_mother = f"G{generation - 1}M" if generation > 2 else "G1M"

        add_person(
            father_id,
            f"世{generation}富",
            "男",
            f"{1940 + generation}-03-03",
            father=parent_father,
            mother=parent_mother,
            bio=f"第{generation}代男性",
        )
        add_person(
            mother_id,
            f"世{generation}秀",
            "女",
            f"{1940 + generation}-04-04",
            bio=f"第{generation}代配偶",
        )
        add_person(
            child_id,
            f"世{generation}子",
            "男",
            f"{1960 + generation}-05-05",
            father=father_id,
            mother=mother_id,
            bio=f"第{generation}代子孙",
        )
        add_person(
            f"G{generation}S",
            f"世{generation}妹",
            "女",
            f"{1961 + generation}-08-08",
            father=father_id,
            mother=mother_id,
            bio=f"第{generation}代兄妹节点",
        )

        previous_child = child_id

    return members


def normalize_members(members):
    changed = False
    for person in members.values():
        if person.father == person.id:
            person.father = None
            changed = True
        if person.mother == person.id:
            person.mother = None
            changed = True
    return changed


def load_data():
    if DATA_FILE.exists():
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        members = {member_id: Person.from_dict(data) for member_id, data in raw.get("members", {}).items()}
        if members:
            changed = normalize_members(members)
            roots = [person for person in members.values() if not person.father and not person.mother]
            if changed:
                save_data(members)
            if roots:
                return members

    members = build_sample_data()
    save_data(members)
    return members


class GenealogyApp:
    MAX_LEVEL = 4

    def __init__(self, root):
        self.root = root
        self.root.title("家谱系统")
        self.root.geometry(f"{CANVAS_WIDTH}x{CANVAS_HEIGHT}")

        self.members = load_data()
        self.selected_member_id = None
        self.tooltip = None
        self.current_hover_id = None
        self.node_positions = {}
        self.scale_factor = 1.0

        roots = self.get_roots()
        if roots:
            self.selected_member_id = roots[0].id

        self.setup_ui()
        self.refresh_view()

    def setup_ui(self):
        container = ttk.Frame(self.root, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="添加新成员", command=self.open_member_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="刷新", command=self.refresh_view).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="重置中心", command=self.reset_center).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(container, bg="#f6f8fc", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_left_click)
        self.canvas.bind("<ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<B1-Motion>", self.on_pan_move)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", lambda event: self.zoom_at(event.x, event.y, 1.1))
        self.canvas.bind("<Button-5>", lambda event: self.zoom_at(event.x, event.y, 0.9))

    def refresh_view(self):
        self.render_graph_view()

    def get_roots(self):
        return [person for person in self.members.values() if not person.father and not person.mother]

    def get_children(self, person_id):
        unique_children = {}
        for person in self.members.values():
            if person.father == person_id or person.mother == person_id:
                unique_children[person.id] = person
        return list(unique_children.values())

    def get_siblings(self, person):
        if not person:
            return []
        return [
            member
            for member in self.members.values()
            if member.id != person.id
            and member.father == person.father
            and member.mother == person.mother
            and (person.father or person.mother)
        ]

    def get_ancestor_levels(self, person, max_level=3):
        levels = []
        current_level = [person]
        seen = {person.id}

        for _ in range(max_level):
            next_level = []
            for member in current_level:
                for parent_id in (member.father, member.mother):
                    if parent_id and parent_id in self.members and parent_id not in seen:
                        seen.add(parent_id)
                        next_level.append(self.members[parent_id])
            if not next_level:
                break
            levels.append(next_level)
            current_level = next_level

        return levels

    def get_descendant_levels(self, person, max_level=3):
        levels = []
        current_level = [person]
        seen = {person.id}

        for _ in range(max_level):
            next_level = []
            for member in current_level:
                for child in self.get_children(member.id):
                    if child.id not in seen:
                        seen.add(child.id)
                        next_level.append(child)
            if not next_level:
                break
            levels.append(next_level)
            current_level = next_level

        return levels

    def render_graph_view(self):
        root_person = self.members.get(self.selected_member_id)
        if root_person is None:
            roots = self.get_roots()
            if not roots:
                self.canvas.delete("all")
                self.canvas.create_text(
                    CANVAS_WIDTH / 2,
                    CANVAS_HEIGHT / 2,
                    text="当前暂无可视化成员",
                    font=(None, 16),
                    fill="#666666",
                )
                return
            root_person = roots[0]
            self.selected_member_id = root_person.id

        self.hide_tooltip()
        self.canvas.delete("all")
        self.node_positions = {}
        self.scale_factor = 1.0

        ancestor_levels = self.get_ancestor_levels(root_person, max_level=3)
        descendant_levels = self.get_descendant_levels(root_person, max_level=3)
        siblings = self.get_siblings(root_person)
        center_x = CANVAS_WIDTH / 2
        center_y = CANVAS_HEIGHT / 2

        for index, level in enumerate(reversed(ancestor_levels), start=1):
            y = center_y - LAYER_HEIGHT * index
            self.draw_level(level, y, "anc", center_person=root_person)

        self.draw_node(center_x, center_y, root_person, "center")

        if siblings:
            sibling_y = center_y
            self.draw_same_row_group(root_person, siblings, sibling_y)

        for index, level in enumerate(descendant_levels, start=1):
            y = center_y + LAYER_HEIGHT * index
            self.draw_level(level, y, "chd", center_person=root_person)

        self.draw_relationships(root_person, siblings)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def draw_level(self, members, y, prefix, center_person=None):
        if not members:
            return

        ordered_members = self.order_level_members(members, center_person)
        count = len(ordered_members)
        width = count * NODE_WIDTH + max(0, count - 1) * HORIZONTAL_GAP
        start_x = CANVAS_WIDTH / 2 - width / 2 + NODE_WIDTH / 2
        for index, person in enumerate(ordered_members):
            x = start_x + index * (NODE_WIDTH + HORIZONTAL_GAP)
            self.draw_node(x, y, person, prefix)

    def draw_same_row_group(self, center_person, siblings, y):
        ordered = self.order_level_members(siblings + [center_person], center_person)
        count = len(ordered)
        width = count * NODE_WIDTH + max(0, count - 1) * HORIZONTAL_GAP
        start_x = CANVAS_WIDTH / 2 - width / 2 + NODE_WIDTH / 2
        for index, person in enumerate(ordered):
            x = start_x + index * (NODE_WIDTH + HORIZONTAL_GAP)
            prefix = "center" if person.id == center_person.id else "sib"
            self.draw_node(x, y, person, prefix)

    def order_level_members(self, members, center_person=None):
        def sort_key(person):
            child_count = len(self.get_children(person.id))
            sibling_bonus = 0
            if center_person and (person.father == center_person.id or person.mother == center_person.id):
                sibling_bonus = -100
            return (
                sibling_bonus,
                0 if person.id == getattr(center_person, "id", None) else 1,
                -child_count,
                person.birth or "9999-99-99",
                person.name,
            )

        return sorted(members, key=sort_key)

    def draw_node(self, x, y, person, prefix):
        node_tag = f"node_{person.id}"
        is_center = person.id == self.selected_member_id
        fill_color = "#dbeafe" if is_center else "#ffffff"
        outline_color = "#1d4ed8" if is_center else "#3b82f6"
        text_color = "#0f172a" if is_center else "#111827"
        self.canvas.create_rectangle(
            x - NODE_WIDTH / 2,
            y - NODE_HEIGHT / 2,
            x + NODE_WIDTH / 2,
            y + NODE_HEIGHT / 2,
            fill=fill_color,
            outline=outline_color,
            width=2 if is_center else 1.4,
            tags=("graph", node_tag, f"{prefix}_{person.id}"),
        )
        self.canvas.create_text(
            x,
            y,
            text=f"{person.name}\n{person.gender}",
            font=(None, 10),
            fill=text_color,
            tags=("graph", node_tag, f"{prefix}_{person.id}"),
        )
        self.node_positions[person.id] = (x, y)

    def draw_relationships(self, center_person, siblings):
        drawn = set()

        def add_line(from_id, to_id, label):
            if from_id not in self.node_positions or to_id not in self.node_positions:
                return
            key = (from_id, to_id, label)
            if key in drawn:
                return
            drawn.add(key)

            x0, y0 = self.node_positions[from_id]
            x1, y1 = self.node_positions[to_id]
            self.canvas.create_line(
                x0,
                y0 + NODE_HEIGHT / 2 - 4,
                x1,
                y1 - NODE_HEIGHT / 2 + 4,
                arrow=tk.LAST,
                width=1.2,
                fill="#1f2937",
                tags=("graph",),
            )
            self.canvas.create_text(
                (x0 + x1) / 2,
                (y0 + y1) / 2 - 10,
                text=label,
                fill="#b91c1c",
                font=(None, 9),
                tags=("graph",),
            )

        for person_id, person in self.members.items():
            if person_id not in self.node_positions:
                continue
            if person.father:
                add_line(person.father, person_id, "父")
            if person.mother:
                add_line(person.mother, person_id, "母")

        for sibling in siblings:
            if sibling.id in self.node_positions and center_person.id in self.node_positions:
                x0, y0 = self.node_positions[center_person.id]
                x1, y1 = self.node_positions[sibling.id]
                self.canvas.create_line(x0, y0, x1, y1, dash=(3, 2), fill="#64748b", tags=("graph",))
                self.canvas.create_text((x0 + x1) / 2, y0 - 18, text="兄妹", fill="#b91c1c", font=(None, 9), tags=("graph",))

    def on_canvas_right_click(self, event):
        person_id = self.find_person_at(event.x, event.y)
        if not person_id or person_id not in self.members:
            return

        self.selected_member_id = person_id
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="设为中心显示", command=lambda: self.set_center(person_id))
        menu.add_command(label="编辑此人", command=lambda: self.open_member_dialog(role="edit", target_id=person_id))
        menu.add_command(label="删除此人", command=lambda: self.delete_member(person_id))
        menu.add_separator()
        menu.add_command(label="添加父亲", command=lambda: self.open_member_dialog(role="father", target_id=person_id))
        menu.add_command(label="添加母亲", command=lambda: self.open_member_dialog(role="mother", target_id=person_id))
        menu.add_command(label="添加子女", command=lambda: self.open_member_dialog(role="child", target_id=person_id))
        menu.post(event.x_root, event.y_root)

    def on_canvas_left_click(self, event):
        person_id = self.find_person_at(event.x, event.y)
        if not person_id or person_id not in self.members:
            return
        self.set_center(person_id)

    def find_person_at(self, x, y):
        for item in self.canvas.find_overlapping(x, y, x, y):
            for tag in self.canvas.gettags(item):
                if tag.startswith("node_"):
                    return tag.split("node_", 1)[1]
        return None

    def on_canvas_motion(self, event):
        person_id = self.find_person_at(event.x, event.y)
        if person_id and person_id in self.members:
            if self.current_hover_id != person_id:
                self.current_hover_id = person_id
                self.show_tooltip(person_id, event.x_root + 14, event.y_root + 14)
            return
        self.hide_tooltip()

    def on_canvas_leave(self, _event):
        self.hide_tooltip()

    def show_tooltip(self, person_id, screen_x, screen_y):
        self.hide_tooltip()
        person = self.members.get(person_id)
        if not person:
            return

        father_name = self.members[person.father].name if person.father and person.father in self.members else "未知"
        mother_name = self.members[person.mother].name if person.mother and person.mother in self.members else "未知"
        text = (
            f"姓名：{person.name}\n"
            f"性别：{person.gender}\n"
            f"生日：{person.birth or '未知'}\n"
            f"卒日：{person.death or '未去世'}\n"
            f"父亲：{father_name}\n"
            f"母亲：{mother_name}\n"
            f"生平：{person.bio or '无'}"
        )

        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{screen_x}+{screen_y}")
        label = tk.Label(
            self.tooltip,
            text=text,
            justify=tk.LEFT,
            background="#fff9db",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=4,
        )
        label.pack()

    def hide_tooltip(self):
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None
        self.current_hover_id = None

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def zoom_at(self, x, y, factor):
        self.canvas.scale("graph", x, y, factor, factor)
        self.scale_factor *= factor
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_at(event.x, event.y, factor)

    def set_center(self, member_id):
        self.selected_member_id = member_id
        self.refresh_view()

    def reset_center(self):
        roots = self.get_roots()
        self.selected_member_id = roots[0].id if roots else None
        self.refresh_view()

    def open_member_dialog(self, role=None, target_id=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑人物" if role == "edit" else "新增人物")
        dialog.grab_set()

        entries = {}
        fields = [
            ("姓名", "name"),
            ("性别", "gender"),
            ("生日", "birth"),
            ("卒日", "death"),
            ("生平简介", "bio"),
        ]

        for row, (label_text, key) in enumerate(fields):
            ttk.Label(dialog, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=6, pady=6)
            entry = ttk.Entry(dialog, width=40)
            entry.grid(row=row, column=1, padx=6, pady=6)
            entries[key] = entry

        if role == "edit" and target_id in self.members:
            person = self.members[target_id]
            entries["name"].insert(0, person.name)
            entries["gender"].insert(0, person.gender)
            entries["birth"].insert(0, person.birth)
            entries["death"].insert(0, person.death)
            entries["bio"].insert(0, person.bio)

        def on_submit():
            name = entries["name"].get().strip()
            gender = entries["gender"].get().strip()
            if not name or not gender:
                messagebox.showwarning("缺少必填", "姓名和性别为必填项目")
                return

            birth = entries["birth"].get().strip()
            death = entries["death"].get().strip()
            bio = entries["bio"].get().strip()

            if role == "edit" and target_id in self.members:
                person = self.members[target_id]
                person.name = name
                person.gender = gender
                person.birth = birth
                person.death = death
                person.bio = bio
            else:
                new_person = Person(str(uuid.uuid4()), name, gender, birth, death, bio=bio)
                self.attach_relationship(new_person, role, target_id)
                self.members[new_person.id] = new_person

            self.save_and_refresh()
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.grid(row=len(fields), column=0, columnspan=2, pady=(6, 10))
        ttk.Button(button_row, text="确认", command=on_submit).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    def attach_relationship(self, person, role, target_id):
        target = self.members.get(target_id)
        if role == "father" and target:
            target.father = person.id
        elif role == "mother" and target:
            target.mother = person.id
        elif role == "child" and target:
            if target.gender in ("男", "男性", "male"):
                person.father = target.id
                person.mother = target.mother
            elif target.gender in ("女", "女性", "female"):
                person.mother = target.id
                person.father = target.father
            else:
                person.father = target.father
                person.mother = target.mother

    def collect_descendants(self, person_id, collected):
        for child in self.get_children(person_id):
            if child.id not in collected:
                collected.add(child.id)
                self.collect_descendants(child.id, collected)

    def delete_member(self, person_id):
        if person_id not in self.members:
            return
        if not messagebox.askyesno("确认删除", "删除该人物会同时删除其所有子孙，确定吗？"):
            return

        to_delete = {person_id}
        self.collect_descendants(person_id, to_delete)

        for member_id in to_delete:
            self.members.pop(member_id, None)

        for person in self.members.values():
            if person.father in to_delete:
                person.father = None
            if person.mother in to_delete:
                person.mother = None

        if self.selected_member_id in to_delete:
            roots = self.get_roots()
            self.selected_member_id = roots[0].id if roots else None

        self.save_and_refresh()

    def save_and_refresh(self):
        save_data(self.members)
        self.refresh_view()


def main():
    root = tk.Tk()
    app = GenealogyApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (save_data(app.members), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
