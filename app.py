#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tkinter 家谱应用主界面与交互逻辑。"""

import uuid
import tkinter as tk
from tkinter import messagebox, ttk

from model import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GENDER_ICON_FILE,
    HORIZONTAL_GAP,
    LAYER_HEIGHT,
    NODE_HEIGHT,
    NODE_WIDTH,
    Person,
)
from storage import load_data, save_data

class GenealogyApp:
    """家谱桌面应用主类，负责 UI、关系计算与数据读写。"""
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
        self._dragging = False
        self._press_x = 0
        self._press_y = 0
        self._drag_node_id = None
        self._pan_mode = False
        self._current_center_person = None
        self._current_siblings = []
        self._current_spouse = None
        self.relation_items = {}
        self.gender_avatars = {}

        roots = self.get_roots()
        if roots:
            self.selected_member_id = roots[0].id

        self.setup_ui()
        self.load_gender_avatars()
        self.refresh_view()

    def load_gender_avatars(self):
        self.gender_avatars = {}
        if not GENDER_ICON_FILE.exists():
            return

        try:
            source = tk.PhotoImage(file=str(GENDER_ICON_FILE))
            width = source.width()
            height = source.height()
            if width <= 2 or height <= 0:
                return

            mid = width // 2
            split_gap = 4
            male_right = max(1, mid - split_gap)
            female_left = min(width - 1, mid + split_gap)

            male_raw = tk.PhotoImage()
            male_raw.tk.call(male_raw, "copy", source, "-from", 0, 0, male_right, height)
            female_raw = tk.PhotoImage()
            female_raw.tk.call(female_raw, "copy", source, "-from", female_left, 0, width, height)

            # Resize to fit node corner area.
            male_target_width = 26
            male_target_height = 26
            sample_x = max(1, male_raw.width() // male_target_width)
            sample_y = max(1, male_raw.height() // male_target_height)

            male_icon = male_raw.subsample(sample_x, sample_y)
            female_icon = female_raw.subsample(sample_x, sample_y)

            # Keep references to avoid Tk image garbage collection.
            self._gender_icon_source = source
            self._gender_icon_male_raw = male_raw
            self._gender_icon_female_raw = female_raw
            self.gender_avatars = {
                "男": male_icon,
                "女": female_icon,
                "未知": male_icon,
            }
        except tk.TclError:
            self.gender_avatars = {}

    def setup_ui(self):
        container = ttk.Frame(self.root, padding=8)
        container.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="添加新成员", command=self.open_member_dialog).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="刷新", command=self.refresh_view).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="重置中心", command=self.reset_center).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="搜索人物", command=self.open_search_dialog).pack(side=tk.LEFT, padx=(0, 6))

        self.canvas = tk.Canvas(container, bg="#f6f8fc", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_left_click)
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
        """按当前中心人物重绘可视化画布。"""
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

        father = self.members.get(root_person.father) if root_person.father in self.members else None
        mother = self.members.get(root_person.mother) if root_person.mother in self.members else None
        spouses = [self.members[sid] for sid in root_person.spouses if sid in self.members and sid != root_person.id]
        siblings = self.get_siblings(root_person)
        children = self.get_children(root_person.id)

        center_x = CANVAS_WIDTH / 2
        center_y = CANVAS_HEIGHT / 2

        # 上层：父母
        parent_nodes = [p for p in (father, mother) if p is not None]
        if parent_nodes:
            parent_y = center_y - LAYER_HEIGHT
            parent_count = len(parent_nodes)
            parent_width = parent_count * NODE_WIDTH + max(0, parent_count - 1) * HORIZONTAL_GAP
            parent_start_x = center_x - parent_width / 2 + NODE_WIDTH / 2
            for index, person in enumerate(parent_nodes):
                px = parent_start_x + index * (NODE_WIDTH + HORIZONTAL_GAP)
                self.draw_node(px, parent_y, person, "anc")

        # 中层：兄弟姐妹 + 本人 + 配偶（按顺序横向排布）
        same_row = siblings + [root_person]
        same_row.extend(spouses)

        same_row = self.order_level_members(same_row, center_person=root_person)
        row_count = len(same_row)
        row_width = row_count * NODE_WIDTH + max(0, row_count - 1) * HORIZONTAL_GAP
        row_start_x = center_x - row_width / 2 + NODE_WIDTH / 2
        for index, person in enumerate(same_row):
            px = row_start_x + index * (NODE_WIDTH + HORIZONTAL_GAP)
            prefix = "center" if person.id == root_person.id else "sib"
            if person.id in {s.id for s in spouses}:
                prefix = "spouse"
            self.draw_node(px, center_y, person, prefix)

        # 下层：子女
        if children:
            child_y = center_y + LAYER_HEIGHT
            ordered_children = self.order_level_members(children, center_person=root_person)
            child_count = len(ordered_children)
            child_width = child_count * NODE_WIDTH + max(0, child_count - 1) * HORIZONTAL_GAP
            child_start_x = center_x - child_width / 2 + NODE_WIDTH / 2
            for index, person in enumerate(ordered_children):
                px = child_start_x + index * (NODE_WIDTH + HORIZONTAL_GAP)
                self.draw_node(px, child_y, person, "chd")

        self._current_center_person = root_person
        self._current_siblings = siblings
        self._current_spouse = spouses
        self.draw_relationships(root_person, siblings, spouses)
        self.draw_legend()
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
        """同层节点排序：中心优先、后代多者优先、再按出生日期与姓名。"""
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
            y + 6,
            text=person.name,
            font=(None, 12),
            fill=text_color,
            tags=("graph", node_tag, f"{prefix}_{person.id}"),
        )
        self.draw_gender_avatar(x - NODE_WIDTH / 2 + 20, y - NODE_HEIGHT / 2 + 18, person.gender, node_tag, prefix)
        self.node_positions[person.id] = (x, y)

    def draw_gender_avatar(self, x, y, gender, node_tag, prefix):
        image = self.gender_avatars.get(gender)
        if image is not None:
            self.canvas.create_image(
                x,
                y,
                image=image,
                anchor=tk.CENTER,
                tags=("graph", node_tag, f"{prefix}_avatar"),
            )
            return

        if gender == "男":
            avatar_bg = "#2563eb"
            ring_color = "#1e40af"
        elif gender == "女":
            avatar_bg = "#db2777"
            ring_color = "#9d174d"
        else:
            avatar_bg = "#64748b"
            ring_color = "#334155"

        # Badge avatar style: round background + clean white profile glyph.
        self.canvas.create_oval(
            x - 10,
            y - 10,
            x + 10,
            y + 10,
            fill=avatar_bg,
            outline=ring_color,
            width=1.5,
            tags=("graph", node_tag, f"{prefix}_avatar"),
        )

        # Head
        self.canvas.create_oval(
            x - 3,
            y - 6,
            x + 3,
            y,
            fill="#ffffff",
            outline="#ffffff",
            width=1,
            tags=("graph", node_tag, f"{prefix}_avatar"),
        )

        # Shoulders / torso curve
        self.canvas.create_arc(
            x - 6,
            y - 1,
            x + 6,
            y + 9,
            start=0,
            extent=180,
            style=tk.ARC,
            outline="#ffffff",
            width=2,
            tags=("graph", node_tag, f"{prefix}_avatar"),
        )

        # Subtle highlight for better depth
        self.canvas.create_rectangle(
            x - 6,
            y - 9,
            x + 1,
            y - 7,
            fill="#ffffff",
            outline="#ffffff",
            width=0,
            tags=("graph", node_tag, f"{prefix}_avatar"),
        )

    def draw_relationships(self, center_person, siblings, spouses=None):
        """绘制当前可见节点之间的关系线，并记录线条元数据。"""
        # Clear previous relationship edges/labels to avoid ghosting during drag.
        self.canvas.delete("relation")
        self.relation_items = {}
        drawn = set()

        def add_parent_child_line(from_id, to_id):
            if from_id not in self.node_positions or to_id not in self.node_positions:
                return
            key = (from_id, to_id, "pc")
            if key in drawn:
                return
            drawn.add(key)

            x0, y0 = self.node_positions[from_id]
            x1, y1 = self.node_positions[to_id]
            line_id = self.canvas.create_line(
                x0,
                y0 + NODE_HEIGHT / 2 - 4,
                x1,
                y1 - NODE_HEIGHT / 2 + 4,
                arrow=tk.LAST,
                width=3,
                fill="#dc2626",
                tags=("graph", "relation"),
            )
            self.relation_items[line_id] = ("pc", from_id, to_id)

        for person_id, person in self.members.items():
            if person_id not in self.node_positions:
                continue
            if person.father:
                add_parent_child_line(person.father, person_id)
            if person.mother:
                add_parent_child_line(person.mother, person_id)

        for sibling in siblings:
            if sibling.id in self.node_positions and center_person.id in self.node_positions:
                x0, y0 = self.node_positions[center_person.id]
                x1, y1 = self.node_positions[sibling.id]
                line_id = self.canvas.create_line(
                    x0,
                    y0,
                    x1,
                    y1,
                    width=3,
                    fill="#facc15",
                    tags=("graph", "relation"),
                )
                self.relation_items[line_id] = ("sib", center_person.id, sibling.id)

        for spouse in (spouses or []):
            if spouse.id in self.node_positions and center_person.id in self.node_positions:
                x0, y0 = self.node_positions[center_person.id]
                x1, y1 = self.node_positions[spouse.id]
                line_id = self.canvas.create_line(
                    x0,
                    y0 + 8,
                    x1,
                    y1 + 8,
                    dash=(8, 4),
                    width=3,
                    fill="#2563eb",
                    tags=("graph", "relation"),
                )
                self.relation_items[line_id] = ("spouse", center_person.id, spouse.id)

    def draw_legend(self):
        # Legend for relation styles in the top-left corner.
        x0 = 18
        y0 = 16
        width = 250
        height = 120
        self.canvas.create_rectangle(
            x0,
            y0,
            x0 + width,
            y0 + height,
            fill="#ffffff",
            outline="#cbd5e1",
            width=1,
            tags=("graph", "legend"),
        )
        self.canvas.create_text(
            x0 + 10,
            y0 + 14,
            text="线条图例",
            anchor=tk.W,
            fill="#334155",
            font=(None, 10, "bold"),
            tags=("graph", "legend"),
        )

        rows = [
            ("父母/子女", "#dc2626", False, True),
            ("配偶", "#2563eb", True, False),
            ("兄弟姐妹", "#facc15", False, False),
        ]

        start_y = y0 + 36
        for idx, (label, color, dashed, arrowed) in enumerate(rows):
            y = start_y + idx * 26
            kwargs = {
                "fill": color,
                "width": 3,
                "tags": ("graph", "legend"),
            }
            if dashed:
                kwargs["dash"] = (8, 4)
            if arrowed:
                kwargs["arrow"] = tk.LAST

            self.canvas.create_line(x0 + 12, y, x0 + 72, y, **kwargs)
            self.canvas.create_text(
                x0 + 82,
                y,
                text=label,
                anchor=tk.W,
                fill="#0f172a",
                font=(None, 9),
                tags=("graph", "legend"),
            )

    def on_canvas_right_click(self, event):
        """右键菜单：命中人物弹人物菜单，命中关系线弹删除关系菜单。"""
        person_id = self.find_person_at(event.x, event.y)
        if person_id and person_id in self.members:
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
            return

        relation_info = self.find_relation_at(event.x, event.y)
        if not relation_info:
            return

        rel_type, from_id, to_id = relation_info
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label="删除该关系",
            command=lambda: self.delete_relation(rel_type, from_id, to_id),
        )
        menu.post(event.x_root, event.y_root)

    def on_canvas_left_click(self, event):
        if self._dragging:
            return
        person_id = self.find_person_at(event.x, event.y)
        if not person_id or person_id not in self.members:
            return
        self.set_center(person_id)

    def on_left_press(self, event):
        self._dragging = False
        self._press_x = event.x
        self._press_y = event.y

        person_id = self.find_person_at(event.x, event.y)
        if person_id and person_id in self.members:
            self._drag_node_id = person_id
            self._pan_mode = False
        else:
            self._drag_node_id = None
            self._pan_mode = False

    def on_left_motion(self, event):
        if self._drag_node_id:
            dx = event.x - self._press_x
            dy = event.y - self._press_y
            if dx == 0 and dy == 0:
                return

            if abs(dx) > 1 or abs(dy) > 1:
                self._dragging = True

            self.canvas.move(f"node_{self._drag_node_id}", dx, dy)
            x, y = self.node_positions.get(self._drag_node_id, (0, 0))
            self.node_positions[self._drag_node_id] = (x + dx, y + dy)
            self._press_x = event.x
            self._press_y = event.y

            if self._current_center_person is not None:
                self.draw_relationships(self._current_center_person, self._current_siblings, self._current_spouse)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return

        # Background panning is intentionally disabled.

    def on_left_release(self, event):
        if self._dragging:
            self._drag_node_id = None
            self._pan_mode = False
            return

        person_id = self.find_person_at(event.x, event.y)
        if person_id and person_id in self.members:
            self.current_hover_id = person_id
            self.show_tooltip(person_id, event.x_root + 14, event.y_root + 14)
        else:
            self.hide_tooltip()

        self._drag_node_id = None
        self._pan_mode = False

    def find_person_at(self, x, y):
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        for item in self.canvas.find_overlapping(cx, cy, cx, cy):
            for tag in self.canvas.gettags(item):
                if tag.startswith("node_"):
                    return tag.split("node_", 1)[1]
        return None

    def find_relation_at(self, x, y):
        """返回点击位置对应的关系线元信息。"""
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        for item in reversed(self.canvas.find_overlapping(cx, cy, cx, cy)):
            if item in self.relation_items:
                return self.relation_items[item]
        return None

    def delete_relation(self, rel_type, from_id, to_id):
        """删除指定关系线对应的真实关系数据。"""
        from_person = self.members.get(from_id)
        to_person = self.members.get(to_id)

        if rel_type == "pc":
            relation_label = "父母/子女"
        elif rel_type == "spouse":
            relation_label = "配偶"
        elif rel_type == "sib":
            relation_label = "兄弟姐妹"
        else:
            relation_label = "关系"

        from_name = from_person.name if from_person else "未知"
        to_name = to_person.name if to_person else "未知"
        if not messagebox.askyesno(
            "确认删除关系",
            f"确定要删除【{from_name}】与【{to_name}】的【{relation_label}】关系吗？",
        ):
            return

        changed = False

        if rel_type == "pc":
            child = self.members.get(to_id)
            if child is None:
                return
            if child.father == from_id:
                child.father = None
                changed = True
            if child.mother == from_id:
                child.mother = None
                changed = True

        elif rel_type == "spouse":
            left = self.members.get(from_id)
            right = self.members.get(to_id)
            if left is None or right is None:
                return
            if to_id in left.spouses:
                left.spouses.remove(to_id)
                changed = True
            if from_id in right.spouses:
                right.spouses.remove(from_id)
                changed = True

        elif rel_type == "sib":
            left = self.members.get(from_id)
            right = self.members.get(to_id)
            if left is None or right is None:
                return

            # Sibling relation is derived from shared parents; break shared links on one side.
            if left.father and right.father == left.father:
                right.father = None
                changed = True
            if left.mother and right.mother == left.mother:
                right.mother = None
                changed = True

        if not changed:
            return

        self.save_and_refresh()

    def on_canvas_motion(self, event):
        if self.current_hover_id is None:
            return

        person_id = self.find_person_at(event.x, event.y)
        if person_id != self.current_hover_id:
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
        spouse_names = [self.members[sid].name for sid in person.spouses if sid in self.members]
        text = (
            f"姓名：{person.name}\n"
            f"性别：{person.gender}\n"
            f"生日：{person.birth or '未知'}\n"
            f"卒日：{person.death or '未去世'}\n"
            f"父亲：{father_name}\n"
            f"母亲：{mother_name}\n"
            f"配偶：{', '.join(spouse_names) if spouse_names else '无'}\n"
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

    def zoom_at(self, x, y, factor):
        cx = self.canvas.canvasx(x)
        cy = self.canvas.canvasy(y)
        self.canvas.scale("graph", cx, cy, factor, factor)
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

    def person_option(self, person_id):
        person = self.members.get(person_id)
        if not person:
            return person_id
        return f"{person.name} ({person.gender}) | {person_id}"

    def resolve_person_id(self, value):
        value = (value or "").strip()
        if not value:
            return None
        if value in self.members:
            return value
        if "|" in value:
            possible_id = value.split("|")[-1].strip()
            if possible_id in self.members:
                return possible_id
        return None

    def add_spouse_link(self, person_id, spouse_id):
        if not person_id or not spouse_id:
            return
        if person_id == spouse_id:
            return
        if person_id not in self.members or spouse_id not in self.members:
            return

        if spouse_id not in self.members[person_id].spouses:
            self.members[person_id].spouses.append(spouse_id)
        if person_id not in self.members[spouse_id].spouses:
            self.members[spouse_id].spouses.append(person_id)

    def set_spouse_links(self, person_id, spouse_ids):
        if person_id not in self.members:
            return
        current = set(self.members[person_id].spouses)
        target = {sid for sid in spouse_ids if sid in self.members and sid != person_id}

        for sid in list(current - target):
            if sid in self.members and person_id in self.members[sid].spouses:
                self.members[sid].spouses.remove(person_id)

        self.members[person_id].spouses = []
        for sid in target:
            self.add_spouse_link(person_id, sid)

    def get_primary_spouse_id(self, person):
        for sid in person.spouses:
            if sid in self.members:
                return sid
        return None

    def apply_sibling_links(self, person_id, sibling_ids):
        if person_id not in self.members:
            return
        person = self.members[person_id]
        for sid in sibling_ids:
            if sid == person_id or sid not in self.members:
                continue
            sibling = self.members[sid]

            if person.father and not sibling.father:
                sibling.father = person.father
            if person.mother and not sibling.mother:
                sibling.mother = person.mother
            if sibling.father and not person.father:
                person.father = sibling.father
            if sibling.mother and not person.mother:
                person.mother = sibling.mother

    def open_search_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("搜索人物")
        dialog.geometry("700x520")
        dialog.grab_set()

        # --- Filter area ---
        filter_frame = ttk.LabelFrame(dialog, text="筛选条件", padding=8)
        filter_frame.pack(fill=tk.X, padx=8, pady=8)

        row0 = ttk.Frame(filter_frame)
        row0.pack(fill=tk.X, pady=2)
        ttk.Label(row0, text="姓名：", width=9).pack(side=tk.LEFT)
        name_var = tk.StringVar()
        ttk.Entry(row0, textvariable=name_var, width=18).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row0, text="性别：", width=6).pack(side=tk.LEFT)
        gender_var = tk.StringVar(value="全部")
        ttk.Combobox(row0, textvariable=gender_var, values=["全部", "男", "女"], state="readonly", width=8).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row0, text="出生年代：", width=9).pack(side=tk.LEFT)
        birth_var = tk.StringVar()
        ttk.Entry(row0, textvariable=birth_var, width=12).pack(side=tk.LEFT)
        ttk.Label(row0, text="（如：1950、195）", foreground="#888", font=(None, 8)).pack(side=tk.LEFT)

        row1 = ttk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="配偶姓名：", width=9).pack(side=tk.LEFT)
        spouse_var = tk.StringVar()
        ttk.Entry(row1, textvariable=spouse_var, width=18).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row1, text="子女姓名：", width=9).pack(side=tk.LEFT)
        child_var = tk.StringVar()
        ttk.Entry(row1, textvariable=child_var, width=18).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row1, text="兄妹姓名：", width=9).pack(side=tk.LEFT)
        sibling_var = tk.StringVar()
        ttk.Entry(row1, textvariable=sibling_var, width=18).pack(side=tk.LEFT)

        # --- Results area ---
        result_frame = ttk.LabelFrame(dialog, text="搜索结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        columns = ("name", "gender", "birth", "spouse", "children", "siblings")
        tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=14)
        tree.heading("name", text="姓名")
        tree.heading("gender", text="性别")
        tree.heading("birth", text="出生日期")
        tree.heading("spouse", text="配偶")
        tree.heading("children", text="子女")
        tree.heading("siblings", text="兄妹")
        tree.column("name", width=80, anchor=tk.CENTER)
        tree.column("gender", width=48, anchor=tk.CENTER)
        tree.column("birth", width=100, anchor=tk.CENTER)
        tree.column("spouse", width=130)
        tree.column("children", width=130)
        tree.column("siblings", width=130)

        vsb = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        _row_person_map = {}

        def do_search(*_args):
            for item in tree.get_children():
                tree.delete(item)
            _row_person_map.clear()

            name_term = name_var.get().strip().lower()
            gender_filter = gender_var.get()
            birth_term = birth_var.get().strip()
            spouse_term = spouse_var.get().strip().lower()
            child_term = child_var.get().strip().lower()
            sibling_term = sibling_var.get().strip().lower()

            for person in sorted(self.members.values(), key=lambda p: p.birth or ""):
                if name_term and name_term not in person.name.lower():
                    continue
                if gender_filter != "全部" and person.gender != gender_filter:
                    continue
                if birth_term and not (person.birth or "").startswith(birth_term):
                    continue
                if spouse_term:
                    spouse_names = [self.members[sid].name.lower() for sid in person.spouses if sid in self.members]
                    if not any(spouse_term in sn for sn in spouse_names):
                        continue
                if child_term:
                    child_names = [c.name.lower() for c in self.get_children(person.id)]
                    if not any(child_term in cn for cn in child_names):
                        continue
                if sibling_term:
                    sibling_names = [s.name.lower() for s in self.get_siblings(person)]
                    if not any(sibling_term in sn for sn in sibling_names):
                        continue

                spouses_str = "、".join(self.members[sid].name for sid in person.spouses if sid in self.members) or "无"
                children_str = "、".join(c.name for c in self.get_children(person.id)) or "无"
                siblings_str = "、".join(s.name for s in self.get_siblings(person)) or "无"
                row_id = tree.insert("", tk.END, values=(
                    person.name, person.gender, person.birth or "", spouses_str, children_str, siblings_str,
                ))
                _row_person_map[row_id] = person.id

            count_label.config(text=f"共 {len(_row_person_map)} 条")

        def on_set_center():
            sel = tree.selection()
            if not sel:
                return
            person_id = _row_person_map.get(sel[0])
            if person_id:
                self.set_center(person_id)
                dialog.destroy()

        tree.bind("<Double-1>", lambda _e: on_set_center())

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=8, pady=(2, 8))
        ttk.Button(btn_frame, text="设为中心", command=on_set_center).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT)
        count_label = ttk.Label(btn_frame, text="", foreground="#555")
        count_label.pack(side=tk.LEFT, padx=(10, 0))

        # Live-search: trigger on every field change
        for var in (name_var, gender_var, birth_var, spouse_var, child_var, sibling_var):
            var.trace_add("write", do_search)

        do_search()

    def open_member_dialog(self, role=None, target_id=None):
        """打开新增/编辑人物弹窗，并在提交时维护关系一致性。"""
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑人物" if role == "edit" else "新增人物")
        dialog.grab_set()

        editing_person = self.members.get(target_id) if role == "edit" else None
        excluded_id = editing_person.id if editing_person else None

        candidate_ids = [pid for pid in self.members.keys() if pid != excluded_id]
        candidate_labels = {pid: self.person_option(pid) for pid in candidate_ids}

        ttk.Label(dialog, text="姓名").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(dialog, text="性别").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        gender_combo = ttk.Combobox(dialog, values=["男", "女"], state="readonly", width=37)
        gender_combo.grid(row=1, column=1, padx=6, pady=6)
        gender_combo.set("男")

        ttk.Label(dialog, text="生日").grid(row=2, column=0, sticky=tk.W, padx=6, pady=6)
        birth_entry = ttk.Entry(dialog, width=40)
        birth_entry.grid(row=2, column=1, padx=6, pady=6)

        ttk.Label(dialog, text="卒日").grid(row=3, column=0, sticky=tk.W, padx=6, pady=6)
        death_entry = ttk.Entry(dialog, width=40)
        death_entry.grid(row=3, column=1, padx=6, pady=6)

        def build_searchable_combo(row, label_text):
            ttk.Label(dialog, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=6, pady=6)
            combo = ttk.Combobox(dialog, width=37)
            combo.grid(row=row, column=1, padx=6, pady=6)

            def refresh_options(_event=None):
                term = combo.get().strip().lower()
                options = [lbl for _, lbl in candidate_labels.items() if term in lbl.lower()]
                combo["values"] = options

            combo.bind("<KeyRelease>", refresh_options)
            combo["values"] = list(candidate_labels.values())
            return combo

        father_combo = build_searchable_combo(4, "父亲")
        mother_combo = build_searchable_combo(5, "母亲")

        ttk.Label(dialog, text="配偶(逐个添加)").grid(row=6, column=0, sticky=tk.NW, padx=6, pady=6)
        spouse_frame = ttk.Frame(dialog)
        spouse_frame.grid(row=6, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(dialog, text="兄弟姐妹(逐个添加)").grid(row=7, column=0, sticky=tk.NW, padx=6, pady=6)
        sibling_frame = ttk.Frame(dialog)
        sibling_frame.grid(row=7, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(dialog, text="生平简介").grid(row=8, column=0, sticky=tk.W, padx=6, pady=6)
        bio_entry = ttk.Entry(dialog, width=40)
        bio_entry.grid(row=8, column=1, padx=6, pady=6)

        existing_spouses = editing_person.spouses[:] if editing_person else []
        existing_siblings = [p.id for p in self.get_siblings(editing_person)] if editing_person else []

        def build_incremental_selector(parent_frame, initial_ids):
            selected_ids = [pid for pid in initial_ids if pid in candidate_labels]

            search_combo = ttk.Combobox(parent_frame, width=40)
            search_combo.pack(fill=tk.X)
            search_combo["values"] = list(candidate_labels.values())

            btn_row = ttk.Frame(parent_frame)
            btn_row.pack(fill=tk.X, pady=(4, 4))
            selected_list = tk.Listbox(parent_frame, selectmode=tk.SINGLE, width=52, height=5)
            selected_list.pack(fill=tk.BOTH)

            def refresh_selected_list():
                selected_list.delete(0, tk.END)
                for pid in selected_ids:
                    selected_list.insert(tk.END, candidate_labels[pid])

            def refresh_search_values(_event=None):
                term = search_combo.get().strip().lower()
                options = [lbl for lbl in candidate_labels.values() if term in lbl.lower()]
                search_combo["values"] = options

            def add_selected():
                pid = self.resolve_person_id(search_combo.get())
                if not pid or pid not in candidate_labels:
                    return
                if pid not in selected_ids:
                    selected_ids.append(pid)
                    refresh_selected_list()
                search_combo.set("")

            def remove_selected():
                idx = selected_list.curselection()
                if not idx:
                    return
                del selected_ids[idx[0]]
                refresh_selected_list()

            ttk.Button(btn_row, text="添加", command=add_selected).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Button(btn_row, text="移除", command=remove_selected).pack(side=tk.LEFT)

            search_combo.bind("<KeyRelease>", refresh_search_values)
            refresh_selected_list()

            return lambda: list(selected_ids)

        get_spouse_ids = build_incremental_selector(spouse_frame, existing_spouses)
        get_sibling_ids = build_incremental_selector(sibling_frame, existing_siblings)

        if editing_person:
            name_entry.insert(0, editing_person.name)
            gender_combo.set(editing_person.gender if editing_person.gender in ("男", "女") else "男")
            birth_entry.insert(0, editing_person.birth)
            death_entry.insert(0, editing_person.death)
            bio_entry.insert(0, editing_person.bio)
            if editing_person.father and editing_person.father in candidate_labels:
                father_combo.set(candidate_labels[editing_person.father])
            if editing_person.mother and editing_person.mother in candidate_labels:
                mother_combo.set(candidate_labels[editing_person.mother])

        def on_submit():
            name = name_entry.get().strip()
            gender = gender_combo.get().strip()
            if not name:
                messagebox.showwarning("缺少必填", "姓名为必填项目")
                return
            if gender not in ("男", "女"):
                messagebox.showwarning("性别无效", "性别只能选择 男 或 女")
                return

            father_id = self.resolve_person_id(father_combo.get())
            mother_id = self.resolve_person_id(mother_combo.get())
            if father_combo.get().strip() and not father_id:
                messagebox.showwarning("父亲无效", "父亲选择无效，请按姓名检索后选择")
                return
            if mother_combo.get().strip() and not mother_id:
                messagebox.showwarning("母亲无效", "母亲选择无效，请按姓名检索后选择")
                return

            spouse_ids = get_spouse_ids()
            sibling_ids = get_sibling_ids()

            # Validate spouse genders: male ↔ female only.
            expected_spouse_gender = "女" if gender == "男" else "男"
            for sid in spouse_ids:
                sp = self.members.get(sid)
                if sp and sp.gender != expected_spouse_gender:
                    messagebox.showwarning(
                        "配偶性别有误",
                        f"【{sp.name}】的性别为【{sp.gender}】，与当前人物（{gender}）性别相同。\n"
                        f"配偶必须为相反性别（{expected_spouse_gender}）。",
                    )
                    return

            birth = birth_entry.get().strip()
            death = death_entry.get().strip()
            bio = bio_entry.get().strip()

            if editing_person:
                person = editing_person
                person.name = name
                person.gender = gender
                person.birth = birth
                person.death = death
                person.bio = bio
                person.father = father_id
                person.mother = mother_id
                self.set_spouse_links(person.id, spouse_ids)
                self.apply_sibling_links(person.id, sibling_ids)
            else:
                person = Person(str(uuid.uuid4()), name, gender, birth, death, father=father_id, mother=mother_id, bio=bio)
                self.members[person.id] = person
                self.attach_relationship(person, role, target_id)
                self.set_spouse_links(person.id, spouse_ids)
                self.apply_sibling_links(person.id, sibling_ids)

            if person.father and person.mother:
                self.add_spouse_link(person.father, person.mother)

            self.save_and_refresh()
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.grid(row=9, column=0, columnspan=2, pady=(6, 10))
        ttk.Button(button_row, text="确认", command=on_submit).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=4)

    def attach_relationship(self, person, role, target_id):
        """根据“添加父亲/母亲/子女”的上下文自动补齐关系。"""
        target = self.members.get(target_id)
        if role == "father" and target:
            target.father = person.id
            if target.mother and target.mother in self.members:
                self.add_spouse_link(person.id, target.mother)
        elif role == "mother" and target:
            target.mother = person.id
            if target.father and target.father in self.members:
                self.add_spouse_link(person.id, target.father)
        elif role == "child" and target:
            # 子女父母应由“当前节点及其配偶”决定，不能继承当前节点的上一代父母。
            spouse_id = self.get_primary_spouse_id(target)
            if target.gender in ("男", "男性", "male"):
                if not person.father:
                    person.father = target.id
                if not person.mother:
                    person.mother = spouse_id
            elif target.gender in ("女", "女性", "female"):
                if not person.mother:
                    person.mother = target.id
                if not person.father:
                    person.father = spouse_id

    def collect_descendants(self, person_id, collected):
        for child in self.get_children(person_id):
            if child.id not in collected:
                collected.add(child.id)
                self.collect_descendants(child.id, collected)

    def delete_member(self, person_id):
        """删除人物及其后代，同时清理其他成员上的悬挂关系。"""
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
            person.spouses = [sid for sid in person.spouses if sid not in to_delete]

        if self.selected_member_id in to_delete:
            roots = self.get_roots()
            self.selected_member_id = roots[0].id if roots else None

        self.save_and_refresh()

    def save_and_refresh(self):
        """持久化并刷新画布。"""
        save_data(self.members)
        self.refresh_view()
