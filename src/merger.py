# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序

import re
import copy
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger


def normalize_channel_name(name: str) -> str:
    """标准化频道名，去除清晰度标签和括号内容"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_cctv_standard_name(name: str) -> str:
    """将央视频道名转换为标准格式，CCTV-5+ 优先于 CCTV-5"""
    name_original = name
    name_lower = name.lower()
    
    # 1. 优先匹配 CCTV-5+（必须包含加号）
    if re.search(r'cctv[-\s]*5\s*[＋\+]', name_lower):
        logger.debug(f"CCTV-5+ 匹配: {name_original}")
        return "CCTV-5+"
    
    # 2. 匹配 CCTV-5（不包含加号）
    if re.search(r'cctv[-\s]*5\b', name_lower):
        if '+' not in name_original and '＋' not in name_original:
            logger.debug(f"CCTV-5 匹配: {name_original}")
            return "CCTV-5"
    
    # 3. 其他 CCTV-数字
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = match.group(1)
        if num != '5':
            return f"CCTV-{num}"
    
    # 4. 央视+数字
    match = re.search(r'央视[-\s]*(\d+)', name_original)
    if match:
        num = match.group(1)
        if '+' in name_original or '＋' in name_original:
            if num == '5':
                return "CCTV-5+"
        if num == '5':
            return "CCTV-5"
        return f"CCTV-{num}"
    
    return None


def ensure_both_cctv5(merged: list) -> list:
    """确保 CCTV-5 和 CCTV-5+ 都存在"""
    has_cctv5 = False
    has_cctv5plus = False
    cctv5_ch = None
    cctv5plus_ch = None
    
    for ch in merged:
        if ch["name"] == "CCTV-5":
            has_cctv5 = True
            cctv5_ch = ch
        if ch["name"] == "CCTV-5+":
            has_cctv5plus = True
            cctv5plus_ch = ch
    
    logger.info(f"📊 检查 CCTV-5 状态: CCTV-5={has_cctv5}, CCTV-5+={has_cctv5plus}")
    
    # 情况1：两个都没有，创建默认的
    if not has_cctv5 and not has_cctv5plus:
        logger.warning("⚠️ 未找到 CCTV-5 和 CCTV-5+，创建默认频道")
        default_ch = {
            "name": "",
            "urls": [],
            "url": "",
            "latency": 9999,
            "video_codec": "",
            "group_title": "央视",
            "id": "",
            "logo": "",
        }
        cctv5_default = copy.deepcopy(default_ch)
        cctv5_default["name"] = "CCTV-5"
        merged.append(cctv5_default)
        
        cctv5plus_default = copy.deepcopy(default_ch)
        cctv5plus_default["name"] = "CCTV-5+"
        merged.append(cctv5plus_default)
        logger.info("✅ 已创建默认 CCTV-5 和 CCTV-5+")
    
    # 情况2：有 CCTV-5+ 但没有 CCTV-5
    elif has_cctv5plus and not has_cctv5:
        logger.warning("⚠️ 有 CCTV-5+ 但没有 CCTV-5，从 CCTV-5+ 复制")
        if cctv5plus_ch:
            cctv5 = copy.deepcopy(cctv5plus_ch)
            cctv5["name"] = "CCTV-5"
            merged.append(cctv5)
            logger.info("✅ 已添加 CCTV-5（从 CCTV-5+ 复制）")
    
    # 情况3：有 CCTV-5 但没有 CCTV-5+
    elif has_cctv5 and not has_cctv5plus:
        logger.warning("⚠️ 有 CCTV-5 但没有 CCTV-5+，从 CCTV-5 复制")
        if cctv5_ch:
            cctv5plus = copy.deepcopy(cctv5_ch)
            cctv5plus["name"] = "CCTV-5+"
            merged.append(cctv5plus)
            logger.info("✅ 已添加 CCTV-5+（从 CCTV-5 复制）")
    
    return merged


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，确保 CCTV-5 和 CCTV-5+ 正确分离"""
    groups = defaultdict(list)
    
    # 调试：输出所有 CCTV-5 相关的原始源
    cctv5_sources = []
    for ch in valid_channels:
        if 'cctv-5' in ch["name"].lower() or 'cctv5' in ch["name"].lower():
            cctv5_sources.append(ch["name"])
    
    if cctv5_sources:
        logger.info(f"📡 发现 {len(cctv5_sources)} 个 CCTV-5 相关源:")
        for src in cctv5_sources[:15]:
            logger.info(f"   - {src}")
    
    # 分组
    for ch in valid_channels:
        raw_name = ch["name"]
        std_name = get_cctv_standard_name(raw_name)
        if std_name:
            norm_name = std_name
        else:
            norm_name = normalize_channel_name(raw_name)
            if not norm_name or len(norm_name) < 2:
                norm_name = raw_name
        groups[norm_name].append(ch)
    
    # 调试：检查分组结果
    if "CCTV-5" in groups:
        logger.info(f"✅ CCTV-5 分组: {len(groups['CCTV-5'])} 个源")
        for src in groups["CCTV-5"][:5]:
            logger.info(f"   - {src['name']}")
    if "CCTV-5+" in groups:
        logger.info(f"✅ CCTV-5+ 分组: {len(groups['CCTV-5+'])} 个源")
        for src in groups["CCTV-5+"][:5]:
            logger.info(f"   - {src['name']}")
    
    logo_matcher = get_logo_matcher()
    matched_logos = 0
    merged = []
    
    for norm_name, ch_list in groups.items():
        # 排序：H.264 > H.265 > 其他，然后延迟低优先
        def sort_key(ch):
            codec = ch.get("video_codec", "").lower()
            if codec == "h264":
                priority = 0
            elif codec in ["hevc", "h265"]:
                priority = 1
            else:
                priority = 2
            return (priority, ch.get("latency", 9999))
        
        ch_list.sort(key=sort_key)
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0]
        
        logo_url = primary.get("tvg_logo", "")
        if not logo_url:
            logo_url = logo_matcher.get_logo_url(norm_name)
            matched_logos += 1
        
        merged.append({
            "name": norm_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary["latency"],
            "video_codec": primary["video_codec"],
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo_url,
        })
    
    # 强制确保 CCTV-5 和 CCTV-5+ 都存在
    merged = ensure_both_cctv5(merged)
    
    # 最终统计
    cctv5_count = sum(1 for ch in merged if ch["name"] == "CCTV-5")
    cctv5plus_count = sum(1 for ch in merged if ch["name"] == "CCTV-5+")
    logger.info(f"📊 合并结果: CCTV-5={cctv5_count}, CCTV-5+={cctv5plus_count}")
    logger.info(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    logger.info(f"🖼️ 图标匹配：为 {matched_logos} 个频道自动匹配了图标")
    
    return merged
