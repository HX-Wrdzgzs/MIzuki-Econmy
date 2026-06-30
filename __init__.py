import sys
from pathlib import Path
plugins_dir = Path(__file__).parent.parent
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))

import random
import datetime
import aiomysql
import traceback
import asyncio
import string
import time
import httpx
from nonebot import on_command, get_plugin_config, get_driver, logger, get_bots
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.exception import FinishedException, RejectedException, PausedException

from .config import Config
from .model import EconomyManager
from .draw import (draw_sign_card, draw_profile_card, draw_work_card, draw_shop_menu,
                   draw_inventory_card, draw_card_image, draw_gacha_result, download_card_image,
                   draw_leaderboard_card, draw_achievement_card, draw_calendar_card, draw_stock_chart, draw_card_collection)
from .const import (QUOTES, FORTUNE_EVENTS, JOBS, PJSK_CARDS_URL, PJSK_CARD_IMAGE_BASE,
                    PJSK_PROXY_URL, RARITY_MAP, CHAR_MAP, STOCK_LIST, CROP_MAP, PET_MAP, MAP_AREAS,
                    QUIZ_BANK, RAID_BOSSES, DAILY_TASKS, ACHIEVEMENTS, SYNTHESIS_RULES, LOAN_CONFIG,
                    CROP_TYPES, PET_TYPES)

from maimai_sync.lib_msg import _build_markdown_segment, _make_button_rows
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER

def _econ_md(text: str, buttons: list = None) -> Message:
    rows = _make_button_rows(buttons) if buttons else None
    return Message(_build_markdown_segment(text, rows))


__plugin_meta__ = PluginMetadata(
    name="Mizuki Econmy", description="25时经济系统",
    usage="签到, 打工, 个人信息, pk, 结算订单, 发红包, 抢红包, v50报名, 经济帮助, 单抽, 十连, 我的卡牌"
)

pjsk_card_pool = []
pjsk_card_by_id = {}

async def load_pjsk_cards():
    global pjsk_card_pool, pjsk_card_by_id
    import json as _json
    data_dir = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy"
    data_dir.mkdir(parents=True, exist_ok=True)
    cards_dir = data_dir / "cards"
    cards_dir.mkdir(exist_ok=True)
    local_json = data_dir / "cards.json"
    cards = None
    if local_json.exists():
        try:
            with open(local_json, "r", encoding="utf-8") as f:
                cards = _json.load(f)
        except Exception:
            cards = None
    if not cards:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(PJSK_CARDS_URL, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    cards = resp.json()
                    with open(local_json, "w", encoding="utf-8") as f:
                        _json.dump(cards, f, ensure_ascii=False)
        except Exception as e:
            return
    if not cards:
        return
    for c in cards:
        rarity = c.get("cardRarityType", "")
        rarity_info = RARITY_MAP.get(rarity)
        if not rarity_info:
            continue
        char_id = c.get("characterId", 0)
        char_name = CHAR_MAP.get(char_id, "unknown")
        pjsk_card_pool.append({
            "id": c.get("id"),
            "title": c.get("prefix", ""),
            "asset": c.get("assetbundleName", ""),
            "rarity": rarity,
            "star": rarity_info["star"],
            "char_name": char_name,
            "rarity_label": rarity_info["label"],
            "weight": rarity_info["weight"],
        })
    pjsk_card_by_id = {c["id"]: c for c in pjsk_card_pool}

def gacha_pull(count=1):
    if not pjsk_card_pool:
        return []
    weights = [c["weight"] for c in pjsk_card_pool]
    return [random.choices(pjsk_card_pool, weights=weights, k=1)[0].copy() for _ in range(count)]

economy = None
plugin_config = get_plugin_config(Config)
group_envelopes = {}
pending_pks = {}
rps_games = {}

ECONOMY_BUTTONS = [
    {"render_data.label": "签到", "action.data": "签到"},
    {"render_data.label": "打工", "action.data": "打工"},
    {"render_data.label": "个人信息", "action.data": "个人信息"},
    {"render_data.label": "我的背包", "action.data": "我的背包"},
    {"render_data.label": "发起PK", "action.data": "pk "},
    {"render_data.label": "v50报名", "action.data": "v50报名"},
    {"render_data.label": "发红包", "action.data": "发红包 "},
    {"render_data.label": "网页商城", "action.data": "https://store.mizuki.top", "action.type": 0}
]

GACHA_BUTTONS = [
    {"render_data.label": "单抽", "action.data": "单抽"},
    {"render_data.label": "十连", "action.data": "十连"},
    {"render_data.label": "我的卡牌", "action.data": "我的卡牌"},
    {"render_data.label": "网页商城", "action.data": "https://store.mizuki.top", "action.type": 0}
]

STREAK_REWARDS = {3: 30, 7: 100, 14: 250, 30: 500}

async def auto_reconnect_loop():
    while True:
        await asyncio.sleep(10800)
        if economy and not economy.pool:
            logger.info("Database pool is disconnected. Attempting to reconnect...")
            try:
                pool = await aiomysql.create_pool(
                    host=plugin_config.sign_mysql_host,
                    port=plugin_config.sign_mysql_port,
                    user=plugin_config.sign_mysql_user,
                    password=plugin_config.sign_mysql_password,
                    db=plugin_config.sign_mysql_db,
                    autocommit=True,
                    minsize=3,
                    maxsize=20,
                    pool_recycle=3600
                )
                economy.pool = pool
                await economy.init_tables()
                await economy.init_cards_table()
                logger.info("Successfully reconnected to MySQL database!")
                try:
                    await economy.sync_local_to_db()
                    logger.info("Successfully synced local JSON database to MySQL.")
                except Exception as sync_err:
                    logger.error(f"Error syncing local database to MySQL: {sync_err}")
            except Exception as e:
                logger.error(f"Database reconnection failed: {e}")

async def run_crawl_cards():
    try:
        from .crawl_cards import main as crawl_main
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, crawl_main)
        logger.info("Card metadata and thumbnails successfully updated in background!")
    except Exception as e:
        logger.error(f"Error updating card thumbnails on startup: {e}")

@get_driver().on_startup
async def init_db():
    global economy
    try:
        pool = await aiomysql.create_pool(host=plugin_config.sign_mysql_host,port=plugin_config.sign_mysql_port,user=plugin_config.sign_mysql_user,password=plugin_config.sign_mysql_password,db=plugin_config.sign_mysql_db,autocommit=True,minsize=3,maxsize=20,pool_recycle=3600)
        economy = EconomyManager(pool)
        await economy.init_tables()
        await economy.init_cards_table()
        await economy.sync_local_to_db()
        asyncio.ensure_future(load_pjsk_cards())
    except Exception as e:
        logger.warning(f"Database connection failed: {e}. Falling back to local mode.")
        economy = EconomyManager(None)
        asyncio.ensure_future(load_pjsk_cards())
    asyncio.ensure_future(auto_reconnect_loop())
    asyncio.ensure_future(run_crawl_cards())

@get_driver().on_shutdown
async def shutdown_db():
    if economy and economy.pool:
        economy.pool.close()
        await economy.pool.wait_closed()

async def safe_execute(matcher, func, *args, **kwargs):
    if not economy:
        await matcher.finish("数据库未连接")
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=45.0)
    except (FinishedException, RejectedException, PausedException):
        raise
    except asyncio.TimeoutError:
        await matcher.finish("请求超时，请重试")
    except Exception:
        import io
        tb = io.StringIO()
        traceback.print_exc(file=tb)
        tb_str = tb.getvalue()
        await matcher.finish(f"错误:\n{tb_str[:800]}")

def get_user_name(event):
    name = getattr(event.sender, "card", "") or getattr(event.sender, "nickname", "")
    return name if name else str(event.user_id)

HELP_PAGES = {
    1: {
        "title": "25时经济系统 - 基础与娱乐 (第1页/共4页)",
        "text": "签到: 每日签到并获取奖励\n查询: 查看个人余额与详细信息\n打工: 消耗体力进行委托任务\n排行榜: 查看群内财富排行榜\n背包: 查看自己拥有的道具\n使用 物品ID: 消耗并使用背包中的物品\n每日问答: 参与日常趣味答题\n设置背景 [发送图片]: 自定义个人中心背景\n兑换码 [CDK]: 兑换特殊系统礼包\n骰子 [下注]: 摇双骰娱乐小游戏\n幸运数字 [数字] [下注]: 猜幸运数字小游戏\n网页排行榜: https://list.mizuki.top",
        "buttons": [
            {"render_data.label": "签到", "action.data": "签到"},
            {"render_data.label": "个人信息", "action.data": "个人信息"},
            {"render_data.label": "打工", "action.data": "打工"},
            {"render_data.label": "排行榜", "action.data": "排行榜"},
            {"render_data.label": "背包", "action.data": "背包"},
            {"render_data.label": "使用", "action.data": "使用 "},
            {"render_data.label": "下一页", "action.data": "经济帮助 下一页 1"}
        ]
    },
    2: {
        "title": "25时经济系统 - 交互与社交 (第2页/共4页)",
        "text": "pk @某人: 发起代币对决PK\n接受pk / 拒绝pk: 应对他人的PK决斗请求\n猜拳 @某人 金额: 石头剪刀布决斗\n发红包 金额 份数: 在群里塞红包\n抢红包: 抢夺群内发出的最新红包\nv50报名: 参与周四的v50大奖集资\n转账 @某人 金额: 转账给指定用户\n写日记 内容: 在日记墙留下实名心情\n树洞 内容: 在日记墙留下匿名心情\n共鸣 日记ID: 产生共鸣并为作者提供奖励\n日记墙: 查看群友写的日记列表",
        "buttons": [
            {"render_data.label": "上一页", "action.data": "经济帮助 上一页 2"},
            {"render_data.label": "v50报名", "action.data": "v50报名"},
            {"render_data.label": "日记墙", "action.data": "日记墙"},
            {"render_data.label": "发红包", "action.data": "发红包 "},
            {"render_data.label": "抢红包", "action.data": "抢红包"},
            {"render_data.label": "pk", "action.data": "pk "},
            {"render_data.label": "下一页", "action.data": "经济帮助 下一页 2"}
        ]
    },
    3: {
        "title": "25时经济系统 - 经济与经营 (第3页/共4页)",
        "text": "购买 物品ID: 网页或命令快捷购买商城物资\n贷款 金额: 向系统借贷代币\n还款: 还清当前的系统借贷\n股市: 查看并交易虚拟股票\n卖出 股票ID 数量: 变现持有的股票\n我的持仓: 查看个人股票资产\n拍卖 列表: 查看拍卖行上架物品\n每日任务: 查看今天可完成的任务\n领取奖励 任务ID: 结算完成的任务奖励\n网页商城: https://store.mizuki.top",
        "buttons": [
            {"render_data.label": "上一页", "action.data": "经济帮助 上一页 3"},
            {"render_data.label": "我的持仓", "action.data": "我的持仓"},
            {"render_data.label": "每日任务", "action.data": "每日任务"},
            {"render_data.label": "股市", "action.data": "股市"},
            {"render_data.label": "买入", "action.data": "买入 "},
            {"render_data.label": "卖出", "action.data": "卖出 "},
            {"render_data.label": "贷款", "action.data": "贷款 "},
            {"render_data.label": "下一页", "action.data": "经济帮助 下一页 3"}
        ]
    },
    4: {
        "title": "25时经济系统 - 收集与育成 (第4页/共4页)",
        "text": "单抽: 消耗代币抽取一张卡牌\n十连: 一次性抽取十张卡牌\n我的卡牌: 查看个人卡牌馆藏\n合成 星级: 三合一升级高星卡牌\n农场: 查看自己的作物种植情况\n种植 作物ID: 播种相应植物种子\n收菜: 收获已经成熟的农作物\n宠物: 查看个人宠物状态\n领养宠物 类型: 获得自己的新宠物\n喂食: 消耗代币给宠物喂食\n副本: 消耗代币组队挑战Boss\n探索 [区域ID]: 探索不同地图获取产出\n成就墙: 展示已解锁的系统成就",
        "buttons": [
            {"render_data.label": "上一页", "action.data": "经济帮助 上一页 4"},
            {"render_data.label": "我的卡牌", "action.data": "我的卡牌"},
            {"render_data.label": "单抽", "action.data": "单抽"},
            {"render_data.label": "十连", "action.data": "十连"},
            {"render_data.label": "农场", "action.data": "农场"},
            {"render_data.label": "收菜", "action.data": "收菜"},
            {"render_data.label": "宠物", "action.data": "宠物"},
            {"render_data.label": "副本", "action.data": "副本"}
        ]
    }
}

help_cmd = on_command("经济帮助", aliases={"25时经济系统", "经济菜单"}, priority=5, block=True)
@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    arg = args.extract_plain_text().strip().split()
    page = 1
    if len(arg) >= 2:
        action = arg[0]
        cur_p = int(arg[1]) if arg[1].isdigit() else 1
        if action == "下一页":
            page = min(4, cur_p + 1)
        elif action == "上一页":
            page = max(1, cur_p - 1)
    elif len(arg) == 1 and arg[0].isdigit():
        page = int(arg[0])
    
    p_data = HELP_PAGES.get(page, HELP_PAGES[1])
    text = f"### {p_data['title']}\n"
    for line in p_data["text"].split("\n"):
        text += f"> {line}\n"
    
    await help_cmd.finish(_econ_md(text, p_data["buttons"]))

sign_cmd = on_command("签到", priority=5, block=True)
@sign_cmd.handle()
async def handle_sign(bot: Bot, event: MessageEvent):
    async def _logic():
        uid, uname = event.user_id, get_user_name(event)
        today = datetime.date.today()
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT last_sign_date FROM user_economy WHERE user_id=%s", (uid,))
                    row = await cur.fetchone()
                    if row and row[0] == today:
                        await sign_cmd.finish("今天已经签过了")
        pc = random.randint(5, 20)
        luck = random.randint(0, 100)
        q = random.choice(QUOTES)
        evt = random.choice(FORTUNE_EVENTS)
        qs = f"{q[1]} | {q[2]}"
        lvl, xp, title = await economy.sign_in(uid, uname, luck, qs, evt["good"], evt["bad"])
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (pc, uid))
        else:
            data = economy._read_local()
            uid_str = str(uid)
            if uid_str in data["user_economy"]:
                data["user_economy"][uid_str]["balance"] += pc
                economy._write_local(data)
        try:
            if economy.pool:
                async with economy.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT last_sign_date,sign_streak FROM user_economy WHERE user_id=%s", (uid,))
                        r = await cur.fetchone()
                        yesterday = today - datetime.timedelta(days=1)
                        if r and r[0]:
                            ld = r[0]
                            if isinstance(ld, str): ld = datetime.datetime.strptime(ld, "%Y-%m-%d").date()
                            streak = (r[1] or 0) + 1 if ld == yesterday else 1
                        else:
                            streak = 1
                        await cur.execute("UPDATE user_economy SET sign_streak=%s WHERE user_id=%s", (streak, uid))
                        if streak in STREAK_REWARDS:
                            b = STREAK_REWARDS[streak]
                            await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (b, uid))
                            await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (uid, b, f"连签{streak}天"))
            else:
                data = economy._read_local()
                uid_str = str(uid)
                if uid_str in data["user_economy"]:
                    data["user_economy"][uid_str]["sign_streak"] = data["user_economy"][uid_str].get("sign_streak", 0) + 1
                    economy._write_local(data)
        except Exception:
            pass
        gid = event.group_id if hasattr(event, "group_id") else None
        img = await draw_sign_card(uid, uname, {"title": title, "luck": luck, "quote": qs, "good": evt["good"], "bad": evt["bad"], "lvl": lvl, "xp": xp, "pc_add": pc}, bot, gid)
        msg = MessageSegment.image(img) + _econ_md("签到成功", ECONOMY_BUTTONS)
        await sign_cmd.finish(msg)
    await safe_execute(sign_cmd, _logic)

info_cmd = on_command("个人信息", aliases={"余额", "查询"}, priority=5, block=True)
@info_cmd.handle()
async def handle_info(bot: Bot, event: MessageEvent):
    async def _logic():
        data = await economy.get_user_detail(event.user_id)
        if not data:
            await info_cmd.finish("请先签到")
        gid = event.group_id if hasattr(event, "group_id") else None
        img = await draw_profile_card(event.user_id, get_user_name(event), data, bot, gid)
        msg = MessageSegment.image(img) + _econ_md("个人信息", ECONOMY_BUTTONS)
        await info_cmd.finish(msg)
    await safe_execute(info_cmd, _logic)

work_cmd = on_command("打工", priority=5, block=True)
@work_cmd.handle()
async def handle_work(bot: Bot, event: MessageEvent):
    async def _logic():
        res = await economy.work_process(event.user_id, get_user_name(event), JOBS)
        if res.get("status") == "failed":
            await work_cmd.finish(res["msg"])
        img = await draw_work_card(get_user_name(event), "一键", res)
        msg = MessageSegment.image(img) + _econ_md("打工结算完成", ECONOMY_BUTTONS)
        await work_cmd.finish(msg)
    await safe_execute(work_cmd, _logic)

inv_cmd = on_command("我的背包", aliases={"背包"}, priority=5, block=True)
@inv_cmd.handle()
async def handle_inv(bot: Bot, event: MessageEvent):
    async def _logic():
        bal, lvl = await economy.get_shop_info(event.user_id)
        items = await economy.get_inventory(event.user_id)
        img = await draw_inventory_card(get_user_name(event), bal, lvl, items)
        msg = MessageSegment.image(img) + _econ_md("我的背包", ECONOMY_BUTTONS)
        await inv_cmd.finish(msg)
    await safe_execute(inv_cmd, _logic)

buy_cmd = on_command("结算订单", aliases={"购买"}, priority=5, block=True)
@buy_cmd.handle()
async def handle_buy(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    async def _logic():
        tid = args.extract_plain_text().strip()
        if not tid.isdigit():
            await buy_cmd.finish("格式: 结算订单 物品ID")
        res = await economy.buy_item(event.user_id, int(tid))
        p = "交易成功" if res["status"] else "交易失败"
        await buy_cmd.finish(_econ_md(f"{p}\n{res['msg']}", ECONOMY_BUTTONS))
    await safe_execute(buy_cmd, _logic)

cancel_cmd = on_command("取消", aliases={"退出", "quit", "重置"}, priority=1, block=True)
@cancel_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await cancel_cmd.finish("已清理")

pk_cmd = on_command("pk", aliases={"决斗", "对决"}, priority=5, block=True)
@pk_cmd.handle()
async def handle_pk(bot: Bot, event: MessageEvent):
    async def _logic():
        tid = None
        if event.reply:
            tid = event.reply.sender.user_id
        if not tid:
            for seg in getattr(event, "original_message", event.message):
                if seg.type == "at":
                    qq = str(seg.data.get("qq", ""))
                    if qq and qq != "all" and qq != str(bot.self_id):
                        tid = int(qq)
                        break
        if not tid:
            await pk_cmd.finish("请回复或@某人发起pk")
        if tid == event.user_id:
            await pk_cmd.finish("不能和自己pk")
        amt = random.randint(10, 1000)
        pending_pks[tid] = {"challenger": event.user_id, "challenger_name": get_user_name(event), "amount": amt}
        txt = f"PK邀请\n{get_user_name(event)} 发起pk 赌注{amt}PC"
        btns = [{"render_data.label": "接受", "action.data": "接受pk"}, {"render_data.label": "拒绝", "action.data": "拒绝pk"}]
        await pk_cmd.finish(MessageSegment.at(tid) + _econ_md(txt, btns))
    await safe_execute(pk_cmd, _logic)

accept_pk = on_command("接受pk", priority=5, block=True)
@accept_pk.handle()
async def handle_accept(bot: Bot, event: MessageEvent):
    async def _logic():
        if event.user_id not in pending_pks:
            await accept_pk.finish("没有待处理的pk")
        pd = pending_pks.pop(event.user_id)
        res = await economy.settle_pk(pd["challenger"], event.user_id, pd["amount"])
        if not res["status"]:
            await accept_pk.finish(res["msg"])
        txt = f"PK结算\n胜者: {res['winner_name']}\n败者: {res['loser_name']}\n获得 {res['win_net']} PC (扣税{res['tax']})"
        await accept_pk.finish(txt)
    await safe_execute(accept_pk, _logic)

refuse_pk = on_command("拒绝pk", priority=5, block=True)
@refuse_pk.handle()
async def handle_refuse(bot: Bot, event: MessageEvent):
    if event.user_id in pending_pks:
        pending_pks.pop(event.user_id)
        await refuse_pk.finish("已拒绝pk")
    else:
        await refuse_pk.finish("没有待处理的pk")

v50_cmd = on_command("v50报名", aliases={"参与v50", "v我50"}, priority=5, block=True)
@v50_cmd.handle()
async def handle_v50(bot: Bot, event: MessageEvent):
    async def _logic():
        gid = getattr(event, "group_id", 0)
        if not gid:
            await v50_cmd.finish("仅限群聊参与")
        res = await economy.join_v50_pool(event.user_id, get_user_name(event), gid)
        await v50_cmd.finish(res["msg"])
    await safe_execute(v50_cmd, _logic)

send_re = on_command("发红包", priority=5, block=True)
@send_re.handle()
async def handle_send(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    gid, uid = event.group_id, event.user_id
    try:
        parts = args.extract_plain_text().strip().split()
        total, count = int(parts[0]), int(parts[1])
        if count < 1 or count > 50 or total < 10:
            raise ValueError
    except:
        await send_re.finish("格式: 发红包 金额 份数")
    tax = max(1, int(total * 0.05))
    pool = total - tax
    if pool < count:
        await send_re.finish("余额不足")
    pkt_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    async def _logic():
        ok, msg = await economy.send_redpacket(uid, total, pkt_id)
        if not ok:
            await send_re.finish(msg)
        remain, cnt = pool, count
        parts_list = []
        for _ in range(count - 1):
            v = random.randint(1, max(1, (remain // cnt) * 2))
            parts_list.append(v)
            remain -= v
            cnt -= 1
        parts_list.append(remain)
        random.shuffle(parts_list)
        if gid not in group_envelopes:
            group_envelopes[gid] = []
        group_envelopes[gid].append({"id": pkt_id, "sender_name": get_user_name(event), "parts": parts_list, "grabbed_by": set()})
        txt = f"红包 {get_user_name(event)}\n金额: {total}PC 税{tax}\n序列号: {pkt_id}"
        await send_re.finish(txt)
    await safe_execute(send_re, _logic)

grab_re = on_command("抢红包", priority=5, block=True)
@grab_re.handle()
async def handle_grab(bot: Bot, event: GroupMessageEvent):
    async def _logic():
        gid, uid = event.group_id, event.user_id
        if gid not in group_envelopes or not group_envelopes[gid]:
            await grab_re.finish("没有红包")
        env = group_envelopes[gid][-1]
        if uid in env["grabbed_by"]:
            await grab_re.finish("已经抢过了")
        if not env["parts"]:
            await grab_re.finish("抢光了")
        amt = env["parts"].pop(0)
        env["grabbed_by"].add(uid)
        pid = env["id"]
        if not env["parts"]:
            group_envelopes[gid].remove(env)
        await economy.grab_redpacket(uid, get_user_name(event), amt, pid, env["sender_name"])
        await grab_re.finish(f"抢到 {amt} PC")
    await safe_execute(grab_re, _logic)

admin_set = on_command("设置余额", permission=SUPERUSER, priority=1, block=True)
@admin_set.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip().split()
        if len(t) < 2 or not t[0].isdigit():
            await admin_set.finish("格式: 设置余额 @某人 金额")
        await economy.admin_set_balance(int(t[0]), int(t[1]))
        await admin_set.finish(f"已设置 {t[0]} 余额为 {t[1]} PC")
    await safe_execute(admin_set, _f)

admin_add = on_command("加减余额", permission=SUPERUSER, priority=1, block=True)
@admin_add.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip().split()
        if len(t) < 2 or not t[0].isdigit():
            await admin_add.finish("格式: 加减余额 @某人 金额")
        await economy.admin_add_balance(int(t[0]), int(t[1]))
        await admin_add.finish(f"已调整 {t[0]} {int(t[1]):+d} PC")
    await safe_execute(admin_add, _f)

admin_stats = on_command("经济统计", permission=SUPERUSER, priority=1, block=True)
@admin_stats.handle()
async def _(bot, event):
    async def _f():
        s = await economy.get_stats()
        await admin_stats.finish(f"经济统计\n用户: {s['users']}\n流通PC: {s['total_pc']}\n今日活跃: {s['today_active']}")
    await safe_execute(admin_stats, _f)

cdk_redeem = on_command("兑换CDK", aliases={"兑换码"}, priority=5, block=True)
@cdk_redeem.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        cdk = args.extract_plain_text().strip()
        if not cdk:
            await cdk_redeem.finish("格式: 兑换CDK 码")
        res = await economy.redeem_cdk(event.user_id, cdk)
        await cdk_redeem.finish(res.get("msg", str(res)))
    await safe_execute(cdk_redeem, _f)

cdk_gen = on_command("生成CDK", permission=SUPERUSER, priority=1, block=True)
@cdk_gen.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip().split()
        if len(t) < 2:
            await cdk_gen.finish("格式: 生成CDK 物品ID 有效期小时")
        await cdk_gen.finish(await economy.create_cdk(int(t[0]), int(t[1])))
    await safe_execute(cdk_gen, _f)

use_cmd = on_command("使用", aliases={"使用道具"}, priority=5, block=True)
@use_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        tid = args.extract_plain_text().strip()
        if not tid.isdigit():
            await use_cmd.finish("格式: 使用 物品ID")
        inv = await economy.get_inventory(event.user_id)
        if not any(i["id"] == int(tid) and i["qty"] > 0 for i in inv):
            await use_cmd.finish("你没有这个物品")
        await economy.use_item(event.user_id, int(tid))
        await use_cmd.finish(await economy.use_item_effect(event.user_id, int(tid)))
    await safe_execute(use_cmd, _f)

transfer_cmd = on_command("转账", aliases={"转钱"}, priority=5, block=True)
@transfer_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        at_id = None
        for seg in event.message:
            if seg.type == "at":
                at_id = int(seg.data.get("qq", 0))
                break
        t = args.extract_plain_text().strip().split()
        amt = int(t[-1]) if t and t[-1].isdigit() else 0
        tid = at_id or (int(t[0]) if t and t[0].isdigit() else 0)
        if not tid or amt < 10:
            await transfer_cmd.finish("格式: 转账 @某人 金额 (最低10PC)")
        if tid == event.user_id:
            await transfer_cmd.finish("不能给自己转账")
        res = await economy.transfer_pc(event.user_id, tid, amt)
        await transfer_cmd.finish(res["msg"])
    await safe_execute(transfer_cmd, _f)

loan_cmd = on_command("贷款", aliases={"借钱"}, priority=5, block=True)
@loan_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip()
        if not t.isdigit():
            await loan_cmd.finish("格式: 贷款 金额 (100-5000)")
        await loan_cmd.finish((await economy.take_loan(event.user_id, int(t)))["msg"])
    await safe_execute(loan_cmd, _f)

repay_cmd = on_command("还款", aliases={"还贷"}, priority=5, block=True)
@repay_cmd.handle()
async def _(bot, event):
    async def _f():
        await repay_cmd.finish((await economy.repay_loan(event.user_id))["msg"])
    await safe_execute(repay_cmd, _f)

daily_cmd = on_command("每日任务", aliases={"任务"}, priority=5, block=True)
@daily_cmd.handle()
async def _(bot, event):
    async def _f():
        tasks = await economy.get_daily_tasks(event.user_id)
        txt = "今日任务\n"
        buttons = []
        for t, done, claimed in tasks:
            st = "已领" if claimed else ("可领" if done else "未完成")
            txt += f"[{t['id']}] {t.get('name',t['id'])} - {st} (+{t.get('reward',50)}PC)\n"
            if done and not claimed:
                buttons.append({"render_data.label": f"领 {t.get('name')}", "action.data": f"领取奖励 {t['id']}"})
        txt += "\n发送 领取奖励 任务ID"
        buttons.append({"render_data.label": "每日任务", "action.data": "每日任务"})
        buttons.append({"render_data.label": "个人信息", "action.data": "个人信息"})
        await daily_cmd.finish(_econ_md(txt, buttons))
    await safe_execute(daily_cmd, _f)

claim_cmd = on_command("领取奖励", priority=5, block=True)
@claim_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        tid = args.extract_plain_text().strip()
        if not tid:
            await claim_cmd.finish("格式: 领取奖励 任务ID")
        res_msg = await economy.claim_task_reward(event.user_id, tid)
        await claim_cmd.finish(_econ_md(res_msg, [{"render_data.label": "每日任务", "action.data": "每日任务"}]))
    await safe_execute(claim_cmd, _f)

ach_list_cmd = on_command("成就列表", aliases={"成就详情"}, priority=5, block=True)
@ach_list_cmd.handle()
async def _(bot, event):
    async def _f():
        achs = await economy.get_achievements(event.user_id)
        unlocked = sum(1 for _, ok in achs if ok)
        txt = f"成就 ({unlocked}/{len(achs)})\n"
        for a, ok in achs:
            icon = "+" if ok else "x"
            txt += f"{icon} {a['name']} - {a['desc']} (+{a['reward']}PC)\n"
        await ach_list_cmd.finish(txt)
    await safe_execute(ach_list_cmd, _f)

synth_cmd = on_command("合成", aliases={"卡牌合成"}, priority=5, block=True)
@synth_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip()
        if not t.isdigit() or int(t) < 1 or int(t) > 4:
            await synth_cmd.finish("格式: 合成 星级(1-4)\n3张同星卡+100PC=1张高星卡")
        await synth_cmd.finish((await economy.synthesize_cards(event.user_id, int(t)))["msg"])
    await safe_execute(synth_cmd, _f)

farm_cmd = on_command("农场", aliases={"我的农场"}, priority=5, block=True)
@farm_cmd.handle()
async def _(bot, event):
    async def _f():
        from .const import CROP_MAP
        plots = await economy.get_farm(event.user_id)
        if not plots:
            await farm_cmd.finish("农场空空如也，发送 种植 作物ID 开始\n" + "、".join(f"{c['id']}({c['name']})" for c in CROP_MAP.values()))
        txt = "你的农场\n"
        for pid, cid, planted, status in plots:
            crop = CROP_MAP.get(cid, {"name": cid})
            txt += f"{crop['name']} - {status}\n"
        await farm_cmd.finish(txt)
    await safe_execute(farm_cmd, _f)

plant_cmd = on_command("种植", priority=5, block=True)
@plant_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        cid = args.extract_plain_text().strip()
        if not cid:
            await plant_cmd.finish("格式: 种植 作物ID (如 c01)")
        await plant_cmd.finish(await economy.plant_crop(event.user_id, cid))
    await safe_execute(plant_cmd, _f)

harvest_cmd = on_command("收菜", aliases={"收获"}, priority=5, block=True)
@harvest_cmd.handle()
async def _(bot, event):
    async def _f():
        await harvest_cmd.finish(await economy.harvest_crops(event.user_id))
    await safe_execute(harvest_cmd, _f)

pet_cmd = on_command("宠物", aliases={"我的宠物"}, priority=5, block=True)
@pet_cmd.handle()
async def _(bot, event):
    async def _f():
        pet = await economy.get_pet(event.user_id)
        if not pet:
            await pet_cmd.finish("没有宠物，发送 领养宠物 类型 领养\np01(夜猫) p02(柴犬) p03(猫头鹰)")
        pt, name, hunger, happy, level = pet
        await pet_cmd.finish(f"{name} (Lv.{level})\n饱食: {hunger}/100\n心情: {happy}/100\n发送 喂食 加餐")
    await safe_execute(pet_cmd, _f)

adopt_pet = on_command("领养宠物", priority=5, block=True)
@adopt_pet.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        pt = args.extract_plain_text().strip()
        if not pt:
            await adopt_pet.finish("格式: 领养宠物 类型 (p01/p02/p03)")
        await adopt_pet.finish(await economy.adopt_pet(event.user_id, pt))
    await safe_execute(adopt_pet, _f)

feed_cmd = on_command("喂食", priority=5, block=True)
@feed_cmd.handle()
async def _(bot, event):
    async def _f():
        await feed_cmd.finish(await economy.feed_pet(event.user_id))
    await safe_execute(feed_cmd, _f)

raid_cmd = on_command("副本", aliases={"团队副本"}, priority=5, block=True)
@raid_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        from .const import RAID_BOSSES
        t = args.extract_plain_text().strip()
        if not t:
            txt = "可用副本\n"
            for b in RAID_BOSSES:
                txt += f"[{b['id']}] {b['name']} - {b['cost']}PC (HP:{b['hp']})\n"
            txt += "\n发送 副本 BossID 挑战"
            await raid_cmd.finish(txt)
        await raid_cmd.finish(await economy.join_raid(event.user_id, t))
    await safe_execute(raid_cmd, _f)

quiz_cmd = on_command("每日问答", aliases={"问答", "答题"}, priority=5, block=True)
@quiz_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        answer = args.extract_plain_text().strip()
        if not answer:
            q = await economy.get_quiz(event.user_id)
            opts = " / ".join(q["options"])
            await quiz_cmd.finish(f"{q['q']}\n选项: {opts}\n\n发送 每日问答 你的答案")
        await quiz_cmd.finish(await economy.answer_quiz(event.user_id, answer))
    await safe_execute(quiz_cmd, _f)

explore_cmd = on_command("探索", aliases={"探索地图"}, priority=5, block=True)
@explore_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        from .const import MAP_AREAS
        t = args.extract_plain_text().strip()
        if not t or not t.isdigit():
            txt = "探索地图\n"
            for a in MAP_AREAS:
                txt += f"[{a['id']}] {a['name']} - {a['cost']}PC -> {a['reward_pc']}PC\n"
            txt += "\n发送 探索 区域ID"
            await explore_cmd.finish(txt)
        await explore_cmd.finish(await economy.explore_area(event.user_id, int(t)))
    await safe_execute(explore_cmd, _f)

STOCK_BUTTONS = [
    {"render_data.label": "股市行情", "action.data": "股市"},
    {"render_data.label": "我的持仓", "action.data": "我的持仓"},
    {"render_data.label": "个人信息", "action.data": "个人信息"}
]

stock_cmd = on_command("股市", aliases={"股票"}, priority=5, block=True)
@stock_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        from .const import STOCK_LIST
        t = args.extract_plain_text().strip()
        if t:
            parts = t.split()
            if len(parts) >= 2 and parts[1].isdigit():
                res = await economy.buy_stock(event.user_id, parts[0], int(parts[1]))
                await stock_cmd.finish(_econ_md(res["msg"], STOCK_BUTTONS))
            else:
                await stock_cmd.finish("格式: 股票 代码 数量 或 直接发送 买入 代码 数量")
        
        prices, event_desc = economy.get_stock_prices()
        history = economy.get_stock_history()
        img = await draw_stock_chart(STOCK_LIST, prices, history, event_desc)
        msg = MessageSegment.image(img) + _econ_md(event_desc or "25时证券交易所", STOCK_BUTTONS)
        await stock_cmd.finish(msg)
    await safe_execute(stock_cmd, _f)

buy_stock_cmd = on_command("买入", priority=5, block=True)
@buy_stock_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        parts = args.extract_plain_text().strip().split()
        if len(parts) < 2 or not parts[1].isdigit():
            await buy_stock_cmd.finish("格式: 买入 代码 数量")
        res = await economy.buy_stock(event.user_id, parts[0], int(parts[1]))
        await buy_stock_cmd.finish(_econ_md(res["msg"], STOCK_BUTTONS))
    await safe_execute(buy_stock_cmd, _f)

sell_cmd = on_command("卖出", aliases={"卖股票"}, priority=5, block=True)
@sell_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        parts = args.extract_plain_text().strip().split()
        if len(parts) < 2 or not parts[1].isdigit():
            await sell_cmd.finish("格式: 卖出 代码 数量")
        res = await economy.sell_stock(event.user_id, parts[0], int(parts[1]))
        await sell_cmd.finish(_econ_md(res["msg"], STOCK_BUTTONS))
    await safe_execute(sell_cmd, _f)

hold_cmd = on_command("我的持仓", aliases={"持仓"}, priority=5, block=True)
@hold_cmd.handle()
async def _(bot, event):
    async def _f():
        from .const import STOCK_LIST
        holdings = await economy.get_holdings(event.user_id)
        if not holdings:
            await hold_cmd.finish(_econ_md("你目前没有任何持仓", STOCK_BUTTONS))
        prices, _ = economy.get_stock_prices()
        txt = "我的股票持仓\n"
        for sid, qty in holdings:
            s = next((s for s in STOCK_LIST if s["id"] == sid), {"name": sid})
            cur_price = prices.get(sid, {}).get("price", 0)
            val = cur_price * qty
            txt += f"[{sid}] {s['name']} x{qty} (现值 {val} PC)\n"
        await hold_cmd.finish(_econ_md(txt, STOCK_BUTTONS))
    await safe_execute(hold_cmd, _f)

auction_cmd = on_command("拍卖", aliases={"拍卖行"}, priority=5, block=True)
@auction_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip()
        if not t:
            await auction_cmd.finish("用法:\n拍卖 上架 物品ID 底价 时长\n拍卖 出价 拍卖ID 金额\n拍卖 列表")
        parts = t.split()
        if parts[0] == "上架" and len(parts) >= 4:
            await auction_cmd.finish(await economy.create_auction(event.user_id, int(parts[1]), int(parts[2]), int(parts[3])))
        elif parts[0] == "出价" and len(parts) >= 3:
            await auction_cmd.finish(await economy.bid_auction(event.user_id, int(parts[1]), int(parts[2])))
        else:
            await auction_cmd.finish("格式错误")
    await safe_execute(auction_cmd, _f)

diary_cmd = on_command("写日记", aliases={"日记"}, priority=5, block=True)
@diary_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        content = args.extract_plain_text().strip()
        if not content:
            await diary_cmd.finish("格式: 写日记 内容")
        if len(content) > 200:
            await diary_cmd.finish("不超过200字")
        await diary_cmd.finish(await economy.write_diary(event.user_id, content))
    await safe_execute(diary_cmd, _f)

treehole = on_command("树洞", aliases={"匿名树洞"}, priority=5, block=True)
@treehole.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        content = args.extract_plain_text().strip()
        if not content:
            await treehole.finish("格式: 树洞 内容")
        if len(content) > 200:
            await treehole.finish("不超过200字")
        await treehole.finish(await economy.write_diary(event.user_id, content, is_anonymous=1))
    await safe_execute(treehole, _f)

rank_cmd = on_command("排行榜", aliases={"排行", "富豪榜"}, priority=5, block=True)
@rank_cmd.handle()
async def _(bot, event):
    async def _f():
        lb = await economy.get_leaderboard(20)
        if not lb:
            await rank_cmd.finish("还没有排行数据")
        my_rank = 0
        for e in lb:
            if int(e["user_id"]) == event.user_id:
                my_rank = e["rank"]
                break
        if my_rank == 0:
            detail = await economy.get_user_detail(event.user_id)
            if detail:
                all_lb = await economy.get_leaderboard(9999)
                for e in all_lb:
                    if int(e["user_id"]) == event.user_id:
                        my_rank = e["rank"]
                        break
        img = await draw_leaderboard_card(get_user_name(event), lb, my_rank)
        msg = MessageSegment.image(img) + _econ_md("排行榜", ECONOMY_BUTTONS)
        await rank_cmd.finish(msg)
    await safe_execute(rank_cmd, _f)

ach_cmd = on_command("成就墙", aliases={"成就", "我的成就"}, priority=5, block=True)
@ach_cmd.handle()
async def _(bot, event):
    async def _f():
        achs = await economy.get_achievements(event.user_id)
        if not achs:
            await ach_cmd.finish("暂无成就数据，请先发送签到注册")
        img = await draw_achievement_card(get_user_name(event), achs)
        msg = MessageSegment.image(img) + _econ_md("我的成就", ECONOMY_BUTTONS)
        await ach_cmd.finish(msg)
    await safe_execute(ach_cmd, _f)

calendar_cmd = on_command("签到日历", aliases={"日历", "我的签到"}, priority=5, block=True)
@calendar_cmd.handle()
async def _(bot, event):
    async def _f():
        sign_dates = await economy.get_sign_dates(event.user_id)
        streak = await economy.get_sign_streak(event.user_id)
        img = await draw_calendar_card(event.user_id, get_user_name(event), sign_dates, streak)
        msg = MessageSegment.image(img) + _econ_md("签到日历", ECONOMY_BUTTONS)
        await calendar_cmd.finish(msg)
    await safe_execute(calendar_cmd, _f)

DIARY_BUTTONS = [
    {"render_data.label": "日记墙", "action.data": "日记墙"},
    {"render_data.label": "个人信息", "action.data": "个人信息"}
]

wall_cmd = on_command("日记墙", aliases={"树洞墙"}, priority=5, block=True)
@wall_cmd.handle()
async def _(bot, event):
    async def _f():
        diaries = await economy.get_diaries(10)
        if not diaries:
            await wall_cmd.finish(_econ_md("日记墙目前空空如也，快来写下你的第一篇日记吧！", DIARY_BUTTONS))
        txt = "日记墙\n"
        for d in diaries:
            did = d.get("id")
            uid = d.get("user_id")
            content = d.get("content")
            likes = d.get("likes", 0)
            anon = d.get("is_anonymous", 0)
            author = "匿名" if anon else f"用户{uid}"
            txt += f"#{did} ({author}) 共鸣数:{likes}\n{content}\n\n"
        txt += "发送: 共鸣 [日记ID]"
        await wall_cmd.finish(_econ_md(txt, DIARY_BUTTONS))
    await safe_execute(wall_cmd, _f)

like_cmd = on_command("共鸣", priority=5, block=True)
@like_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip()
        if not t.isdigit():
            await like_cmd.finish("格式: 共鸣 日记ID")
        await like_cmd.finish(await economy.like_diary(event.user_id, int(t)))
    await safe_execute(like_cmd, _f)

dice_cmd = on_command("骰子", aliases={"摇骰子"}, priority=5, block=True)
@dice_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip()
        if not t.isdigit() or int(t) < 10:
            await dice_cmd.finish("格式: 骰子 金额 (最低10PC)")
        bet = int(t)
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (event.user_id,))
                    row = await cur.fetchone()
                    if not row or row[0] < bet:
                        await dice_cmd.finish("余额不足")
                    dice = [random.randint(1, 6) for _ in range(3)]
                    total = sum(dice)
                    triple = len(set(dice)) == 1
                    pair = len(set(dice)) == 2
                    if triple:
                        mult, tag = 3.0, "豹子"
                    elif pair:
                        mult, tag = 1.5, "对子"
                    elif total > 10:
                        mult, tag = 1.8, "大"
                    else:
                        mult, tag = 0, "小"
                    if mult > 0:
                        win = int(bet * mult)
                        await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (win - bet, event.user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (event.user_id, win - bet, f"骰子赢{win}"))
                        await dice_cmd.finish(f"{tag} {dice} {total}点\n赢了 {win} PC ({mult}倍)")
                    else:
                        await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (bet, event.user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (event.user_id, -bet, "骰子输"))
                        await dice_cmd.finish(f"{tag} {dice} {total}点\n输了 {bet} PC")
        else:
            data = economy._read_local()
            uid_str = str(event.user_id)
            if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < bet:
                await dice_cmd.finish("余额不足")
            dice = [random.randint(1, 6) for _ in range(3)]
            total = sum(dice)
            triple = len(set(dice)) == 1
            pair = len(set(dice)) == 2
            if triple:
                mult, tag = 3.0, "豹子"
            elif pair:
                mult, tag = 1.5, "对子"
            elif total > 10:
                mult, tag = 1.8, "大"
            else:
                mult, tag = 0, "小"
            if mult > 0:
                win = int(bet * mult)
                data["user_economy"][uid_str]["balance"] += (win - bet)
                data["economy_logs"].append({"user_id": event.user_id, "amount": win - bet, "description": f"骰子赢{win}"})
                economy._write_local(data)
                await dice_cmd.finish(f"{tag} {dice} {total}点\n赢了 {win} PC ({mult}倍)")
            else:
                data["user_economy"][uid_str]["balance"] -= bet
                data["economy_logs"].append({"user_id": event.user_id, "amount": -bet, "description": "骰子输"})
                economy._write_local(data)
                await dice_cmd.finish(f"{tag} {dice} {total}点\n输了 {bet} PC")
    await safe_execute(dice_cmd, _f)

lucknum = on_command("幸运数字", priority=5, block=True)
@lucknum.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        t = args.extract_plain_text().strip().split()
        if len(t) < 2:
            await lucknum.finish("格式: 幸运数字 数字(1-10) 下注金额")
        my_num, bet = int(t[0]), int(t[1])
        if my_num < 1 or my_num > 10 or bet < 10:
            await lucknum.finish("数字1-10，最低10PC")
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (event.user_id,))
                    row = await cur.fetchone()
                    if not row or row[0] < bet:
                        await lucknum.finish("余额不足")
                    lucky = random.randint(1, 10)
                    diff = abs(my_num - lucky)
                    if diff == 0:
                        win = bet * 10
                        await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (win - bet, event.user_id))
                        await lucknum.finish(f"幸运数字是 {lucky}！猜中了！赢 {win} PC (10倍)")
                    elif diff == 1:
                        win = bet * 3
                        await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (win - bet, event.user_id))
                        await lucknum.finish(f"幸运数字是 {lucky}！差一点！赢 {win} PC (3倍)")
                    else:
                        await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (bet, event.user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (event.user_id, -bet, "幸运数字"))
                        await lucknum.finish(f"幸运数字是 {lucky}，你猜 {my_num}，输了 {bet} PC")
        else:
            data = economy._read_local()
            uid_str = str(event.user_id)
            if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < bet:
                await lucknum.finish("余额不足")
            lucky = random.randint(1, 10)
            diff = abs(my_num - lucky)
            if diff == 0:
                win = bet * 10
                data["user_economy"][uid_str]["balance"] += (win - bet)
                economy._write_local(data)
                await lucknum.finish(f"幸运数字是 {lucky}！猜中了！赢 {win} PC (10倍)")
            elif diff == 1:
                win = bet * 3
                data["user_economy"][uid_str]["balance"] += (win - bet)
                economy._write_local(data)
                await lucknum.finish(f"幸运数字是 {lucky}！差一点！赢 {win} PC (3倍)")
            else:
                data["user_economy"][uid_str]["balance"] -= bet
                data["economy_logs"].append({"user_id": event.user_id, "amount": -bet, "description": "幸运数字"})
                economy._write_local(data)
                await lucknum.finish(f"幸运数字是 {lucky}，你猜 {my_num}，输了 {bet} PC")
    await safe_execute(lucknum, _f)

rps_games = {}
rps_cmd = on_command("猜拳", aliases={"石头剪刀布"}, priority=5, block=True)
@rps_cmd.handle()
async def _(bot, event, args=CommandArg()):
    async def _f():
        import re as _re
        text = args.extract_plain_text().strip()
        at_id = None
        for seg in event.message:
            if seg.type == "at":
                at_id = int(seg.data.get("qq", 0))
                break
        amt_str = _re.sub(r'[^0-9]', '', text)
        amt = int(amt_str) if amt_str else 0
        if not at_id:
            parts = text.split()
            if parts and parts[0].isdigit():
                at_id = int(parts[0])
        if not at_id or amt < 10:
            await rps_cmd.finish("格式: 猜拳 @某人 金额 (最低10PC)")
        if at_id == event.user_id:
            await rps_cmd.finish("不能和自己猜拳")
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (event.user_id,))
                    row = await cur.fetchone()
                    if not row or row[0] < amt:
                        await rps_cmd.finish("余额不足")
        else:
            data = economy._read_local()
            uid_str = str(event.user_id)
            if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < amt:
                await rps_cmd.finish("余额不足")
        rps_games[event.user_id] = {"target": at_id, "amount": amt}
        await rps_cmd.finish(f"猜拳发起，赌注 {amt} PC\n对手请发送 石头、剪刀 或 布")
    await safe_execute(rps_cmd, _f)

stone_cmd = on_command("石头", priority=5, block=True)
@stone_cmd.handle()
async def _(bot, event):
    await _rps_move(bot, event, 0)

scissors_cmd = on_command("剪刀", priority=5, block=True)
@scissors_cmd.handle()
async def _(bot, event):
    await _rps_move(bot, event, 1)

paper_cmd = on_command("布", priority=5, block=True)
@paper_cmd.handle()
async def _(bot, event):
    await _rps_move(bot, event, 2)

async def _rps_move(bot, event, move):
    uid = event.user_id
    challenger = None
    for cid, game in list(rps_games.items()):
        if game["target"] == uid:
            challenger = cid
            break
    if not challenger:
        return
    game = rps_games.pop(challenger)
    amt = game["amount"]
    p1, p2 = move, random.randint(0, 2)
    names = {0: "石头", 1: "剪刀", 2: "布"}
    if p1 == p2:
        await event.reply(f"平局，都是{names[p1]}")
    elif (p1 == 0 and p2 == 1) or (p1 == 1 and p2 == 2) or (p1 == 2 and p2 == 0):
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (amt, uid))
                    await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (amt, challenger))
        else:
            data = economy._read_local()
            data["user_economy"][str(uid)]["balance"] += amt
            data["user_economy"][str(challenger)]["balance"] -= amt
            economy._write_local(data)
        await event.reply(f"你赢了，{names[p1]} vs {names[p2]}\n获得 {amt} PC")
    else:
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (amt, uid))
                    await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (amt, challenger))
        else:
            data = economy._read_local()
            data["user_economy"][str(uid)]["balance"] -= amt
            data["user_economy"][str(challenger)]["balance"] += amt
            economy._write_local(data)
        await event.reply(f"你输了，{names[p1]} vs {names[p2]}\n失去 {amt} PC")

gacha_cmd = on_command("单抽", aliases={"抽卡"}, priority=5, block=True)
@gacha_cmd.handle()
async def _(bot, event):
    async def _f():
        if not pjsk_card_pool:
            await gacha_cmd.finish("卡牌池未加载")
        inv = await economy.get_inventory(event.user_id)
        has = any(i["id"] == 202 and i["qty"] > 0 for i in inv)
        used_ticket = has
        if has:
            await economy.use_item(event.user_id, 202)
        else:
            if economy.pool:
                async with economy.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (event.user_id,))
                        row = await cur.fetchone()
                        if not row or row[0] < 50:
                            await gacha_cmd.finish("余额不足")
                        await cur.execute("UPDATE user_economy SET balance=balance-50 WHERE user_id=%s", (event.user_id,))
                        await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (event.user_id, -50, "PJSK单抽"))
            else:
                data = economy._read_local()
                uid_str = str(event.user_id)
                if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < 50:
                    await gacha_cmd.finish("余额不足")
                data["user_economy"][uid_str]["balance"] -= 50
                data["economy_logs"].append({"user_id": event.user_id, "amount": -50, "description": "PJSK单抽"})
                economy._write_local(data)
        results = gacha_pull(1)
        card = results[0]
        await economy.add_card(event.user_id, card["id"])
        img_bytes = await download_card_image(card, PJSK_PROXY_URL)
        img = await draw_card_image(card, card["char_name"], card["rarity_label"], img_bytes)
        desc = "单抽成功，消耗一张单抽券" if used_ticket else "单抽成功，已扣除 50 PC"
        msg = MessageSegment.image(img) + _econ_md(desc, GACHA_BUTTONS)
        await gacha_cmd.finish(msg)
    await safe_execute(gacha_cmd, _f)

ten_cmd = on_command("十连", aliases={"十连抽"}, priority=5, block=True)
@ten_cmd.handle()
async def _(bot, event):
    async def _f():
        if not pjsk_card_pool:
            await ten_cmd.finish("卡牌池未加载")
        inv = await economy.get_inventory(event.user_id)
        has = any(i["id"] == 203 and i["qty"] > 0 for i in inv)
        used_ticket = has
        if has:
            await economy.use_item(event.user_id, 203)
        else:
            if economy.pool:
                async with economy.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (event.user_id,))
                        row = await cur.fetchone()
                        if not row or row[0] < 450:
                            await ten_cmd.finish("余额不足")
                        await cur.execute("UPDATE user_economy SET balance=balance-450 WHERE user_id=%s", (event.user_id,))
                        await cur.execute("INSERT INTO economy_logs (user_id,amount,description) VALUES (%s,%s,%s)", (event.user_id, -450, "PJSK十连"))
            else:
                data = economy._read_local()
                uid_str = str(event.user_id)
                if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < 450:
                    await ten_cmd.finish("余额不足")
                data["user_economy"][uid_str]["balance"] -= 450
                data["economy_logs"].append({"user_id": event.user_id, "amount": -450, "description": "PJSK十连"})
                economy._write_local(data)
        results = gacha_pull(10)
        for card in results:
            await economy.add_card(event.user_id, card["id"])
        card_images = {}
        for card in results:
            ib = await download_card_image(card, PJSK_PROXY_URL)
            if ib:
                card_images[card["asset"]] = ib
        img = await draw_gacha_result(results, card_images)
        desc = "十连成功，消耗一张十连券" if used_ticket else "十连成功，已扣除 450 PC"
        msg = MessageSegment.image(img) + _econ_md(desc, GACHA_BUTTONS)
        await ten_cmd.finish(msg)
    await safe_execute(ten_cmd, _f)

mycards_cmd = on_command("我的卡牌", aliases={"卡牌", "卡牌图鉴"}, priority=5, block=True)
@mycards_cmd.handle()
async def _(bot, event):
    async def _f():
        cards = await economy.get_user_cards(event.user_id)
        if not cards:
            await mycards_cmd.finish(_econ_md("你目前还没有获得任何卡牌。发送 单抽 / 十连 开始抽取吧！", GACHA_BUTTONS))
        cards_with_info = []
        for cid, qty in cards:
            cinfo = pjsk_card_by_id.get(cid)
            if cinfo:
                cards_with_info.append({"info": cinfo, "qty": qty})
        if not cards_with_info:
            await mycards_cmd.finish(_econ_md("你目前还没有获得任何卡牌。发送 单抽 / 十连 开始抽取吧！", GACHA_BUTTONS))
        img = await draw_card_collection(get_user_name(event), cards_with_info)
        msg = MessageSegment.image(img) + _econ_md("我的卡牌图鉴", GACHA_BUTTONS)
        await mycards_cmd.finish(msg)
    await safe_execute(mycards_cmd, _f)

change_theme = on_command("切换主题", priority=5, block=True)
@change_theme.handle()
async def handle_change_theme(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    t = args.extract_plain_text().strip()
    if not t.isdigit():
        await change_theme.finish("格式: 切换主题 主题ID (0: 默认粉色, 1: 天蓝色, 2: 浅紫色, 3: 薄荷绿, 4: 暗黑夜)")
    tid = int(t)
    if tid not in [0, 1, 2, 3, 4]:
        await change_theme.finish("主题ID范围为 0-4")
    try:
        if economy.pool:
            async with economy.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("UPDATE user_economy SET theme=%s WHERE user_id=%s", (tid, event.user_id))
        else:
            data = economy._read_local()
            uid_str = str(event.user_id)
            if uid_str in data["user_economy"]:
                data["user_economy"][uid_str]["theme"] = tid
                economy._write_local(data)
        await change_theme.finish(f"主题已切换为 {tid}")
    except (FinishedException, RejectedException, PausedException):
        raise
    except Exception as e:
        await change_theme.finish(f"切换主题出错: {str(e)}")

set_bg = on_command("设置背景", priority=5, block=True)
@set_bg.handle()
async def handle_set_bg(bot: Bot, event: MessageEvent):
    img_url = None
    for seg in event.message:
        if seg.type == "image":
            img_url = seg.data.get("url")
            break
    if not img_url:
        await set_bg.finish("请在发送 设置背景 时附带一张图片")
    bg_dir = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    save_path = bg_dir / f"{event.user_id}.png"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(img_url, timeout=10)
            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(r.content)
                await set_bg.finish("自定义背景设置成功，发送 个人信息 查看效果")
            else:
                await set_bg.finish("图片下载失败，请重试")
    except (FinishedException, RejectedException, PausedException):
        raise
    except Exception as e:
        await set_bg.finish(f"设置背景出错: {str(e)}")

try:
    from nonebot import get_app
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    app = get_app()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    @app.get("/economy/rank")
    async def api_economy_rank():
        if not economy:
            return JSONResponse({"code": 500, "msg": "DB not connected", "data": []})
        try:
            data = await economy.get_leaderboard(100)
            return JSONResponse({"code": 200, "msg": "success", "data": data})
        except Exception as e:
            return JSONResponse({"code": 500, "msg": str(e), "data": []})
except Exception as e:
    pass
