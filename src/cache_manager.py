#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from src.db_manager import IPTVDatabase, DATA_EXPIRY_SECONDS

class CacheManager:
    def __init__(self):
        self.db = IPTVDatabase()
        self.stats = self.db.get_stats()
        total = self.stats.get('total_channels', 0)
        active = self.stats.get('active', 0)
        failed = self.stats.get('failed', 0)
        recent = self.stats.get('recent_valid', 0)
        print(f"📊 数据库统计: 总计={total}, 活跃={active}, 失效={failed}, 近期有效={recent}")
        print(f"📅 数据有效期: {DATA_EXPIRY_SECONDS // 86400}天, 全量更新阈值: 30天")

    def should_update(self) -> bool:
        total = self.stats.get('total_channels', 0)
        if total == 0:
            print("📦 数据库为空，需要执行完整采集")
            return True

        if self.db.is_stale():
            print(f"⏰ 缓存数据已超过 {DATA_EXPIRY_SECONDS // 3600} 小时，需要执行完整采集")
            return True

        last_full = self.db.get_last_full_update_time()
        if last_full is None:
            print("📦 从未执行全量采集，需要执行")
            return True
        if (int(time.time()) - last_full) > 30 * 24 * 3600:
            print("⏰ 距离上次全量采集已超过30天，需要执行完整采集")
            return True

        last_update = self.db.get_last_update_time()
        if last_update:
            print(f"✅ 缓存数据有效（上次更新: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update))}），跳过完整采集")
        else:
            print("✅ 缓存数据有效，跳过完整采集")
        return False

    def load_from_cache(self):
        channels = self.db.load_valid_channels(skip_old=False)
        print(f"📂 从缓存加载了 {len(channels)} 个频道（每个 URL 一条记录）")
        return channels

    def save_to_cache(self, channels):
        records = []
        for ch in channels:
            if isinstance(ch, dict):
                if 'urls' in ch and ch['urls']:
                    for url in ch['urls']:
                        records.append({
                            "name": ch.get("name", ""),
                            "url": url,
                            "group_title": ch.get("group_title", ""),
                            "id": ch.get("id", ""),
                            "logo": ch.get("logo", ""),
                            "latency": ch.get("latency", 9999),
                            "video_codec": ch.get("video_codec", ""),
                            "ip_info": ch.get("ip_info")
                        })
                elif 'url' in ch:
                    records.append(ch)
            else:
                if hasattr(ch, 'urls') and ch.urls:
                    for url in ch.urls:
                        records.append({
                            "name": ch.name,
                            "url": url,
                            "group_title": getattr(ch, 'group_title', ''),
                            "id": getattr(ch, 'tvg_id', ''),
                            "logo": getattr(ch, 'tvg_logo', ''),
                            "latency": getattr(ch, 'latency', 9999),
                            "video_codec": getattr(ch, 'video_codec', ''),
                            "ip_info": getattr(ch, 'ip_info', None)
                        })
                elif hasattr(ch, 'url'):
                    records.append({
                        "name": ch.name,
                        "url": ch.url,
                        "group_title": getattr(ch, 'group_title', ''),
                        "id": getattr(ch, 'tvg_id', ''),
                        "logo": getattr(ch, 'tvg_logo', ''),
                        "latency": getattr(ch, 'latency', 9999),
                        "video_codec": getattr(ch, 'video_codec', ''),
                        "ip_info": getattr(ch, 'ip_info', None)
                    })
        if records:
            self.db.save_channels(records)
            self.db.set_last_update_time()
            print(f"💾 已保存 {len(records)} 条记录（来自 {len(channels)} 个合并频道）到缓存")
        else:
            print("⚠️ 没有可保存的记录")

    def get_cache_age(self) -> int:
        last_update = self.db.get_last_update_time()
        if last_update is None:
            return 0
        elapsed = int(time.time()) - last_update
        return max(0, DATA_EXPIRY_SECONDS - elapsed)
