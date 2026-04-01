#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据持久化与样例数据构建。"""

import json
import uuid

from model import DATA_FILE, Person

def save_data(members):
    """将内存中的人物数据保存到 data.json。"""
    raw = {"members": {member_id: member.to_dict() for member_id, member in members.items()}}
    DATA_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def build_sample_data():
    """
    构建一棵五代赵氏家谱测试数据，关系严格合法：
      - 夫妻互为配偶且性别相反
      - 子女的 father/mother 指向正确的父亲/母亲 ID
      - 无自环、无乱引用
    """
    members = {}
    name_to_id: dict[str, str] = {}

    def add(name, gender, birth, death="", father=None, mother=None, bio=""):
        pid = str(uuid.uuid4())
        father_id = name_to_id.get(father) if father else None
        mother_id = name_to_id.get(mother) if mother else None
        members[pid] = Person(pid, name, gender, birth, death, father_id, mother_id, bio=bio)
        name_to_id[name] = pid
        return pid

    def marry(name1, name2):
        pid1 = name_to_id[name1]
        pid2 = name_to_id[name2]
        if pid2 not in members[pid1].spouses:
            members[pid1].spouses.append(pid2)
        if pid1 not in members[pid2].spouses:
            members[pid2].spouses.append(pid1)

    # ── 第一代 ──────────────────────────────────────────────────────
    add("赵大山", "男", "1920-03-15", "1995-08-20", bio="赵氏家族第一代祖先，曾任私塾先生")
    add("李秀英", "女", "1923-07-08", "2001-12-10", bio="贤良淑德，勤俭持家")
    marry("赵大山", "李秀英")

    # ── 第二代：赵大山与李秀英的子女 ───────────────────────────────
    add("赵国强", "男", "1945-04-02", father="赵大山", mother="李秀英", bio="长子，工厂工人")
    add("赵云花", "女", "1947-09-18", father="赵大山", mother="李秀英", bio="次女，小学教师")
    add("赵国华", "男", "1950-11-05", father="赵大山", mother="李秀英", bio="幼子，经商")

    # 第二代配偶（外来，无父母记录）
    add("陈美玲", "女", "1946-06-20", bio="赵国强之妻，护士出身")
    add("周伟民", "男", "1945-02-14", bio="赵云花之夫，工程师")
    add("孙晓燕", "女", "1952-03-30", bio="赵国华之妻，会计")

    marry("赵国强", "陈美玲")
    marry("赵云花", "周伟民")
    marry("赵国华", "孙晓燕")

    # ── 第三代 ──────────────────────────────────────────────────────
    # 赵国强 & 陈美玲 的子女
    add("赵志明", "男", "1968-01-15", father="赵国强", mother="陈美玲", bio="长孙，软件工程师")
    add("赵丽娜", "女", "1970-05-22", father="赵国强", mother="陈美玲", bio="长孙女，医生")
    add("赵志远", "男", "1973-08-08", father="赵国强", mother="陈美玲", bio="三孙，高中教师")

    # 赵云花 & 周伟民 的子女
    add("周明远", "男", "1972-04-10", father="周伟民", mother="赵云花", bio="云花长子，建筑师")
    add("周丽芳", "女", "1974-11-28", father="周伟民", mother="赵云花", bio="云花幼女，律师")

    # 赵国华 & 孙晓燕 的子女
    add("赵建国", "男", "1975-06-01", father="赵国华", mother="孙晓燕", bio="国华长子，医生")
    add("赵建华", "女", "1977-02-17", father="赵国华", mother="孙晓燕", bio="国华幼女，画家")

    # 第三代配偶（外来）
    add("王雪梅", "女", "1969-03-10", bio="赵志明之妻，律师")
    add("吴建军", "男", "1969-07-05", bio="赵丽娜之夫，警察")
    add("张欣怡", "女", "1974-12-01", bio="赵志远之妻，设计师")
    add("林晓燕", "女", "1976-09-14", bio="赵建国之妻，护士")
    add("刘志强", "男", "1976-05-20", bio="赵建华之夫，厨师")
    add("郑伟峰", "男", "1973-10-30", bio="周丽芳之夫，商人")

    marry("赵志明", "王雪梅")
    marry("赵丽娜", "吴建军")
    marry("赵志远", "张欣怡")
    marry("赵建国", "林晓燕")
    marry("赵建华", "刘志强")
    marry("周丽芳", "郑伟峰")

    # ── 第四代 ──────────────────────────────────────────────────────
    # 赵志明 & 王雪梅 的子女
    add("赵小明", "男", "1995-06-18", father="赵志明", mother="王雪梅", bio="第四代，大学生")
    add("赵小红", "女", "1998-03-07", father="赵志明", mother="王雪梅", bio="第四代，高中生")

    # 赵丽娜 & 吴建军 的子女
    add("吴浩然", "男", "1996-09-12", father="吴建军", mother="赵丽娜", bio="第四代")

    # 赵志远 & 张欣怡 的子女
    add("赵天宇", "男", "2000-01-20", father="赵志远", mother="张欣怡", bio="第四代")
    add("赵天娇", "女", "2002-08-15", father="赵志远", mother="张欣怡", bio="第四代")

    # 赵建国 & 林晓燕 的子女
    add("赵宇航", "男", "1998-11-03", father="赵建国", mother="林晓燕", bio="第四代，理工科学生")

    # 赵建华 & 刘志强 的子女
    add("刘思思", "女", "2001-04-25", father="刘志强", mother="赵建华", bio="第四代")

    # 周丽芳 & 郑伟峰 的子女
    add("郑浩宇", "男", "2000-07-30", father="郑伟峰", mother="周丽芳", bio="第四代")

    # 第四代婚配
    add("刘梦瑶", "女", "1997-02-14", bio="赵小明之妻")
    marry("赵小明", "刘梦瑶")

    # ── 第五代 ──────────────────────────────────────────────────────
    add("赵思远", "男", "2022-05-10", father="赵小明", mother="刘梦瑶", bio="第五代，家族最小成员")

    return members


def normalize_members(members):
    """修正历史脏数据，保证基础关系可用。

    - 移除父母自引用
    - 去除配偶自引用与重复配偶
    """
    changed = False
    for person in members.values():
        if person.father == person.id:
            person.father = None
            changed = True
        if person.mother == person.id:
            person.mother = None
            changed = True
        normalized_spouses = []
        seen = set()
        for spouse_id in person.spouses:
            if spouse_id == person.id or spouse_id in seen:
                changed = True
                continue
            seen.add(spouse_id)
            normalized_spouses.append(spouse_id)
        person.spouses = normalized_spouses
    return changed


def load_data():
    """优先加载本地数据；无有效数据时生成样例数据。"""
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


