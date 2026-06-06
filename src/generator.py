# src/generator.py
import os
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE

def generate_m3u(classified: dict, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for category, channels in classified.items():
            if not channels:
                continue
            f.write(f"\n# 分类: {category}\n")
            for ch in channels:
                # 获取最优 URL（多源取第一个）
                if 'urls' in ch and ch['urls']:
                    url = ch['urls'][0]
                elif 'url' in ch:
                    url = ch['url']
                else:
                    continue
                extinf = f'#EXTINF:-1'
                if ch.get('id'):
                    extinf += f' tvg-id="{ch["id"]}"'
                if ch.get('logo'):
                    extinf += f' tvg-logo="{ch["logo"]}"'
                if category:
                    extinf += f' group-title="{category}"'
                extinf += f',{ch["name"]}\n'
                f.write(extinf)
                f.write(f"{url}\n")

def generate_txt(classified: dict, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        for category, channels in classified.items():
            if not channels:
                continue
            f.write(f"\n# {category}\n")
            for ch in channels:
                if 'urls' in ch and ch['urls']:
                    url = ch['urls'][0]
                elif 'url' in ch:
                    url = ch['url']
                else:
                    continue
                f.write(f"{url}\n")

def generate_outputs(classified: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    m3u_path = os.path.join(OUTPUT_DIR, M3U_FILE)
    txt_path = os.path.join(OUTPUT_DIR, TXT_FILE)
    generate_m3u(classified, m3u_path)
    generate_txt(classified, txt_path)
    print(f"📄 输出已生成：\n  - {m3u_path}\n  - {txt_path}")
