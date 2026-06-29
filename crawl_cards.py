import os
import sys
import json
import re
import time
import requests
from pathlib import Path

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
    21: "初音ミク", 22: "镜音リン", 23: "镜音レン", 24: "巡音ルカ",
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

def download_with_fallback(asset_name, save_path, char_name, proxies):
    sekai_url = f"{SEKAI_BEST_BASE}/{asset_name}"
    proxy_url = f"{REMOTE_PROXY_BASE}/api-assets/sekai-jp-assets/character/member/{asset_name}"

    if proxies:
        if download(sekai_url, save_path, proxies):
            return "local-proxy"

    if download(sekai_url, save_path):
        return "direct"

    if download(proxy_url, save_path):
        return "remote-proxy"

    return "failed"

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

def main():
    force = "--force" in sys.argv
    no_download = "--no-download" in sys.argv
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    new_cards = fetch_latest_cards()
    if not new_cards:
        return
    old_cards = load_local_cards()
    added_ids, removed_ids = find_new_cards(old_cards, new_cards)
    if not added_ids and not force:
        with open(CARDS_JSON, "w", encoding="utf-8") as f:
            json.dump(new_cards, f, ensure_ascii=False, indent=2)
        return
    new_card_list = [c for c in new_cards if c.get("id") in added_ids]
    if no_download:
        pass
    else:
        proxies = get_proxies()
        success = 0
        failed = 0
        download_list = new_card_list if not force else new_cards
        for i, card in enumerate(download_list):
            char_id = card.get("characterId", 0)
            char_name = CHAR_MAP.get(char_id, "其他")
            rarity = RARITY_MAP.get(card.get("cardRarityType"), "?")
            prefix = card.get("prefix", "card")
            asset_name = card.get("assetbundleName")
            if not asset_name:
                continue
            safe_name = sanitize(f"[{rarity}][{prefix}]_{char_name}")
            target_dir = SAVE_DIR / char_name
            target_dir.mkdir(exist_ok=True)
            path_normal = target_dir / f"{safe_name}_特训前.webp"
            if not path_normal.exists() or force:
                result = download_with_fallback(f"{asset_name}/card_normal.webp", str(path_normal), char_name, proxies)
                if result != "failed":
                    success += 1
                else:
                    failed += 1
            if card.get("cardRarityType") not in ["rarity_1", "rarity_2"]:
                path_trained = target_dir / f"{safe_name}_特训后.webp"
                if not path_trained.exists() or force:
                    result = download_with_fallback(f"{asset_name}/card_after_training.webp", str(path_trained), char_name, proxies)
                    if result != "failed":
                        success += 1
                    else:
                        failed += 1
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