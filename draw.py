# mizuki_econmy/draw.py
import io
import httpx
import math
import time
from PIL import Image, ImageDraw, ImageFont
from .const import SHOP_ITEMS

# 瑞希正统可爱粉配色
C_PINK_BG = (255, 240, 245)
C_PINK_MAIN = (228, 164, 190)
C_PINK_DARK = (219, 112, 147)
C_TEXT_MAIN = (80, 80, 80)
C_TEXT_SUB = (150, 150, 150)
C_GREEN = (60, 179, 113)
C_RED = (205, 92, 92)

def load_font(size):
    try: return ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", size)
    except: 
        try: return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
        except: return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    lines = []
    if not text: return lines
    current_line = ""
    for char in text:
        if draw.textlength(current_line + char, font=font) <= max_width:
            current_line += char
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)
    return lines

async def get_avatar(user_id, name="User"):
    url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640&t={int(time.time())}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=3)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize((150, 150))
                mask = Image.new("L", (150, 150), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, 150, 150), fill=255)
                img.putalpha(mask)
                return img
    except:
        pass
    
    img = Image.new("RGBA", (150, 150), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, 150, 150), fill=C_PINK_MAIN)
    char = name[0] if name else "U"
    f = load_font(80)
    w = draw.textlength(char, font=f)
    draw.text(((150-w)/2, 20), char, font=f, fill="white")
    return img

def draw_dot(draw, x, y, color):
    r = 8
    draw.ellipse([x-r, y-r, x+r, y+r], fill=color)

# --- 1. 签到卡片 (统一白框大收纳排版，绝出错位) ---
async def draw_sign_card(user_id, user_name, data):
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
    
    good_lines = wrap_text(f"宜：{g_raw}", f_evt, 560, dummy_draw)
    bad_lines = wrap_text(f"忌：{b_raw}", f_evt, 560, dummy_draw)
    
    # 精密计算唯一白框的内部高度
    box_inner_h = 40 # 顶部内边距
    box_inner_h += len(lines_jp) * 45
    box_inner_h += 10 # 中日文间距
    box_inner_h += len(lines_cn) * 40
    box_inner_h += 40 # 分割线上方间距
    box_inner_h += 40 # 分割线下方间距
    box_inner_h += len(good_lines) * 45
    box_inner_h += 20 # 宜和忌之间的间距
    box_inner_h += len(bad_lines) * 45
    box_inner_h += 40 # 底部内边距
    
    box_y = 440 # 白框起始Y坐标
    H = box_y + box_inner_h + 180 # 预留底部经验条和水印空间
    
    img = Image.new("RGBA", (W, H), C_PINK_BG)
    draw = ImageDraw.Draw(img)
    
    # 顶部粉色圆弧 Header
    draw.rectangle([0, 0, W, 120], fill=C_PINK_MAIN)
    draw.ellipse([-50, 80, W+50, 200], fill=C_PINK_MAIN)
    draw.text((320, 20), "今日运势", font=load_font(40), fill="white")
    
    # 头像
    avatar = await get_avatar(user_id, user_name)
    img.paste(avatar, (325, 80), avatar)
    draw.ellipse([325, 80, 475, 230], outline="white", width=5)
    
    # 称号与信息
    title_txt = f"<{data['title']}>"
    w_title = draw.textlength(title_txt, font=f_title)
    draw.text(((W-w_title)/2, 250), title_txt, font=f_title, fill=C_PINK_DARK)
    
    info_txt = f"等级 Lv.{data['lvl']}   |   运势 {data['luck']}"
    w_info = draw.textlength(info_txt, font=f_info)
    draw.text(((W-w_info)/2, 310), info_txt, font=f_info, fill=C_TEXT_SUB)
    
    # 🌟 修复乱码方块：去除了 Emoji 符号
    pc_txt = f"签到奖励: +{data.get('pc_add', 0)} PC"
    w_pc = draw.textlength(pc_txt, font=f_pc)
    draw.rounded_rectangle([(W-w_pc)/2 - 30, 360, (W+w_pc)/2 + 30, 410], radius=25, fill="white", outline=C_PINK_MAIN, width=3)
    draw.text(((W-w_pc)/2, 368), pc_txt, font=f_pc, fill=C_PINK_DARK)
    
    # 绘制唯一大白框
    draw.rounded_rectangle([60, box_y, W-60, box_y + box_inner_h], radius=25, fill="white")
    
    # 在白框内部逐行渲染内容
    curr_y = box_y + 40
    for line in lines_jp:
        w_l = draw.textlength(line, font=f_jp)
        draw.text(((W-w_l)/2, curr_y), line, font=f_jp, fill=C_TEXT_MAIN)
        curr_y += 45
        
    curr_y += 10
    for line in lines_cn:
        w_l = draw.textlength(line, font=f_cn)
        draw.text(((W-w_l)/2, curr_y), line, font=f_cn, fill=C_TEXT_SUB)
        curr_y += 40
        
    # 分割线
    curr_y += 20
    draw.line([100, curr_y, W-100, curr_y], fill="#ffe4e1", width=2)
    curr_y += 20
    
    # 宜
    draw_dot(draw, 100, curr_y + 15, C_GREEN)
    for line in good_lines:
        draw.text((130, curr_y), line, font=f_evt, fill=C_GREEN)
        curr_y += 45
        
    curr_y += 20
    
    # 忌
    draw_dot(draw, 100, curr_y + 15, C_RED)
    for line in bad_lines:
        draw.text((130, curr_y), line, font=f_evt, fill=C_RED)
        curr_y += 45
        
    # 底部经验进度条
    bar_y = box_y + box_inner_h + 40
    needed = (data['lvl'] + 1) * 100
    pct = min(1.0, data['xp'] / needed)
    
    draw.text((50, bar_y), f"经验值: {data['xp']} / {needed}", font=load_font(24), fill=C_TEXT_SUB)
    draw.rounded_rectangle([50, bar_y + 40, W-50, bar_y + 70], radius=15, fill="#eee")
    if pct > 0:
        draw.rounded_rectangle([50, bar_y + 40, 50+int((W-100)*pct), bar_y + 70], radius=15, fill=C_PINK_MAIN)
        
    # 底部水印
    url_txt = "Mizuki Economy | list.mizuki.top"
    w_url = draw.textlength(url_txt, font=load_font(20))
    draw.text(((W-w_url)/2, H-40), url_txt, font=load_font(20), fill="#b0b0b0")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# --- 2. 个人中心 ---
async def draw_profile_card(user_id, name, data):
    W, H = 800, 1000
    theme_colors = {
        0: {"bg": (255, 250, 252), "top": C_PINK_MAIN, "text": C_TEXT_MAIN, "sub": C_TEXT_SUB, "acc": C_PINK_DARK},
        401: {"bg": (250, 252, 255), "top": (176, 196, 222), "text": (60, 60, 60), "sub": (120, 120, 120), "acc": (100, 149, 237)},
        403: {"bg": (250, 245, 255), "top": (147, 112, 219), "text": (50, 40, 70), "sub": (130, 120, 150), "acc": (138, 43, 226)},
        405: {"bg": (245, 255, 250), "top": (102, 205, 170), "text": (40, 70, 60), "sub": (120, 150, 140), "acc": (46, 139, 87)},
        407: {"bg": (20, 20, 25), "top": (40, 40, 50), "text": (220, 220, 230), "sub": (150, 150, 160), "acc": (200, 180, 255)},
        410: {"bg": (255, 250, 240), "top": (218, 165, 32), "text": (80, 70, 40), "sub": (180, 150, 100), "acc": (255, 140, 0)}
    }
    tc = theme_colors.get(data.get("theme", 0), theme_colors[0])
    
    img = Image.new("RGBA", (W, H), tc["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 180], fill=tc["top"])
    draw.text((50, 60), "个人中心", font=load_font(60), fill="white")
    
    avatar = await get_avatar(user_id, name)
    img.paste(avatar, (325, 105), avatar)
    draw.ellipse([325, 105, 475, 255], outline="white", width=5)
    
    f_name = load_font(48)
    name_txt = f"{name} (Lv.{data['lvl']})" 
    name_w = draw.textlength(name_txt, font=f_name)
    draw.text(((W-name_w)/2, 280), name_txt, font=f_name, fill=tc["text"])
    
    reg_text = f"注册时间: {data['reg_date']}"
    f_reg = load_font(24)
    reg_w = draw.textlength(reg_text, font=f_reg)
    box_color = (60,60,70) if data.get("theme",0) == 407 else "#eee"
    draw.rounded_rectangle([(W-reg_w)/2-10, 350, (W+reg_w)/2+10, 380], radius=10, fill=box_color)
    draw.text(((W-reg_w)/2, 352), reg_text, font=f_reg, fill=tc["sub"])
    
    total_prof = sum(data['prof'])
    info_text = f"三项打工总熟练度: {total_prof}"
    f_info = load_font(28)
    info_w = draw.textlength(info_text, font=f_info)
    draw.text(((W-info_w)/2, 395), info_text, font=f_info, fill=tc["sub"])
    
    bal_text = f"{data['bal']} PC"
    f_bal = load_font(80)
    bal_w = draw.textlength(bal_text, font=f_bal)
    draw.text(((W-bal_w)/2, 440), bal_text, font=f_bal, fill=tc["acc"])
    
    line_color = (60,60,70) if data.get("theme",0) == 407 else "#ddd"
    draw.line([100, 560, 700, 560], fill=line_color, width=2)
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
            if len(desc) > 13: desc = desc[:12] + "..."
            draw.text((350, curr_y), desc, font=f_log, fill=tc["text"])
            curr_y += 60
            
    url_txt = "Mizuki Economy | list.mizuki.top"
    f_url = load_font(20)
    w_url = draw.textlength(url_txt, font=f_url)
    draw.text(((W-w_url)/2, 950), url_txt, font=f_url, fill=tc["sub"])
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# --- 3. 打工结算 (Mizuki 可爱粉色恢复版) ---
async def draw_work_card(name, job_name, res: dict):
    W = 800
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    f_det = load_font(30)
    
    msg_lines = wrap_text(f"事件: {res['msg']}", f_det, 600, dummy_draw) 
    
    box_start_y = 260
    box_h = 40 + (len(msg_lines) * 45) + 20 + 90
    H = max(500, box_start_y + box_h + 60)
    
    img = Image.new("RGBA", (W, H), "white")
    draw = ImageDraw.Draw(img)
    
    # 左侧粉色装饰条
    draw.rectangle([0, 0, 30, H], fill=C_PINK_MAIN)
    
    # 🌟 修复标题：针对一键打工进行更优雅的标题呈现
    if job_name in ["汇总", "一键"]:
        title_txt = "一键打工结算报告"
    else:
        title_txt = f"打工结算报告 - {job_name}"
        
    draw.text((60, 40), title_txt, font=load_font(40), fill=C_TEXT_MAIN)
    draw.text((60, 100), f"执行者: {name}", font=load_font(28), fill=C_TEXT_SUB)
    
    s_text = "大成功!" if res['status'] == "success" else "工伤..."
    s_color = C_PINK_DARK if res['status'] == "success" else (150, 150, 150)
    draw.text((60, 160), s_text, font=load_font(60), fill=s_color)
    
    if res['leveled']:
        draw.text((550, 170), "LEVEL UP!", font=load_font(40), fill="#FFD700")
        
    # 粉色浅底色的承载框
    draw.rounded_rectangle([60, box_start_y, 740, box_start_y + box_h], radius=20, fill="#fff0f5")
    
    text_y = box_start_y + 30
    for line in msg_lines:
        draw.text((90, text_y), line, font=f_det, fill=C_TEXT_MAIN)
        text_y += 45
        
    text_y += 15
    if res['status'] == "success":
        draw.text((90, text_y), f"收益: +{res['reward']} PC   |   经验: +{res['xp_add']}", font=f_det, fill=C_GREEN)
    else:
        draw.text((90, text_y), f"收益: {res['reward']} PC   |   经验: +{res['xp_add']}", font=f_det, fill=C_RED)
        
    text_y += 50
    cost_text = res.get('cost', '未知')
    draw.text((90, text_y), f"体力: -{cost_text} (剩余 {res['stamina']})", font=f_det, fill=C_TEXT_SUB)
    
    draw.text((60, H - 40), "Mizuki Economy | list.mizuki.top", font=load_font(20), fill="#ccc")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# --- 4. 商城全览图 ---
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
    
    img = Image.new("RGBA", (W, H), (255, 252, 254))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 250], fill=C_PINK_MAIN)
    draw.text((60, 80), "经济商城", font=load_font(80), fill="white")
    draw.text((60, 180), f"当前余额: {bal} PC  |  等级: Lv.{lvl}", font=load_font(36), fill="white")
    
    curr_y = 300
    f_cat = load_font(48)
    f_item_name = load_font(32)
    f_item_desc = load_font(24)
    f_price = load_font(36)
    
    for c_type, c_name in categories.items():
        draw.rounded_rectangle([40, curr_y, 300, curr_y+60], radius=30, fill=C_PINK_DARK)
        draw.text((70, curr_y+5), c_name, font=f_cat, fill="white")
        curr_y += 100
        items = [i for i in SHOP_ITEMS if i['type'] == c_type]
        for idx, item in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = 40 + col * 480
            y = curr_y + row * 180
            is_locked = lvl < item['lv']
            bg_color = "#eee" if is_locked else "white"
            stroke = C_TEXT_SUB if is_locked else C_PINK_MAIN
            draw.rounded_rectangle([x, y, x+440, y+160], radius=20, fill=bg_color, outline=stroke, width=2)
            name_color = (150, 150, 150) if is_locked else C_TEXT_MAIN
            draw.text((x+20, y+20), f"#{item['id']} {item['name']}", font=f_item_name, fill=name_color)
            draw.text((x+20, y+70), item['desc'], font=f_item_desc, fill=C_TEXT_SUB)
            price_color = (150, 150, 150) if is_locked else C_PINK_DARK
            draw.text((x+20, y+110), f"{item['price']} PC", font=f_price, fill=price_color)
            if is_locked:
                draw.text((x+250, y+115), f"Lv.{item['lv']}解锁", font=f_item_desc, fill="red")
        rows = (len(items) + 1) // 2
        curr_y += rows * 180 + 50
        
    footer_txt = "发送 '购买 [编号]' 即可消费 | list.mizuki.top"
    f_footer = load_font(30)
    fw = draw.textlength(footer_txt, font=f_footer)
    draw.text(((W - fw) / 2, curr_y + 20), footer_txt, font=f_footer, fill=C_TEXT_SUB)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# --- 5. 背包全览图 ---
async def draw_inventory_card(name, bal, lvl, items):
    rows = math.ceil(len(items) / 2) if items else 1
    W = 1000
    H = max(800, 350 + rows * 180 + 100)
    
    img = Image.new("RGBA", (W, H), (255, 250, 252))
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([0, 0, W, 250], fill=C_PINK_MAIN)
    draw.text((60, 60), f"{name} 的背包", font=load_font(70), fill="white")
    draw.text((60, 160), f"余额: {bal} PC  |  等级: Lv.{lvl}", font=load_font(36), fill="white")
    
    curr_y = 300
    if not items:
        f_empty = load_font(40)
        w_empty = draw.textlength("背包空空如也...", font=f_empty)
        draw.text(((W-w_empty)/2, curr_y + 100), "背包空空如也...", font=f_empty, fill=C_TEXT_SUB)
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
            
            draw.rounded_rectangle([x, y, x+440, y+160], radius=20, fill="white", outline=C_PINK_MAIN, width=3)
            
            draw.text((x+30, y+25), f"#{info['id']} {info['name']}", font=f_item_name, fill=C_TEXT_MAIN)
            draw.text((x+30, y+90), info['desc'], font=f_item_desc, fill=C_TEXT_SUB)
            
            qty_txt = f"x{qty}"
            w_qty = draw.textlength(qty_txt, font=f_qty)
            draw.rounded_rectangle([x+400-w_qty, y+20, x+430, y+70], radius=10, fill=C_PINK_DARK)
            draw.text((x+415-w_qty, y+20), qty_txt, font=f_qty, fill="white")

    draw.text((350, H-60), "发送 '使用 [编号]' 消耗物品 | list.mizuki.top", font=load_font(26), fill=C_TEXT_SUB)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()