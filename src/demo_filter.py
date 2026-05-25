# src/demo_filter.py
# Demo 频道筛选与排序模块，记录被跳过的频道

from pathlib import Path
from typing import List, Tuple, Dict
from src.config import DEMO_FILE, OUTPUT_DIR
from src.alias_matcher import get_alias_matcher

try:
    from src.config import DEMO_MATCH_MODE
except ImportError:
    DEMO_MATCH_MODE = "contains"

SKIP_FILE = OUTPUT_DIR / "skip.txt"

def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    if not demo_file.exists():
        print(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    matcher = get_alias_matcher()
    order = []
    current_category = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#"):
                current_category = line[:-7]
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                demo_name = line
                if matcher:
                    demo_name = matcher.normalize(demo_name)
                order.append((current_category, demo_name))
            else:
                order.append(("其他", line))
    print(f"📋 从 demo.txt 解析到 {len(order)} 个有序频道，共 {len(set(c for c,_ in order))} 个分类")
    return order

def match_channel_name(channel_name: str, demo_name: str) -> bool:
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name
    else:
        return demo_name in channel_name or channel_name in demo_name

def filter_and_order_by_demo(channels: list, alias_matcher=None) -> Tuple[List[dict], Dict[str, list]]:
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        print("⚠️ demo.txt 为空，跳过筛选")
        return channels, {}

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    category_map = {}
    matched_names = set()
    skipped_channels = []

    for category, demo_name in demo_order:
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                category_map.setdefault(category, []).append(ch)
                continue
        
        matched_flag = False
        for ch in channels:
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                category_map.setdefault(category, []).append(ch_copy)
                matched_flag = True
                break
        
        if not matched_flag:
            # 记录未匹配的 demo 频道（被跳过的）
            skipped_channels.append((category, demo_name))

    # 记录未匹配的频道到 skip.txt
    if skipped_channels:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(SKIP_FILE, "w", encoding="utf-8") as f:
            f.write("# Demo 筛选未匹配的频道（这些频道在采集源中未找到）\n")
            f.write("# 格式：分类,频道名\n")
            for category, demo_name in skipped_channels:
                f.write(f"{category},{demo_name}\n")
        print(f"📝 未匹配的 {len(skipped_channels)} 个频道已记录到 {SKIP_FILE}")

    print(f"🎯 Demo 筛选：原始 {len(channels)} 个频道 -> 匹配 {len(matched)} 个频道（匹配模式: {DEMO_MATCH_MODE}）")
    return matched, category_map
