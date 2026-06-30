import io
import httpx
import math
import time
import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .const import SHOP_ITEMS, PJSK_LOCAL_PROXY, PJSK_PROXY_URL, PJSK_SEKAI_BEST_BASE, RARITY_MAP

C_BG = (255, 240, 245)
C_SURFACE = (255, 255, 255)
C_BORDER = (240, 224, 232)
C_PINK_MAIN = (228, 164, 190)
C_PINK_DARK = (219, 112, 147)
C_TEXT_MAIN = (80, 80, 80)
C_TEXT_SUB = (150, 150, 150)
C_GREEN = (60, 179, 113)
C_RED = (205, 92, 92)

THEME_COLORS = {
    0: {"bg": (255, 240, 245), "top": (228, 164, 190), "text": (80, 80, 80), "sub": (150, 150, 150), "acc": (219, 112, 147)},
    1: {"bg": (240, 248, 255), "top": (100, 149, 237), "text": (50, 50, 50), "sub": (120, 120, 120), "acc": (70, 130, 180)},
    2: {"bg": (245, 240, 250), "top": (147, 112, 219), "text": (50, 40, 70), "sub": (130, 120, 150), "acc": (138, 43, 226)},
    3: {"bg": (240, 255, 245), "top": (102, 205, 170), "text": (40, 70, 60), "sub": (120, 150, 140), "acc": (46, 139, 87)},
    4: {"bg": (30, 30, 35), "top": (50, 50, 60), "text": (220, 220, 230), "sub": (150, 150, 160), "acc": (219, 112, 147)}
}

FONT_CACHE = {}

def load_font(size):
    if size not in FONT_CACHE:
        try:
            FONT_CACHE[size] = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", size)
        except:
            try:
                FONT_CACHE[size] = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
            except:
                FONT_CACHE[size] = ImageFont.load_default()
    return FONT_CACHE[size]

def wrap_text(text, font, max_width, draw):
    lines = []
    if not text:
        return lines
    current_line = ""
    for char in text:
        if draw.textlength(current_line + char, font=font) <= max_width:
            current_line += char
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)
    return lines

async def get_avatar(user_id, name="User", bot=None, group_id=None):
    from pathlib import Path
    import time
    cache_dir = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "avatars"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{user_id}.png"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < 86400):
        try:
            return Image.open(cache_path).convert("RGBA")
        except:
            pass
    avatar_url = None
    if bot:
        try:
            params = {"user_id": int(user_id)}
            if group_id:
                params["group_id"] = str(group_id)
            result = await bot.call_api("get_avatar", **params)
            avatar_url = result.get("message")
        except:
            pass
    if not avatar_url:
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640&t={int(time.time())}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(avatar_url, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize((150, 150))
                mask = Image.new("L", (150, 150), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, 150, 150), fill=255)
                img.putalpha(mask)
                try:
                    img.save(cache_path, "PNG")
                except:
                    pass
                return img
    except:
        pass
    img = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, 150, 150), fill=C_PINK_MAIN)
    char = name[0] if name else "U"
    f = load_font(80)
    w = draw.textlength(char, font=f)
    draw.text(((150 - w) / 2, 20), char, font=f, fill="white")
    return img

def draw_dot(draw, x, y, color):
    r = 8
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

async def draw_sign_card(user_id, user_name, data, bot=None, group_id=None):
    W = 800
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    f_title = load_font(40)
    f_info = load_font(28)
    f_jp = load_font(32)
    f_cn = load_font(28)
    f_evt = load_font(30)
    f_pc = load_font(34)
    q_jp, q_cn = data['quote'].split(" | ")
    lines_jp = wrap_text(q_jp, f_jp, 640, dummy_draw)
    lines_cn = wrap_text(q_cn, f_cn, 640, dummy_draw)
    g_raw = data['good'].replace("：", " | ")
    b_raw = data['bad'].replace("：", " | ")
    good_lines = wrap_text(f"宜: {g_raw}", f_evt, 560, dummy_draw)
    bad_lines = wrap_text(f"忌: {b_raw}", f_evt, 560, dummy_draw)
    box_inner_h = 40
    box_inner_h += len(lines_jp) * 45
    box_inner_h += 10
    box_inner_h += len(lines_cn) * 40
    box_inner_h += 40
    box_inner_h += 40
    box_inner_h += len(good_lines) * 45
    box_inner_h += 20
    box_inner_h += len(bad_lines) * 45
    box_inner_h += 40
    box_y = 425
    H = box_y + box_inner_h + 180
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 120], fill=C_PINK_MAIN)
    avatar = await get_avatar(user_id, user_name, bot, group_id)
    img.paste(avatar, (325, 80), avatar)
    draw.ellipse([325, 80, 475, 230], outline="white", width=5)
    title_txt = f"<{data['title']}>"
    w_title = draw.textlength(title_txt, font=f_title)
    draw.text(((W - w_title) / 2, 250), title_txt, font=f_title, fill=C_PINK_DARK)
    info_txt = f"等级 Lv.{data['lvl']} | 运势 {data['luck']}"
    w_info = draw.textlength(info_txt, font=f_info)
    draw.text(((W - w_info) / 2, 300), info_txt, font=f_info, fill=C_TEXT_SUB)
    pc_txt = f"签到奖励: +{data.get('pc_add', 0)} PC"
    w_pc = draw.textlength(pc_txt, font=f_pc)
    draw.rounded_rectangle([(W - w_pc) / 2 - 30, 335, (W + w_pc) / 2 + 30, 385], radius=25, fill="white", outline=C_PINK_MAIN, width=3)
    draw.text(((W - w_pc) / 2, 341), pc_txt, font=f_pc, fill=C_PINK_DARK)
    draw.rounded_rectangle([60, box_y, W - 60, box_y + box_inner_h], radius=20, fill=C_SURFACE, outline=C_BORDER, width=2)
    curr_y = box_y + 40
    for line in lines_jp:
        w_l = draw.textlength(line, font=f_jp)
        draw.text(((W - w_l) / 2, curr_y), line, font=f_jp, fill=C_TEXT_MAIN)
        curr_y += 45
    curr_y += 10
    for line in lines_cn:
        w_l = draw.textlength(line, font=f_cn)
        draw.text(((W - w_l) / 2, curr_y), line, font=f_cn, fill=C_TEXT_SUB)
        curr_y += 40
    curr_y += 20
    draw.line([100, curr_y, W - 100, curr_y], fill=C_BORDER, width=2)
    curr_y += 20
    draw_dot(draw, 100, curr_y + 15, C_GREEN)
    for line in good_lines:
        draw.text((130, curr_y), line, font=f_evt, fill=C_GREEN)
        curr_y += 45
    curr_y += 20
    draw_dot(draw, 100, curr_y + 15, C_RED)
    for line in bad_lines:
        draw.text((130, curr_y), line, font=f_evt, fill=C_RED)
        curr_y += 45
    bar_y = box_y + box_inner_h + 40
    needed = (data['lvl'] + 1) * 100
    pct = min(1.0, data['xp'] / needed)
    draw.text((50, bar_y), f"经验值: {data['xp']} / {needed}", font=load_font(24), fill=C_TEXT_SUB)
    draw.rounded_rectangle([50, bar_y + 40, W - 50, bar_y + 70], radius=15, fill="#eee")
    if pct > 0:
        draw.rounded_rectangle([50, bar_y + 40, 50 + int((W - 100) * pct), bar_y + 70], radius=15, fill=C_PINK_MAIN)
    url_txt = "Mizuki Economy | list.mizuki.top"
    w_url = draw.textlength(url_txt, font=load_font(20))
    draw.text(((W - w_url) / 2, H - 40), url_txt, font=load_font(20), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_profile_card(user_id, name, data, bot=None, group_id=None):
    W, H = 800, 1000
    tc = THEME_COLORS.get(data.get("theme", 0), THEME_COLORS[0])
    bg_path = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "backgrounds" / f"{user_id}.png"
    if bg_path.exists():
        try:
            bg_img = Image.open(bg_path).convert("RGBA").resize((W, H), Image.LANCZOS)
            overlay = Image.new("RGBA", (W, H), (255, 255, 255, 210) if data.get("theme", 0) != 4 else (30, 30, 35, 210))
            img = Image.alpha_composite(bg_img, overlay)
            draw = ImageDraw.Draw(img)
        except:
            img = Image.new("RGBA", (W, H), tc["bg"])
            draw = ImageDraw.Draw(img)
    else:
        img = Image.new("RGBA", (W, H), tc["bg"])
        draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 180], fill=tc["top"])
    draw.text((50, 60), "个人中心", font=load_font(60), fill="white")
    avatar = await get_avatar(user_id, name, bot, group_id)
    img.paste(avatar, (325, 105), avatar)
    draw.ellipse([325, 105, 475, 255], outline="white", width=5)
    f_name = load_font(48)
    name_txt = f"{name} (Lv.{data['lvl']})"
    name_w = draw.textlength(name_txt, font=f_name)
    draw.text(((W - name_w) / 2, 280), name_txt, font=f_name, fill=tc["text"])
    reg_text = f"注册时间: {data['reg_date']}"
    f_reg = load_font(24)
    reg_w = draw.textlength(reg_text, font=f_reg)
    draw.rounded_rectangle([(W - reg_w) / 2 - 10, 350, (W + reg_w) / 2 + 10, 380], radius=10, fill="#eee" if data.get("theme", 0) != 4 else (60, 60, 70))
    draw.text(((W - reg_w) / 2, 352), reg_text, font=f_reg, fill=tc["sub"])
    total_prof = sum(data['prof'])
    info_text = f"三项打工总熟练度: {total_prof}"
    f_info = load_font(28)
    info_w = draw.textlength(info_text, font=f_info)
    draw.text(((W - info_w) / 2, 395), info_text, font=f_info, fill=tc["sub"])
    bal_text = f"{data['bal']} PC"
    f_bal = load_font(80)
    bal_w = draw.textlength(bal_text, font=f_bal)
    draw.text(((W - bal_w) / 2, 440), bal_text, font=f_bal, fill=tc["acc"])
    draw.line([100, 560, 700, 560], fill=C_BORDER if data.get("theme", 0) != 4 else (80, 80, 90), width=2)
    draw.text((320, 545), " 近期账单 ", font=load_font(32), fill=tc["text"], stroke_fill=tc["bg"], stroke_width=10)
    curr_y = 620
    f_log = load_font(30)
    if not data['logs']:
        draw.text((300, 650), "暂无账单记录", font=f_log, fill=tc["sub"])
    else:
        for date_str, amount, desc in data['logs']:
            draw.text((80, curr_y), f"[{date_str}]", font=f_log, fill=tc["sub"])
            color = C_GREEN if amount >= 0 else C_RED
            amt_str = f"+{amount}" if amount > 0 else str(amount)
            draw.text((230, curr_y), amt_str, font=f_log, fill=color)
            if len(desc) > 13:
                desc = desc[:12] + "..."
            draw.text((350, curr_y), desc, font=f_log, fill=tc["text"])
            curr_y += 60
    url_txt = "Mizuki Economy | list.mizuki.top"
    f_url = load_font(20)
    w_url = draw.textlength(url_txt, font=f_url)
    draw.text(((W - w_url) / 2, 950), url_txt, font=f_url, fill=tc["sub"])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_work_card(name, job_name, res: dict):
    W = 800
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    f_det = load_font(30)
    msg_lines = wrap_text(f"事件: {res['msg']}", f_det, 600, dummy_draw)
    box_start_y = 260
    box_h = 40 + (len(msg_lines) * 45) + 20 + 90
    H = max(500, box_start_y + box_h + 60)
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 30, H], fill=C_PINK_MAIN)
    if job_name in ["汇总", "一键"]:
        title_txt = "一键打工结算报告"
    else:
        title_txt = f"打工结算报告 - {job_name}"
    draw.text((60, 40), title_txt, font=load_font(40), fill=C_TEXT_MAIN)
    draw.text((60, 100), f"执行者: {name}", font=load_font(28), fill=C_TEXT_SUB)
    s_text = "大成功" if res['status'] == "success" else "工伤"
    s_color = C_PINK_DARK if res['status'] == "success" else C_TEXT_SUB
    draw.text((60, 160), s_text, font=load_font(60), fill=s_color)
    if res['leveled']:
        draw.text((550, 170), "LEVEL UP", font=load_font(40), fill=C_PINK_MAIN)
    draw.rounded_rectangle([60, box_start_y, 740, box_start_y + box_h], radius=20, fill=C_SURFACE, outline=C_BORDER, width=2)
    text_y = box_start_y + 30
    for line in msg_lines:
        draw.text((90, text_y), line, font=f_det, fill=C_TEXT_MAIN)
        text_y += 45
    text_y += 15
    reward_val = res.get('reward', 0)
    reward_str = f"+{reward_val}" if reward_val >= 0 else str(reward_val)
    if res['status'] == "success":
        draw.text((90, text_y), f"收益: {reward_str} PC | 经验: +{res['xp_add']}", font=f_det, fill=C_GREEN)
    else:
        draw.text((90, text_y), f"收益: {reward_str} PC | 经验: +{res['xp_add']}", font=f_det, fill=C_RED)
    text_y += 50
    cost_text = res.get('cost', '未知')
    draw.text((90, text_y), f"体力: -{cost_text} (剩余 {res['stamina']})", font=f_det, fill=C_TEXT_SUB)
    draw.text((60, H - 40), "Mizuki Economy | list.mizuki.top", font=load_font(20), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_shop_menu(bal, lvl):
    categories = {1: "补给物资", 2: "效率增益", 3: "永久工具", 4: "外观定制"}
    W = 1000
    temp_y = 300
    for c_type in categories.keys():
        temp_y += 100
        items_count = sum(1 for i in SHOP_ITEMS if i.get('type') == c_type)
        rows = (items_count + 1) // 2
        temp_y += rows * 180 + 50
    H = max(1000, temp_y + 120)
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 250], fill=C_PINK_MAIN)
    draw.text((60, 80), "经济商城", font=load_font(80), fill="white")
    draw.text((60, 180), f"当前余额: {bal} PC | 等级: Lv.{lvl}", font=load_font(36), fill="white")
    curr_y = 300
    f_cat = load_font(48)
    f_item_name = load_font(32)
    f_item_desc = load_font(24)
    f_price = load_font(36)
    for c_type, c_name in categories.items():
        draw.rounded_rectangle([40, curr_y, 300, curr_y + 60], radius=30, fill=C_PINK_DARK)
        draw.text((70, curr_y + 5), c_name, font=f_cat, fill="white")
        curr_y += 100
        items = [i for i in SHOP_ITEMS if i['type'] == c_type]
        for idx, item in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = 40 + col * 480
            y = curr_y + row * 180
            is_locked = lvl < item['lv']
            bg_color = "#eee" if is_locked else "white"
            stroke = C_BORDER if is_locked else C_PINK_MAIN
            draw.rounded_rectangle([x, y, x + 440, y + 160], radius=20, fill=bg_color, outline=stroke, width=2)
            name_color = C_TEXT_SUB if is_locked else C_TEXT_MAIN
            draw.text((x + 20, y + 20), f"#{item['id']} {item['name']}", font=f_item_name, fill=name_color)
            draw.text((x + 20, y + 70), item['desc'], font=f_item_desc, fill=C_TEXT_SUB)
            price_color = C_TEXT_SUB if is_locked else C_PINK_DARK
            draw.text((x + 20, y + 110), f"{item['price']} PC", font=f_price, fill=price_color)
            if is_locked:
                draw.text((x + 250, y + 115), f"Lv.{item['lv']}解锁", font=f_item_desc, fill=C_RED)
        rows = (len(items) + 1) // 2
        curr_y += rows * 180 + 50
    footer_txt = "发送 购买 编号 即可消费 | list.mizuki.top"
    f_footer = load_font(30)
    fw = draw.textlength(footer_txt, font=f_footer)
    draw.text(((W - fw) / 2, curr_y + 20), footer_txt, font=f_footer, fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_inventory_card(name, bal, lvl, items):
    rows = math.ceil(len(items) / 2) if items else 1
    W = 1000
    H = max(800, 350 + rows * 180 + 100)
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 250], fill=C_PINK_MAIN)
    draw.text((60, 60), f"{name} 的背包", font=load_font(70), fill="white")
    draw.text((60, 160), f"余额: {bal} PC | 等级: Lv.{lvl}", font=load_font(36), fill="white")
    curr_y = 300
    if not items:
        f_empty = load_font(40)
        w_empty = draw.textlength("背包空空如也...", font=f_empty)
        draw.text(((W - w_empty) / 2, curr_y + 100), "背包空空如也...", font=f_empty, fill=C_TEXT_SUB)
    else:
        f_item_name = load_font(36)
        f_item_desc = load_font(26)
        f_qty = load_font(40)
        for idx, item_data in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = 40 + col * 480
            y = curr_y + row * 180
            info = item_data["info"]
            qty = item_data["qty"]
            draw.rounded_rectangle([x, y, x + 440, y + 160], radius=20, fill="white", outline=C_PINK_MAIN, width=2)
            draw.text((x + 30, y + 25), f"#{info['id']} {info['name']}", font=f_item_name, fill=C_TEXT_MAIN)
            draw.text((x + 30, y + 90), info['desc'], font=f_item_desc, fill=C_TEXT_SUB)
            qty_txt = f"x{qty}"
            w_qty = draw.textlength(qty_txt, font=f_qty)
            draw.rounded_rectangle([x + 400 - w_qty, y + 20, x + 430, y + 70], radius=10, fill=C_PINK_DARK)
            draw.text((x + 415 - w_qty, y + 20), qty_txt, font=f_qty, fill="white")
    draw.text((350, H - 60), "发送 使用 编号 消耗物品 | list.mizuki.top", font=load_font(26), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

STAR_BORDER = {
    1: (180, 180, 180), 2: (100, 200, 100), 3: (100, 150, 255),
    4: (220, 160, 255), 5: (255, 215, 0)
}

async def download_card_image(card_info: dict, proxy_url: str = None) -> bytes | None:
    from pathlib import Path
    import re
    def sanitize(name):
        return re.sub(r'[\\/*?:"<>|]', "", str(name))
    
    asset_name = card_info.get("asset", "")
    rarity_label = card_info.get("rarity_label", "")
    prefix = card_info.get("title", "")
    char_name = card_info.get("char_name", "")
    
    cards_dir = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    
    # Check by user's crawl_cards.py naming convention: cards/{char_name}/[{rarity}][{prefix}]_{char_name}_特训前.webp
    if rarity_label and prefix and char_name:
        safe_name = sanitize(f"[{rarity_label}][{prefix}]_{char_name}")
        local_path = cards_dir / char_name / f"{safe_name}_特训前.webp"
        if local_path.exists():
            return local_path.read_bytes()
            
    for ext in ["webp", "png"]:
        local_path = cards_dir / f"{asset_name}_normal.{ext}"
        if local_path.exists():
            return local_path.read_bytes()
    
    sources = []
    base_paths = [
        f"character/member/{asset_name}/card_normal.webp",
        f"character/member/{asset_name}/card_normal.png"
    ]
    for bp in base_paths:
        if proxy_url:
            sources.append((f"{proxy_url}/api-assets/sekai-jp-assets/{bp}", bp.split(".")[-1]))
        sources.append((f"{PJSK_LOCAL_PROXY}/api-assets/sekai-jp-assets/{bp}", bp.split(".")[-1]))
        sources.append((f"{PJSK_PROXY_URL}/api-assets/sekai-jp-assets/{bp}", bp.split(".")[-1]))
        sources.append((f"https://storage.sekai.best/sekai-jp-assets/{bp}", bp.split(".")[-1]))

    for url, ext in sources:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200 and len(resp.content) > 1000:
                    local_path = cards_dir / f"{asset_name}_normal.{ext}"
                    local_path.write_bytes(resp.content)
                    return resp.content
        except Exception:
            continue
    return None

async def draw_card_image(card_info: dict, char_name: str, rarity_label: str, card_img_bytes: bytes | None = None) -> bytes:
    W, H = 400, 430
    star = card_info.get("star", 1)
    border = STAR_BORDER.get(star, (180, 180, 180))
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, W - 4, H - 4], radius=16, outline=border, width=4)
    if card_img_bytes:
        try:
            cimg = Image.open(io.BytesIO(card_img_bytes)).convert("RGBA")
            cimg = ImageOps.fit(cimg, (360, 203), centering=(0.5, 0.5))
            img.paste(cimg, (20, 60))
        except Exception:
            draw.rectangle([20, 60, 380, 263], fill=C_SURFACE)
    else:
        draw.rectangle([20, 60, 380, 263], fill=C_SURFACE)
        draw.text((120, 140), "暂无卡面", font=load_font(28), fill=C_TEXT_SUB)
    draw.text((20, 15), "*" * star, font=load_font(30), fill=border)
    title = card_info.get("title", "")
    if title:
        draw.text((20, 280), title, font=load_font(26), fill=C_TEXT_MAIN)
    draw.text((20, 320), f"{rarity_label} {char_name}", font=load_font(22), fill=C_TEXT_SUB)
    draw.line([(20, 365), (W - 20, 365)], fill=border, width=2)
    draw.text((20, 378), "Mizuki Economy", font=load_font(18), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_gacha_result(cards: list, card_images: dict) -> bytes:
    count = len(cards)
    if count == 1:
        c = cards[0]
        return await draw_card_image(c, c.get("char_name", ""), c.get("rarity_label", ""), card_images.get(c.get("asset", "")))
    W, H = 1000, 560
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.text((20, 15), "十连结果", font=load_font(36), fill=C_PINK_DARK)
    for i, card in enumerate(cards):
        col, row = i % 5, i // 5
        x, y = 20 + col * 195, 70 + row * 220
        single = await draw_card_image(card, card.get("char_name", ""), card.get("rarity_label", ""), card_images.get(card.get("asset", "")))
        cimg = Image.open(io.BytesIO(single)).convert("RGBA").resize((185, 199), Image.LANCZOS)
        img.paste(cimg, (x, y))
    star_counts = {}
    for c in cards:
        s = c.get("star", 1)
        star_counts[s] = star_counts.get(s, 0) + 1
    stats = " | ".join([f"{s}*{n}" for s, n in sorted(star_counts.items(), reverse=True)])
    draw.text((20, H - 40), stats, font=load_font(24), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

RANK_COLORS = {1: (255, 215, 0), 2: (192, 192, 192), 3: (205, 127, 50)}

async def draw_leaderboard_card(user_name: str, entries: list, my_rank: int = 0) -> bytes:
    W = 800
    show = entries[:20]
    row_h = 110
    header_h = 250
    H = header_h + len(show) * row_h + 100
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 160], fill=C_PINK_MAIN)
    draw.text((280, 40), "财富排行", font=load_font(50), fill="white")
    f_rank = load_font(36)
    f_name = load_font(28)
    f_info = load_font(22)
    f_small = load_font(20)
    curr_y = header_h
    for idx, e in enumerate(show):
        rank = e["rank"]
        bg = C_SURFACE
        rank_color = C_TEXT_MAIN
        if rank in RANK_COLORS:
            rank_color = RANK_COLORS[rank]
        draw.rounded_rectangle([40, curr_y, W - 40, curr_y + row_h - 10], radius=15, fill=bg, outline=C_BORDER, width=2)
        rank_label = f"#{rank}"
        draw.text((60, curr_y + 30), rank_label, font=f_rank, fill=rank_color)
        name_txt = e.get("name", "???")
        if len(name_txt) > 8:
            name_txt = name_txt[:7] + "..."
        draw.text((170, curr_y + 20), name_txt, font=f_name, fill=C_TEXT_MAIN)
        title = e.get("title", "")
        if title:
            t_txt = f"<{title}>"
            if len(t_txt) > 10:
                t_txt = t_txt[:9] + ">"
            draw.text((170, curr_y + 60), t_txt, font=f_info, fill=C_TEXT_SUB)
        bal_txt = f"{e.get('score', 0)} PC"
        w_bal = draw.textlength(bal_txt, font=f_rank)
        draw.text((W - 60 - w_bal, curr_y + 22), bal_txt, font=f_rank, fill=C_PINK_DARK)
        lvl_txt = f"Lv.{e.get('level', 1)}"
        w_lvl = draw.textlength(lvl_txt, font=f_small)
        draw.text((W - 60 - w_lvl, curr_y + 62), lvl_txt, font=f_small, fill=C_TEXT_SUB)
        curr_y += row_h
    if my_rank > 0:
        my_txt = f"你的排名: #{my_rank}"
    else:
        my_txt = "未上榜"
    w_my = draw.textlength(my_txt, font=load_font(28))
    draw.text(((W - w_my) / 2, H - 60), my_txt, font=load_font(28), fill=C_PINK_MAIN)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_achievement_card(user_name: str, achs: list) -> bytes:
    unlocked = [(a, ok) for a, ok in achs if ok]
    locked = [(a, ok) for a, ok in achs if not ok]
    total = len(achs)
    count_unlocked = len(unlocked)
    count_locked = len(locked)
    W = 800
    cols = 2
    rows_u = max(1, (count_unlocked + cols - 1) // cols)
    rows_l = max(1, (count_locked + cols - 1) // cols)
    card_h = 100
    gap = 15
    header_h = 200
    section_title_h = 50
    H = header_h + section_title_h + rows_u * (card_h + gap) + 30 + section_title_h + rows_l * (card_h + gap) + 80
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 140], fill=C_PINK_MAIN)
    draw.text((280, 30), "成就墙", font=load_font(50), fill="white")
    pct = int(count_unlocked / total * 100) if total else 0
    prog_w = 500
    prog_x = (W - prog_w) // 2
    prog_y = 160
    draw.text((prog_x, prog_y), f"{count_unlocked}/{total} ({pct}%)", font=load_font(26), fill=C_TEXT_MAIN)
    draw.rounded_rectangle([prog_x, prog_y + 35, prog_x + prog_w, prog_y + 55], radius=10, fill="#eee")
    if pct > 0:
        draw.rounded_rectangle([prog_x, prog_y + 35, prog_x + int(prog_w * pct / 100), prog_y + 55], radius=10, fill=C_PINK_MAIN)
    curr_y = header_h
    f_sec = load_font(32)
    f_name = load_font(26)
    f_desc = load_font(20)
    f_reward = load_font(22)
    def _draw_section(title, items, start_y):
        y = start_y
        draw.text((50, y), title, font=f_sec, fill=C_PINK_DARK)
        y += section_title_h
        for idx, (a, ok) in enumerate(items):
            col = idx % cols
            row = idx // cols
            x = 50 + col * 365
            cy = y + row * (card_h + gap)
            bg = "white" if ok else "#f0f0f0"
            border = C_PINK_MAIN if ok else C_TEXT_SUB
            draw.rounded_rectangle([x, cy, x + 340, cy + card_h], radius=12, fill=bg, outline=border, width=2)
            icon = "OK" if ok else "Lock"
            draw.text((x + 15, cy + 12), icon, font=load_font(24), fill=C_GREEN if ok else C_TEXT_SUB)
            name = a.get("name", "?")
            if len(name) > 8:
                name = name[:7] + "..."
            draw.text((x + 55, cy + 10), name, font=f_name, fill=C_TEXT_MAIN if ok else C_TEXT_SUB)
            desc = a.get("desc", "")
            if len(desc) > 14:
                desc = desc[:13] + "..."
            draw.text((x + 55, cy + 45), desc, font=f_desc, fill=C_TEXT_SUB)
            reward_txt = f"+{a.get('reward', 0)}PC"
            draw.text((x + 260, cy + 65), reward_txt, font=f_reward, fill=C_GREEN if ok else C_TEXT_SUB)
        return y + rows_u * (card_h + gap) if items else y
    end_y = _draw_section(f"已解锁 ({count_unlocked})", unlocked, curr_y)
    curr_y = end_y + 20
    _draw_section(f"未解锁 ({count_locked})", locked, curr_y)
    url_txt = "Mizuki Economy | list.mizuki.top"
    w_url = draw.textlength(url_txt, font=load_font(20))
    draw.text(((W - w_url) / 2, H - 40), url_txt, font=load_font(20), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_calendar_card(user_id: int, user_name: str, sign_dates: set, streak: int) -> bytes:
    today = datetime.date.today()
    year, month = today.year, today.month
    first_day = datetime.date(year, month, 1)
    import calendar as _cal
    days_in_month = _cal.monthrange(year, month)[1]
    start_weekday = first_day.weekday()
    W = 700
    cell = 80
    grid_rows = (start_weekday + days_in_month + 6) // 7
    header_h = 220
    H = header_h + grid_rows * cell + 140
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 130], fill=C_PINK_MAIN)
    draw.text((230, 25), "签到日历", font=load_font(46), fill="white")
    avatar = await get_avatar(user_id, user_name)
    avatar_sm = avatar.resize((80, 80), Image.LANCZOS)
    img.paste(avatar_sm, (50, 130), avatar_sm)
    f_info = load_font(26)
    draw.text((150, 135), f"{user_name}", font=load_font(30), fill=C_TEXT_MAIN)
    streak_txt = f"连签 {streak} 天"
    draw.text((150, 175), streak_txt, font=f_info, fill=C_PINK_DARK)
    this_month_count = sum(1 for d in sign_dates if d.year == year and d.month == month)
    draw.text((400, 175), f"本月 {this_month_count} 天", font=f_info, fill=C_TEXT_SUB)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    grid_y = header_h
    f_wd = load_font(24)
    grid_x_start = (W - 7 * cell) // 2
    for i, wd in enumerate(weekdays):
        cx = grid_x_start + i * cell + cell // 2
        wt = draw.textlength(wd, font=f_wd)
        draw.text((cx - wt // 2, grid_y), wd, font=f_wd, fill=C_TEXT_SUB)
    grid_y += 35
    f_day = load_font(28)
    for day in range(1, days_in_month + 1):
        idx = start_weekday + day - 1
        col = idx % 7
        row = idx // 7
        cx = grid_x_start + col * cell
        cy = grid_y + row * cell
        d = datetime.date(year, month, day)
        is_signed = d in sign_dates
        is_today = d == today
        if is_signed:
            draw.rounded_rectangle([cx + 5, cy + 5, cx + cell - 5, cy + cell - 5], radius=12, fill=C_PINK_MAIN)
            draw.text((cx + 28, cy + 18), str(day), font=f_day, fill="white")
        elif is_today:
            draw.rounded_rectangle([cx + 5, cy + 5, cx + cell - 5, cy + cell - 5], radius=12, fill="white", outline=C_PINK_DARK, width=3)
            draw.text((cx + 28, cy + 18), str(day), font=f_day, fill=C_PINK_DARK)
        else:
            draw.text((cx + 28, cy + 18), str(day), font=f_day, fill=C_TEXT_SUB)
    url_txt = "Mizuki Economy | list.mizuki.top"
    w_url = draw.textlength(url_txt, font=load_font(20))
    draw.text(((W - w_url) / 2, H - 40), url_txt, font=load_font(20), fill=C_TEXT_SUB)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_stock_chart(stock_list: list, prices: dict, history: dict, event_desc: str = "") -> bytes:
    W = 1000
    row_h = 130
    header_h = 240
    if event_desc:
        header_h += 80
    H = header_h + len(stock_list) * row_h + 100
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    
    # Draw header background
    draw.rectangle([0, 0, W, 180], fill=C_PINK_MAIN)
    draw.text((60, 50), "25时证券交易所", font=load_font(60), fill="white")
    
    # Event box
    curr_y = 190
    if event_desc:
        draw.rounded_rectangle([40, curr_y, W - 40, curr_y + 60], radius=10, fill=(255, 235, 235), outline=C_RED, width=2)
        draw.text((60, curr_y + 16), event_desc, font=load_font(24), fill=C_RED)
        curr_y += 80
        
    f_title = load_font(32)
    f_price = load_font(38)
    f_change = load_font(26)
    f_small = load_font(20)
    
    for idx, s in enumerate(stock_list):
        sid = s["id"]
        s_price = prices[sid]["price"]
        s_change = prices[sid]["change"]
        
        # Determine change color
        if s_change > 0:
            change_txt = f"+{s_change}%"
            change_color = C_RED
        elif s_change < 0:
            change_txt = f"{s_change}%"
            change_color = C_GREEN
        else:
            change_txt = "0%"
            change_color = C_TEXT_SUB
            
        draw.rounded_rectangle([40, curr_y, W - 40, curr_y + row_h - 15], radius=15, fill="white", outline=C_BORDER, width=2)
        
        # Stock Info
        draw.text((70, curr_y + 20), f"[{sid}] {s['name']}", font=f_title, fill=C_TEXT_MAIN)
        draw.text((70, curr_y + 65), f"基准价: {s['base_price']} PC", font=f_small, fill=C_TEXT_SUB)
        
        # Current Price & Change
        draw.text((440, curr_y + 18), f"{s_price} PC", font=f_price, fill=change_color)
        draw.text((440, curr_y + 65), change_txt, font=f_change, fill=change_color)
        
        # Line Sparkline Chart
        stock_hist = history.get(sid, [])
        if len(stock_hist) >= 2:
            hist_prices = [p[1] for p in stock_hist]
            min_p = min(hist_prices)
            max_p = max(hist_prices)
            p_range = max_p - min_p if max_p != min_p else 1.0
            
            graph_x = 650
            graph_w = 280
            graph_y = curr_y + 15
            graph_h = 75
            
            points = []
            for i, (date_str, val) in enumerate(stock_hist):
                px = graph_x + i * (graph_w / (len(stock_hist) - 1))
                py = (graph_y + graph_h) - ((val - min_p) / p_range) * (graph_h - 10)
                points.append((px, py))
                
            # Draw line segments
            for i in range(len(points) - 1):
                draw.line([points[i], points[i+1]], fill=change_color, width=3)
                
            # Draw points and labels
            for i, (px, py) in enumerate(points):
                r = 4
                draw.ellipse([px - r, py - r, px + r, py + r], fill=change_color)
                # Label first and last dates
                if i == 0 or i == len(points) - 1:
                    d_txt = stock_hist[i][0]
                    dw = draw.textlength(d_txt, font=f_small)
                    draw.text((px - dw / 2, graph_y + graph_h + 3), d_txt, font=f_small, fill=C_TEXT_SUB)
                    
        curr_y += row_h
        
    footer = "股市有风险，入市需谨慎 | 买入 股票代码 数量"
    fw = draw.textlength(footer, font=load_font(24))
    draw.text(((W - fw) / 2, H - 45), footer, font=load_font(24), fill=C_TEXT_SUB)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

async def draw_card_collection(user_name: str, cards_with_info: list) -> bytes:
    # Sort cards by star reverse (highest star first)
    cards_with_info = sorted(cards_with_info, key=lambda x: x["info"].get("star", 0), reverse=True)
    
    W = 1000
    col_w = 175
    row_h = 240
    cols = 5
    rows = math.ceil(len(cards_with_info) / cols) if cards_with_info else 1
    
    header_h = 240
    H = header_h + rows * row_h + 100
    img = Image.new("RGBA", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    
    # Draw header
    draw.rectangle([0, 0, W, 180], fill=C_PINK_MAIN)
    draw.text((60, 50), f"{user_name} 的卡牌馆藏", font=load_font(50), fill="white")
    
    total_cards = sum(c["qty"] for c in cards_with_info)
    unique_cards = len(cards_with_info)
    draw.text((60, 130), f"共收集了 {unique_cards} 种，共 {total_cards} 张卡牌", font=load_font(28), fill="white")
    
    f_name = load_font(24)
    f_star = load_font(22)
    f_qty = load_font(20)
    
    grid_x_start = (W - cols * col_w) // 2
    curr_y = header_h
    
    for idx, item in enumerate(cards_with_info):
        col = idx % cols
        row = idx // cols
        x = grid_x_start + col * col_w
        y = curr_y + row * row_h
        
        info = item["info"]
        qty = item["qty"]
        star = info.get("star", 1)
        char_name = info.get("char_name", "其他")
        prefix = info.get("prefix", "card")
        asset_name = info.get("assetbundleName", "")
        
        # Load thumbnail
        from pathlib import Path
        import re
        def sanitize(name):
            return re.sub(r'[\\/*?:"<>|]', "", str(name))
            
        rarity_val = RARITY_MAP.get(info.get("cardRarityType"), {})
        rarity_str = rarity_val.get("label", "?") if isinstance(rarity_val, dict) else rarity_val
        safe_name = sanitize(f"[{rarity_str}][{prefix}]_{char_name}")
        
        # Try to find the thumbnail image (try normal first, then trained)
        cards_dir = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "cards"
        thumb_path = cards_dir / char_name / f"{safe_name}_特训前_thumb.webp"
        if not thumb_path.exists() and star >= 3:
            thumb_path = cards_dir / char_name / f"{safe_name}_特训后_thumb.webp"
            
        border_color = STAR_BORDER.get(star, (150, 150, 150))
        
        # Draw card container
        draw.rounded_rectangle([x + 5, y + 5, x + col_w - 5, y + row_h - 10], radius=15, fill="white", outline=C_BORDER, width=2)
        
        # Draw thumbnail image if found
        thumb_drawn = False
        if thumb_path.exists():
            try:
                t_img = Image.open(thumb_path).convert("RGBA").resize((130, 130), Image.LANCZOS)
                img.paste(t_img, (x + 22, y + 15), t_img)
                draw.rectangle([x + 22, y + 15, x + 152, y + 145], outline=border_color, width=3)
                thumb_drawn = True
            except:
                pass
                
        if not thumb_drawn:
            # Fallback placeholder block
            draw.rounded_rectangle([x + 22, y + 15, x + 152, y + 145], radius=10, fill=border_color)
            fallback_txt = prefix[:8]
            fw = draw.textlength(fallback_txt, font=f_qty)
            draw.text((x + 87 - fw / 2, y + 70), fallback_txt, font=f_qty, fill="white")
            
        # Draw quantity tag
        qty_txt = f"x{qty}"
        qw = draw.textlength(qty_txt, font=f_qty)
        draw.rounded_rectangle([x + 115 - qw, y + 20, x + 145, y + 50], radius=8, fill=C_PINK_DARK)
        draw.text((x + 130 - qw, y + 23), qty_txt, font=f_qty, fill="white")
        
        # Draw name & star
        name_txt = char_name[:6]
        nw = draw.textlength(name_txt, font=f_name)
        draw.text((x + col_w / 2 - nw / 2, y + 155), name_txt, font=f_name, fill=C_TEXT_MAIN)
        
        star_txt = "★" * star
        sw = draw.textlength(star_txt, font=f_star)
        draw.text((x + col_w / 2 - sw / 2, y + 185), star_txt, font=f_star, fill=(255, 180, 0))
        
    footer = "Mizuki Economy | list.mizuki.top"
    fw = draw.textlength(footer, font=load_font(24))
    draw.text(((W - fw) / 2, H - 45), footer, font=load_font(24), fill=C_TEXT_SUB)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
