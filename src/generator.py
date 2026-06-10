# src/generator.py
from pathlib import Path
from typing import List, Tuple, Dict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger

def generate_m3u_by_demo_order(channels_by_name: Dict[str, dict], demo_order: List[Tuple[str, str]], output_path: Path) -> None:
    """严格按照 demo.txt 的顺序生成 M3U 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                url = channel.get("urls", [channel.get("url")])[0]
                name = channel.get("name", demo_name)
                extinf = f'#EXTINF:-1 group-title="{cat}",{name}'
                f.write(f"{extinf}\n{url}\n")
    logger.info(f"✅ M3U 文件已生成: {output_path}")

def generate_txt_by_demo_order(channels_by_name: Dict[str, dict], demo_order: List[Tuple[str, str]], output_path: Path) -> None:
    """严格按照 demo.txt 的顺序生成 TXT 文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        current_cat = None
        for cat, demo_name in demo_order:
            if cat != current_cat:
                current_cat = cat
                f.write(f"\n{cat},#genre#\n")
            channel = channels_by_name.get(demo_name)
            if channel:
                url = channel.get("urls", [channel.get("url")])[0]
                name = channel.get("name", demo_name)
                f.write(f"{name},{url}\n")
    logger.info(f"✅ TXT 文件已生成: {output_path}")

def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[Tuple[str, str]]) -> None:
    """按照 demo.txt 的顺序输出 M3U 和 TXT 文件"""
    if not ordered_channels or not demo_order:
        logger.warning("无频道数据或 demo_order 为空，跳过输出生成")
        return

    # 构建 {标准化名称: 频道数据} 的字典
    channels_by_name = {ch["name"]: ch for ch in ordered_channels}
    # 同时使用 demo_name 作为备用键（如果有的话）
    for ch in ordered_channels:
        if "demo_name" in ch:
            channels_by_name[ch["demo_name"]] = ch

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u_by_demo_order(channels_by_name, demo_order, OUTPUT_DIR / M3U_FILE)
    generate_txt_by_demo_order(channels_by_name, demo_order, OUTPUT_DIR / TXT_FILE)

    # 生成多源 M3U（同样按 demo 顺序）
    with open(OUTPUT_DIR / "tv_multi.m3u", 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, demo_name in demo_order:
            channel = channels_by_name.get(demo_name)
            if channel:
                urls = channel.get("urls", [channel.get("url")])
                multi_url = " # ".join(urls)
                name = channel.get("name", demo_name)
                f.write(f'#EXTINF:-1 group-title="{cat}",{name}\n{multi_url}\n')
    logger.info(f"✅ 多源 M3U 文件已生成: {OUTPUT_DIR / 'tv_multi.m3u'}")
