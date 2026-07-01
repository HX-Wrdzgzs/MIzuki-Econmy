import os
import sys
import json
import re
import time
import requests
from pathlib import Path
try:
    from nonebot.log import logger
except ImportError:
    import logging
    logger = logging.getLogger("Mizuki-Econmy")

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy"
SAVE_DIR = DATA_DIR / "cards"
CARDS_JSON = DATA_DIR / "cards.json"
DIFF_LOG = DATA_DIR / "card_diff.log"

LOCAL_PROXY = "http://127.0.0.1:9008"
REMOTE_PROXY_BASE = "https://proxy.mizuki.top"

CARDS_API = f"{REMOTE_PROXY_BASE}/api-db/sekai-master-db-diff/cards.json"
SEKAI_BEST_BASE = "https://storage.sekai.best/sekai-jp-assets/character/member"

CHAR_MAP = {
    1: "星乃一歌", 2: "天馬咲希", 3: "望月穂波", 4: "日野森志歩",
    5: "花里みのり", 6: "桐谷遥", 7: "桃井愛莉", 8: "日野森雫",
    9: "小豆沢こはね", 10: "白石杏", 11: "東雲彰人", 12: "青柳冬弥",
    13: "天馬司", 14: "鳳えむ", 15: "草薙寧々", 16: "神代類",
    17: "宵崎奏", 18: "朝比奈まふゆ", 19: "東雲絵名", 20: "暁山瑞希",
    21: "初音ミク", 22: "鏡音リン", 23: "鏡音レン", 24: "巡音ルカ",
    25: "MEIKO", 26: "KAITO"
}
RARITY_MAP = {
    "rarity_1": "☆1", "rarity_2": "☆2",
    "rarity_3": "☆3", "rarity_4": "☆4",
    "rarity_birthday": "BD"
}

def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name))

def get_proxies():
    try:
        r = requests.get("http://127.0.0.1:9008", timeout=2)
        return {"http": LOCAL_PROXY, "https": LOCAL_PROXY}
    except Exception:
        return None

def download(url, save_path, proxies=None):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
        return True
    try:
        r = requests.get(url, proxies=proxies, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 1000:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def download_url_with_fallback(direct_url, proxy_url, save_path, proxies):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
        return "exists"
    if proxies:
        if download(direct_url, save_path, proxies):
            return "local-proxy"
    if download(direct_url, save_path):
        return "direct"
    if download(proxy_url, save_path):
        return "remote-proxy"
    return "failed"

def download_with_fallback(asset_name, save_path, char_name, proxies):
    sekai_url = f"{SEKAI_BEST_BASE}/{asset_name}"
    proxy_url = f"{REMOTE_PROXY_BASE}/api-assets/sekai-jp-assets/character/member/{asset_name}"
    return download_url_with_fallback(sekai_url, proxy_url, save_path, proxies)

def fetch_latest_cards():
    proxies = get_proxies()
    if proxies:
        try:
            r = requests.get(CARDS_API, proxies=proxies, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    try:
        r = requests.get(CARDS_API, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        pass

    fallback_url = "https://storage.sekai.best/sekai-jp-assets/character/member/../masterdata/zh-TW/cards.json"
    try:
        r = requests.get(fallback_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return None

def load_local_cards():
    if CARDS_JSON.exists():
        with open(CARDS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def find_new_cards(old_cards, new_cards):
    old_ids = {c.get("id") for c in old_cards}
    new_ids = {c.get("id") for c in new_cards}
    added_ids = new_ids - old_ids
    removed_ids = old_ids - new_ids
    return added_ids, removed_ids

def process_single_card(args_tuple):
    i, total, card, force, proxies = args_tuple
    char_id = card.get("characterId", 0)
    char_name = CHAR_MAP.get(char_id, "其他")
    rarity = RARITY_MAP.get(card.get("cardRarityType"), "?")
    prefix = card.get("prefix", "card")
    asset_name = card.get("assetbundleName")
    if not asset_name:
        return 0, 0
    safe_name = sanitize(f"[{rarity}][{prefix}]_{char_name}")
    target_dir = SAVE_DIR / char_name
    target_dir.mkdir(exist_ok=True)
    
    success = 0
    failed = 0
    
    # Card image normal
    path_normal = target_dir / f"{safe_name}_特训前.webp"
    if not path_normal.exists() or ("--force-all" in sys.argv):
        logger.info(f"PJSK卡牌抓取器: [{i+1}/{total}] 正在下载 {char_name} (ID: {card.get('id')}) 的特训前大图...")
        result = download_with_fallback(f"{asset_name}/card_normal.webp", str(path_normal), char_name, proxies)
        if result != "failed" and result != "exists":
            success += 1
        elif result == "failed":
            failed += 1
    
    # Card thumbnail normal
    path_normal_thumb = target_dir / f"{safe_name}_特训前_thumb.webp"
    if not path_normal_thumb.exists() or force:
        logger.info(f"PJSK卡牌抓取器: [{i+1}/{total}] 正在下载 {char_name} (ID: {card.get('id')}) 的特训前缩略图...")
        direct_t_url = f"https://storage.sekai.best/sekai-jp-assets/thumbnail/chara/{asset_name}_normal.webp"
        proxy_t_url = f"{REMOTE_PROXY_BASE}/api-assets/sekai-jp-assets/thumbnail/chara/{asset_name}_normal.webp"
        download_url_with_fallback(direct_t_url, proxy_t_url, str(path_normal_thumb), proxies)

    if card.get("cardRarityType") not in ["rarity_1", "rarity_2"]:
        # Card image trained
        path_trained = target_dir / f"{safe_name}_特训后.webp"
        if not path_trained.exists() or ("--force-all" in sys.argv):
            logger.info(f"PJSK卡牌抓取器: [{i+1}/{total}] 正在下载 {char_name} (ID: {card.get('id')}) 的特训后大图...")
            result = download_with_fallback(f"{asset_name}/card_after_training.webp", str(path_trained), char_name, proxies)
            if result != "failed" and result != "exists":
                success += 1
            elif result == "failed":
                failed += 1
        
        # Card thumbnail trained
        path_trained_thumb = target_dir / f"{safe_name}_特训后_thumb.webp"
        if not path_trained_thumb.exists() or force:
            logger.info(f"PJSK卡牌抓取器: [{i+1}/{total}] 正在下载 {char_name} (ID: {card.get('id')}) 的特训后缩略图...")
            direct_t_url = f"https://storage.sekai.best/sekai-jp-assets/thumbnail/chara/{asset_name}_after_training.webp"
            proxy_t_url = f"{REMOTE_PROXY_BASE}/api-assets/sekai-jp-assets/thumbnail/chara/{asset_name}_after_training.webp"
            download_url_with_fallback(direct_t_url, proxy_t_url, str(path_trained_thumb), proxies)
            
    return success, failed

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

    logger.info("PJSK卡牌抓取器: 开始检查并更新卡牌元数据与缩略图...")
    force = "--force" in sys.argv
    no_download = "--no-download" in sys.argv
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Clean loose unclassified webp files in SAVE_DIR root
    cleaned_loose = 0
    for f in SAVE_DIR.glob("*.webp"):
        try:
            f.unlink()
            cleaned_loose += 1
        except:
            pass
    if cleaned_loose > 0:
        logger.info(f"PJSK卡牌抓取器: 已成功从卡牌根目录清理 {cleaned_loose} 个散落图片文件。")

    new_cards = fetch_latest_cards()
    if not new_cards:
        logger.error("PJSK卡牌抓取器: 无法拉取最新的卡牌元数据。")
        return
    old_cards = load_local_cards()
    added_ids, removed_ids = find_new_cards(old_cards, new_cards)
    if not added_ids and not force:
        logger.info("PJSK卡牌抓取器: 未检测到任何新增卡牌，本地缓存已是最新状态。")
        with open(CARDS_JSON, "w", encoding="utf-8") as f:
            json.dump(new_cards, f, ensure_ascii=False, indent=2)
        return
    
    new_card_list = [c for c in new_cards if c.get("id") in added_ids]
    if no_download:
        logger.info(f"PJSK卡牌抓取器: 仅更新元数据，共新增 {len(new_card_list)} 个卡牌配置项。")
    else:
        from concurrent.futures import ThreadPoolExecutor
        proxies = get_proxies()
        success = 0
        failed = 0
        download_list = new_card_list if not force else new_cards
        total_len = len(download_list)
        logger.info(f"PJSK卡牌抓取器: 检测到卡牌共 {total_len} 张，已启用 16 线程并发下载卡面与缩略图...")
        
        with ThreadPoolExecutor(max_workers=16) as executor:
            tasks = [(i, total_len, card, force, proxies) for i, card in enumerate(download_list)]
            results = list(executor.map(process_single_card, tasks))
            
        for s, f in results:
            success += s
            failed += f
            
        logger.info(f"PJSK卡牌抓取器: 卡牌抓取处理完成，成功下载并更新了 {success} 个大图，失败数: {failed}。")

    with open(CARDS_JSON, "w", encoding="utf-8") as f:
        json.dump(new_cards, f, ensure_ascii=False, indent=2)
    with open(DIFF_LOG, "a", encoding="utf-8") as f:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{now}] old={len(old_cards)} new={len(new_cards)} added={len(added_ids)} removed={len(removed_ids)}\n")
        for card in new_card_list:
            cid = card.get("characterId", 0)
            char_name = CHAR_MAP.get(cid, "?")
            prefix = card.get("prefix", "?")
            f.write(f"  + [{card.get('cardRarityType')}] {char_name} - {prefix}\n")

if __name__ == "__main__":
    main()