# src/classifier.py
# 智能分类模块，强制输出顺序，支持地方子分类

from src.config import CCTV_ORDER, OUTPUT_CATEGORY_ORDER

PROVINCES = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "香港", "澳门"
]

def classify_channel(channel: dict) -> str:
    """返回频道所属大类：央视/卫视/地方/港澳台/其他"""
    name = channel.get("name", "")
    name_lower = name.lower()
    
    # 1. 央视（最高优先级）
    if any(kw in name_lower for kw in ["cctv", "央视", "中央电视", "中央-", "中央台", "cntv"]):
        return "央视"
    
    # 2. 港澳台
    if any(kw in name_lower for kw in ["港", "澳", "台", "香港", "澳门", "台湾", "翡翠", "明珠", "凤凰", "tvb", "无线", "rthk", "hoy"]):
        return "港澳台"
    
    # 3. 卫视（明确包含“卫视”）
    if "卫视" in name:
        return "卫视"
    
    # 4. 地方（包含省份或常见后缀）
    for prov in PROVINCES:
        if prov in name:
            return "地方"
    if any(kw in name for kw in ["电视台", "综合频道", "公共频道", "生活频道", "新闻综合"]):
        return "地方"
    
    return "其他"

def extract_subcategory(channel: dict) -> str:
    """提取地方频道的子分类（如“北京频道”）"""
    name = channel.get("name", "")
    group = channel.get("group_title", "")
    
    # 优先从 group_title 中提取
    if group:
        for prov in PROVINCES:
            if prov in group:
                return f"{prov}频道"
    # 从频道名中提取
    for prov in PROVINCES:
        if prov in name:
            return f"{prov}频道"
    return "地方频道"

def classify_and_filter(channels: list) -> dict:
    """返回有序字典，顺序 = OUTPUT_CATEGORY_ORDER，地方频道附加 subcategory 字段"""
    temp = {cat: [] for cat in OUTPUT_CATEGORY_ORDER}
    other_count = 0
    
    for ch in channels:
        cat = classify_channel(ch)
        if cat in temp:
            if cat == "地方":
                ch["subcategory"] = extract_subcategory(ch)
            temp[cat].append(ch)
        else:
            other_count += 1
    
    # 央视频道按 CCTV_ORDER 排序
    if temp["央视"]:
        def ctv_key(ch):
            name = ch["name"]
            for idx, std in enumerate(CCTV_ORDER):
                if std.lower() == name.lower() or name.lower().startswith(std.lower()):
                    return idx
            return len(CCTV_ORDER)
        temp["央视"].sort(key=ctv_key)
    
    # 卫视、港澳台按名称排序
    for cat in ["卫视", "港澳台"]:
        if temp[cat]:
            temp[cat].sort(key=lambda x: x["name"])
    
    # 地方频道先按子分类排序，再按名称排序
    if temp["地方"]:
        temp["地方"].sort(key=lambda x: (x.get("subcategory", ""), x["name"]))
    
    # 构建最终有序字典（只保留非空分类）
    result = {cat: temp[cat] for cat in OUTPUT_CATEGORY_ORDER if temp[cat]}
    
    print("📊 分类统计（按顺序）：")
    for cat, lst in result.items():
        if lst:
            print(f"  {cat}: {len(lst)} 个频道")
            if cat == "地方":
                subcats = {}
                for ch in lst:
                    sub = ch.get("subcategory", "地方频道")
                    subcats[sub] = subcats.get(sub, 0) + 1
                for sub, cnt in subcats.items():
                    print(f"    - {sub}: {cnt}")
    print(f"  （其他分类被过滤: {other_count} 个频道）")
    return result
