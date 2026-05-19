# mizuki_econmy/__init__.py
import random
import datetime
import aiomysql
import traceback
import asyncio
import time
from nonebot import on_command, get_plugin_config, get_driver, logger, get_bots
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.exception import FinishedException, RejectedException, PausedException

from .config import Config
from .model import EconomyManager
from .draw import draw_sign_card, draw_profile_card, draw_work_card, draw_shop_menu, draw_inventory_card
from .const import QUOTES, FORTUNE_EVENTS, JOBS

# 引入官方封装模块
from maimai_sync.lib_msg import _sorted_markdown_segment

from nonebot.plugin import PluginMetadata
__plugin_meta__ = PluginMetadata(name="Mizuki Econmy", description="25时经济系统", usage="签到, 打工, 个人信息, pk, 发红包, 抢红包, v50报名, 经济帮助")

economy = None 
plugin_config = get_plugin_config(Config)

# 官方机器人的 QQ 号，只有该 Bot 会发送 Markdown 与按钮
OFFICIAL_BOT_ID = "3889004352"

# 内存队列与对决缓存
group_envelopes = {}
pending_pks = {}

# ==================== 全局标准按钮库 ====================
ECONOMY_BUTTONS = [
    {"render_data.label": "📝 签到", "action.data": "签到"},
    {"render_data.label": "💼 打工", "action.data": "打工"},
    {"render_data.label": "📊 个人信息", "action.data": "个人信息"},
    {"render_data.label": "🎒 我的背包", "action.data": "我的背包"},
    {"render_data.label": "⚔️ 发起PK", "action.data": "pk "},
    {"render_data.label": "🍗 v50报名", "action.data": "v50报名"},
    {"render_data.label": "🧧 发红包", "action.data": "发红包 "},
    {"render_data.label": "🛒 网页商城", "action.data": "https://store.mizuki.top", "action.type": 0}
]

@get_driver().on_startup
async def init_db():
    global economy
    try:
        pool = await aiomysql.create_pool(
            host=plugin_config.sign_mysql_host, port=plugin_config.sign_mysql_port,
            user=plugin_config.sign_mysql_user, password=plugin_config.sign_mysql_password,
            db=plugin_config.sign_mysql_db, autocommit=True, minsize=3, maxsize=20, pool_recycle=3600
        )
        economy = EconomyManager(pool)
        await economy.init_tables()
        logger.opt(colors=True).success("<g>[MizukiEconmy] 数据库初始化成功</g>")
        
        # 激活星期四定时任务
        init_v50_scheduler()
    except Exception as e:
        logger.error(f"[MizukiEconmy] 数据库连接失败: {e}")

async def safe_execute(matcher, func, *args, **kwargs):
    if not economy: await matcher.finish("⚠️ 数据库未连接。")
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=10.0)
    except (FinishedException, RejectedException, PausedException):
        raise
    except asyncio.TimeoutError:
        await matcher.finish("⚠️ 系统拥堵告警：底层响应超时。")
    except Exception:
        err_msg = traceback.format_exc()
        await matcher.finish(f"❌ 内部执行崩溃：\n{err_msg[:150]}...")

# ==================== 智能获取用户名模块 ====================
def get_user_name(event: MessageEvent) -> str:
    name = getattr(event.sender, "card", "") or getattr(event.sender, "nickname", "")
    return name if name else str(event.user_id)

# ==================== 疯狂星期四 APScheduler 广播核心 ====================
def init_v50_scheduler():
    try:
        from nonebot_plugin_apscheduler import scheduler
        
        @scheduler.scheduled_job("cron", day_of_week="wed", hour=18, minute=0, id="v50_wed_notice")
        async def v50_wed_notice():
            text = (
                "### 🍗 疯狂星期四 V我50 全服大乐透 🍗\n\n"
                "> 系统已开启新一轮 **KFC Crazy Thursday** 全服集资狂欢！\n"
                "> 💰 **入场筹码**：押注 `200 PC` 投入公共底池。\n"
                "> 🎁 **绝大暴利**：明天中午 12:00 准时开奖，全服仅抽一位幸运儿独揽全部 PC！\n"
                "> 到底谁能白嫖肯德基？赶快点击下方按钮一键报名参战！"
            )
            await global_broadcast(text, [{"render_data.label": "🍗 投入200PC报名", "action.data": "v50报名"}])

        @scheduler.scheduled_job("cron", day_of_week="thu", hour=9, minute=0, id="v50_thu_notice")
        async def v50_thu_notice():
            text = (
                "### 🔔 疯狂星期四：最后报名倒计时 🔔\n\n"
                "> 今天中午 **12:00** 准时截断并现场开奖！\n"
                "> 错过了就要再等一周，抓紧最后机会上车看谁是终极白嫖王！"
            )
            await global_broadcast(text, [{"render_data.label": "🍗 赶在开奖前上车", "action.data": "v50报名"}])

        @scheduler.scheduled_job("cron", day_of_week="thu", hour=12, minute=0, id="v50_draw_job")
        async def v50_draw_job():
            if not economy: return
            res = await economy.execute_v50_draw()
            if res["status"] == "empty":
                text = "### 🍗 疯狂星期四·开奖流产 🍗\n\n> 本周全服没有任何玩家加入 v50 奖池，天选之子落空！"
                await global_broadcast(text, [{"render_data.label": "📝 去签到攒点钱", "action.data": "签到"}])
                return
            
            text = (
                "### 🎉 疯狂星期四·v50 开奖宣告 🎉\n\n"
                "> 千呼万唤始出来！本周全服大乐透集资结果正式揭晓！\n"
                f"> 📊 **数据统计**：全服共 **{res['count']}** 位群友参与众筹\n"
                f"> 💰 **终极大奖**：总计 **{res['pool']} PC** 奖池！\n"
                f"> 🏅 **天选之子**：祝贺来自群【{res['winner_group']}】的 **{res['winner_name']}** 成功独揽全部奖金！\n"
                "> V我50的梦想已由系统全额打入你的账户，赶紧去消费吧！"
            )
            await global_broadcast(text, [{"render_data.label": "📊 查看个人资产", "action.data": "个人信息"}])
            
        logger.info("[MizukiEconmy] 疯狂星期四定时任务链挂载完毕")
    except Exception as e:
        logger.error(f"[MizukiEconmy] 挂载定时任务失败: {e}")

async def global_broadcast(text: str, extra_btns: list):
    bots = get_bots()
    if not bots: return
    for bot_id, bot in bots.items():
        try:
            group_list = await bot.get_group_list()
            if str(bot_id) == OFFICIAL_BOT_ID:
                msg = _sorted_markdown_segment(text, extra_btns)
            else:
                plain = text.replace("### ", "").replace("> ", "").replace("**", "").replace("<", "").replace(">", "")
                msg = Message(plain)
                
            for group in group_list:
                try:
                    await bot.send_group_msg(group_id=group["group_id"], message=msg)
                    await asyncio.sleep(0.4)
                except: pass
        except Exception as e:
            logger.error(f"全服群发广播出现异常: {e}")

# ==================== 经济帮助 ====================
help_cmd = on_command("经济帮助", aliases={"25时经济系统", "经济菜单"}, priority=5, block=True)
@help_cmd.handle()
async def handle_economy_help(bot: Bot, event: MessageEvent):
    text = (
        "### 🎧 25时·Nightcord 经济系统 🎧\n"
        f"> @{get_user_name(event)} 有事@即可一键被哄睡\n\n"
        "### 💰 基础指令\n"
        "> 📝 **签到**：抽取运势，获取 PC 与经验\n"
        "> 💼 **打工**：一键循环消耗体力赚取 PC\n"
        "> 📊 **个人信息**：查看等级、资产与近期账单\n"
        "> 🎒 **我的背包**：查看已购买的道具存量\n\n"
        "### 🛒 消费与互动\n"
        "> 🛒 **经济商城**：购买补给与专属外观 (指令: `购买 编号`)\n"
        "> ⚔️ **pk**：长按对方消息【回复】，或 `@某人 pk` (赌注 10~1000)\n"
        "> 🍗 **v50报名**：扣除 200 PC 押金参与周四大乐透\n"
        "> 🧧 **发红包/抢红包**：`发红包 金额 份数` (含 5% 税)\n\n"
        "### 🔗 相关链接\n"
        "> 🔗 实时榜单：<https://list.mizuki.top>\n"
        "> 🛒 网页商城：<https://store.mizuki.top>\n"
    )
    
    if str(bot.self_id) == OFFICIAL_BOT_ID:
        await help_cmd.finish(_sorted_markdown_segment(text, ECONOMY_BUTTONS.copy()))
    else:
        plain = text.replace("### ", "").replace("> ", "").replace("**", "").replace("<", "").replace(">", "")
        await help_cmd.finish(plain)

# ==================== 友人对战 (PK 系统) ====================
pk_cmd = on_command("pk", aliases={"决斗", "对决"}, priority=5, block=True)
@pk_cmd.handle()
async def handle_pk(bot: Bot, event: MessageEvent):
    target_id = None
    
    # 策略 1：引用回复检测（针对官方 Bot 防吞最稳妥方案）
    if event.reply:
        target_id = event.reply.sender.user_id
        
    # 策略 2：原始消息体 AT 节点扫描
    if not target_id:
        msg_obj = getattr(event, "original_message", event.message)
        for seg in msg_obj:
            if seg.type == "at":
                qq_str = str(seg.data.get("qq", ""))
                if qq_str and qq_str != "all" and qq_str != str(bot.self_id):
                    target_id = int(qq_str)
                    break
                    
    if not target_id: 
        await pk_cmd.finish("⚠️ 官方接口容易吞 @ 符号！\n👉 请**长按你要对决的友人的消息选择【回复】，然后 @我 输入 pk**！")
    if target_id == event.user_id: 
        await pk_cmd.finish("⚠️ 你不能和自己进行对决！")
        
    amount = random.randint(10, 1000)
    pending_pks[target_id] = {"challenger": event.user_id, "challenger_name": get_user_name(event), "amount": amount}
    
    # 分流渲染决斗邀请
    if str(bot.self_id) == OFFICIAL_BOT_ID:
        txt = (
            f"### ⚔️ 生死决斗邀请 ⚔️\n"
            f"> {get_user_name(event)} 向你发起了对决挑战！\n"
            f"> 🎲 系统生成筹码：**{amount} PC**\n"
            f"> ⚖️ 赢方将扣除 30% 系统手续税。\n"
            f"> 👉 请点击下方按钮或在聊天框回复「接受pk / 拒绝pk」"
        )
        pk_choices = [
            {"render_data.label": "✅ 接受决斗", "action.data": "接受pk"},
            {"render_data.label": "❌ 怯战拒绝", "action.data": "拒绝pk", "render_data.style": 0}
        ]
        await pk_cmd.finish(Message(MessageSegment.at(target_id) + _sorted_markdown_segment(txt, pk_choices)))
    else:
        msg = (MessageSegment.at(target_id) + 
               f"\n⚔️ {get_user_name(event)} 向你发起了生死决斗！\n"
               f"🎲 系统随机生成赌注：{amount} PC\n"
               f"(赢方将收取 30% 手续费)\n"
               f"👉 请回复「接受pk」或「拒绝pk」")
        await pk_cmd.finish(msg)

accept_pk_cmd = on_command("接受pk", aliases={"接受对决"}, priority=5, block=True)
@accept_pk_cmd.handle()
async def handle_accept(bot: Bot, event: MessageEvent):
    target_id = event.user_id
    if target_id not in pending_pks: await accept_pk_cmd.finish("⚠️ 没有等待你处理的对决邀请。")
        
    pk_data = pending_pks.pop(target_id)
    async def _logic():
        res = await economy.settle_pk(pk_data["challenger"], target_id, pk_data["amount"])
        if not res["status"]: await accept_pk_cmd.finish(res["msg"])
            
        txt = (
            f"### ⚔️ 决斗结算报告 ⚔️\n"
            f"> 🏅 **胜者**：{res['winner_name']}\n"
            f"> 💀 **败者**：{res['loser_name']}\n\n"
            f"> 🎉 赢家掠夺了 **{res['win_net']} PC** (已扣税 {res['tax']} PC)\n"
            f"> 📉 输家丢失了 **{pk_data['amount']} PC**"
        )
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            await accept_pk_cmd.finish(_sorted_markdown_segment(txt, ECONOMY_BUTTONS.copy()))
        else:
            await accept_pk_cmd.finish(txt.replace("### ", "").replace("> ", "").replace("**", ""))
    await safe_execute(accept_pk_cmd, _logic)

refuse_pk_cmd = on_command("拒绝pk", aliases={"拒绝对决"}, priority=5, block=True)
@refuse_pk_cmd.handle()
async def handle_refuse(bot: Bot, event: MessageEvent):
    if event.user_id in pending_pks:
        pending_pks.pop(event.user_id)
        await refuse_pk_cmd.finish("✅ 你已怯战并拒绝了该对决。")
    else:
        await refuse_pk_cmd.finish("⚠️ 没有等待你处理的对决邀请。")

# ==================== v50 手动报名响应 ====================
v50_join_cmd = on_command("v50报名", aliases={"参与v50", "v我50"}, priority=5, block=True)
@v50_join_cmd.handle()
async def handle_v50_join(bot: Bot, event: MessageEvent):
    group_id = getattr(event, "group_id", 0)
    if not group_id:
        await v50_join_cmd.finish("⚠️ 该疯狂星期四众筹抽奖活动仅限在群聊中参与。")
        
    async def _logic():
        res = await economy.join_v50_pool(event.user_id, get_user_name(event), group_id)
        
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            msg = _sorted_markdown_segment(f"### 🍗 V50 报名\n> {res['msg']}", ECONOMY_BUTTONS.copy())
            await v50_join_cmd.finish(msg)
        else:
            await v50_join_cmd.finish(res["msg"])
            
    await safe_execute(v50_join_cmd, _logic)

# ==================== 签到 & 个人信息 ====================
sign_cmd = on_command("签到", priority=5, block=True)
@sign_cmd.handle()
async def handle_sign(bot: Bot, event: MessageEvent):
    async def _logic():
        user_id, user_name = event.user_id, get_user_name(event)
        today = datetime.date.today()
        async with economy.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT last_sign_date FROM user_economy WHERE user_id=%s", (user_id,))
                row = await cur.fetchone()
                if row and row[0] == today: await sign_cmd.finish("今天已经去过 SEKAI 了，明天再来吧。")
        
        pc_reward = random.randint(5, 20)
        luck = random.randint(0, 100)
        quote, evt = random.choice(QUOTES), random.choice(FORTUNE_EVENTS)
        quote_str = f"{quote[1]} | {quote[2]}"
        
        lvl, xp, title = await economy.sign_in(user_id, user_name, luck, quote_str, evt['good'], evt['bad'])
        
        async with economy.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE user_economy SET balance = balance + %s WHERE user_id=%s", (pc_reward, user_id))
        
        img = await draw_sign_card(user_id, user_name, {"title": title, "luck": luck, "quote": quote_str, "good": evt['good'], "bad": evt['bad'], "lvl": lvl, "xp": xp, "pc_add": pc_reward})
        
        msg = Message(MessageSegment.image(img))
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            msg += _sorted_markdown_segment("### ✅ 签到成功", ECONOMY_BUTTONS.copy())
            
        await sign_cmd.finish(msg)
    await safe_execute(sign_cmd, _logic)

info_cmd = on_command("个人信息", aliases={"余额", "查询"}, priority=5, block=True)
@info_cmd.handle()
async def handle_info(bot: Bot, event: MessageEvent):
    async def _logic():
        data = await economy.get_user_detail(event.user_id)
        if not data: await info_cmd.finish("暂无数据，请先签到注册。")
        async with economy.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT theme, theme_expire FROM user_economy WHERE user_id=%s", (event.user_id,))
                row = await cur.fetchone()
                theme_id = row[0] if row and row[0] else 0
                if row and row[1] and datetime.datetime.now() > row[1]:
                    theme_id = 0
                    await cur.execute("UPDATE user_economy SET theme=0, theme_expire=NULL WHERE user_id=%s", (event.user_id,))
                data['theme'] = theme_id
        img = await draw_profile_card(event.user_id, get_user_name(event), data)
        
        msg = Message(MessageSegment.image(img))
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            msg += _sorted_markdown_segment("### 🔗 实时榜单: <https://list.mizuki.top>", ECONOMY_BUTTONS.copy())
        else:
            msg += Message("\n🔗 实时榜单: https://list.mizuki.top")
            
        await info_cmd.finish(msg)
    await safe_execute(info_cmd, _logic)

# ==================== 打工系统 ====================
work_cmd = on_command("打工", priority=5, block=True)
@work_cmd.handle()
async def handle_work(bot: Bot, event: MessageEvent):
    async def _logic():
        res = await economy.work_process(event.user_id, get_user_name(event), JOBS)
        if res.get("status") == "failed": 
            await work_cmd.finish(res["msg"])
        
        img = await draw_work_card(get_user_name(event), "汇总", res)
        
        msg = Message(MessageSegment.image(img))
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            msg += _sorted_markdown_segment("### 💼 打工结算完成", ECONOMY_BUTTONS.copy())
            
        await work_cmd.finish(msg)
    await safe_execute(work_cmd, _logic)

# ==================== 红包系统 (含 5% 手续费) ====================
send_re_cmd = on_command("发红包", priority=5, block=True)
@send_re_cmd.handle()
async def handle_send_re(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id, user_id = event.group_id, event.user_id
    try:
        parts = args.extract_plain_text().strip().split()
        if len(parts) != 2: raise ValueError
        total_amount, count = int(parts[0]), int(parts[1])
        if count < 1 or count > 50 or total_amount < 10: raise ValueError
    except:
        await send_re_cmd.finish("⚠️ 格式：发红包 <总金额> <份数>")

    tax = max(1, int(total_amount * 0.05))
    pool = total_amount - tax
    if pool < count: await send_re_cmd.finish(f"⚠️ 余额不足以分成这么多份。")

    async def _logic():
        async with economy.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (user_id,))
                row = await cur.fetchone()
                if not row or row[0] < total_amount: await send_re_cmd.finish(f"❌ 余额不足！")
                await cur.execute("UPDATE user_economy SET balance = balance - %s WHERE user_id=%s", (total_amount, user_id))
                await conn.commit()

        remain_amt, remain_cnt = pool, count
        parts_list = []
        for _ in range(count - 1):
            val = random.randint(1, max(1, (remain_amt // remain_cnt) * 2))
            parts_list.append(val)
            remain_amt -= val; remain_cnt -= 1
        parts_list.append(remain_amt); random.shuffle(parts_list)

        if group_id not in group_envelopes: group_envelopes[group_id] = []
        group_envelopes[group_id].append({"id": f"{user_id}_{int(time.time())}", "sender_name": get_user_name(event), "parts": parts_list, "grabbed_by": set()})
        
        txt = f"### 🧧 {get_user_name(event)} 发送了红包！\n> 总额：{total_amount} PC (已扣税 {tax})\n> 快点击下方「抢红包」来瓜分吧！"
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            await send_re_cmd.finish(Message(_sorted_markdown_segment(txt, [{"render_data.label": "抢红包", "action.data": "抢红包"}])))
        else:
            await send_re_cmd.finish(txt.replace("### ", "").replace("> ", ""))
            
    await safe_execute(send_re_cmd, _logic)

grab_re_cmd = on_command("抢红包", priority=5, block=True)
@grab_re_cmd.handle()
async def handle_grab_re(bot: Bot, event: GroupMessageEvent):
    group_id, user_id = event.group_id, event.user_id
    if group_id not in group_envelopes or not group_envelopes[group_id]: await grab_re_cmd.finish("⚠️ 没红包啦。")
    env = group_envelopes[group_id][-1]
    if user_id in env["grabbed_by"]: await grab_re_cmd.finish("⚠️ 抢过啦！")
    if not env["parts"]: await grab_re_cmd.finish("抢光了 😭")

    grab_amount = env["parts"].pop(0); env["grabbed_by"].add(user_id)
    if not env["parts"]: group_envelopes[group_id].remove(env)

    async def _logic():
        async with economy.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT IGNORE INTO user_economy (user_id, user_name) VALUES (%s, %s)", (user_id, get_user_name(event)))
                await cur.execute("UPDATE user_economy SET balance = balance + %s WHERE user_id=%s", (grab_amount, user_id))
                await conn.commit()
                
        txt = f"### 🧧 恭喜！\n> 抢到了 {env['sender_name']} 的 {grab_amount} PC 💰"
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            await grab_re_cmd.finish(Message(_sorted_markdown_segment(txt, ECONOMY_BUTTONS.copy())))
        else:
            await grab_re_cmd.finish(txt.replace("### ", "").replace("> ", ""))
            
    await safe_execute(grab_re_cmd, _logic)

inventory_cmd = on_command("我的背包", aliases={"背包"}, priority=5, block=True)
@inventory_cmd.handle()
async def handle_inventory(bot: Bot, event: MessageEvent):
    async def _logic():
        bal, lvl = await economy.get_shop_info(event.user_id)
        items = await economy.get_inventory(event.user_id)
        img = await draw_inventory_card(get_user_name(event), bal, lvl, items)
        
        msg = Message(MessageSegment.image(img))
        if str(bot.self_id) == OFFICIAL_BOT_ID:
            msg += _sorted_markdown_segment("### 🎒 背包查询完毕", ECONOMY_BUTTONS.copy())
            
        await inventory_cmd.finish(msg)
    await safe_execute(inventory_cmd, _logic)

cancel_cmd = on_command("取消", aliases={"退出", "quit", "重置"}, priority=1, block=True)
@cancel_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await cancel_cmd.finish("✅ 已清理。")
