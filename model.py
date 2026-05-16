# mizuki_econmy/model.py
import aiomysql
import random
import datetime
import string
from .const import LEVEL_TITLES, SHOP_ITEMS

ITEM_MAP = {item["id"]: item for item in SHOP_ITEMS}

class EconomyManager:
    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_inventory (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        item_id INT NOT NULL,
                        quantity INT DEFAULT 0,
                        UNIQUE KEY `uid_iid` (`user_id`, `item_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS economy_cdk (
                        cdk VARCHAR(16) PRIMARY KEY,
                        item_id INT NOT NULL,
                        expire_time DATETIME NOT NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 建立 v50 报名池表
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS economy_v50 (
                        user_id BIGINT PRIMARY KEY,
                        user_name VARCHAR(255) NOT NULL,
                        group_id BIGINT NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                new_columns = [
                    ("active_theme", "INT DEFAULT 0"), ("theme", "INT DEFAULT 0"),
                    ("theme_expire", "DATETIME NULL"), ("buff_social_succ", "INT DEFAULT 0"),
                    ("buff_tech_succ", "INT DEFAULT 0"), ("buff_no_injury", "INT DEFAULT 0"),
                    ("buff_exp_up", "INT DEFAULT 0"), ("buff_pc_up", "INT DEFAULT 0"),
                    ("buff_sta_half", "INT DEFAULT 0")
                ]
                for col_name, col_type in new_columns:
                    try: await cur.execute(f"ALTER TABLE user_economy ADD COLUMN {col_name} {col_type}")
                    except Exception: pass 

    def _generate_cdk_string(self) -> str:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    async def create_cdk(self, item_id: int, valid_hours: int) -> str:
        if item_id not in ITEM_MAP: return "❌ 物品ID不存在，无法生成。"
        cdk = self._generate_cdk_string()
        expire_time = datetime.datetime.now() + datetime.timedelta(hours=valid_hours)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO economy_cdk (cdk, item_id, expire_time) VALUES (%s, %s, %s)", (cdk, item_id, expire_time))
                await conn.commit()
        return f"✅ 兑换码生成成功！\n🔑 CDK: {cdk}\n🎁 物品: [{ITEM_MAP[item_id]['name']}]\n⏳ 有效期: {valid_hours} 小时"

    async def check_cdk(self, cdk: str) -> str:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM economy_cdk WHERE expire_time < NOW()")
                await cur.execute("SELECT item_id, expire_time FROM economy_cdk WHERE cdk = %s", (cdk,))
                row = await cur.fetchone()
                if not row: return "❌ 该兑换码无效、已被使用或已过期。"
                return f"🔍 兑换码 status：\n🔑 CDK: {cdk}\n🎁 包含物品: [{ITEM_MAP.get(row[0], {'name': '未知'})['name']}]\n⏳ 过期时间: {row[1]}"

    async def delete_cdk(self, cdk: str) -> str:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM economy_cdk WHERE cdk = %s", (cdk,))
                if cur.rowcount > 0:
                    await conn.commit()
                    return f"✅ 兑换码 {cdk} 已被销毁。"
                return "❌ 未找到该兑换码。"

    async def redeem_cdk(self, user_id: int, cdk: str) -> dict:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("DELETE FROM economy_cdk WHERE expire_time < NOW()")
                    await cur.execute("SELECT item_id FROM economy_cdk WHERE cdk = %s FOR UPDATE", (cdk,))
                    row = await cur.fetchone()
                    if not row:
                        await conn.rollback()
                        return {"status": False, "msg": "❌ 兑换码无效或已过期。"}
                    
                    item_id = row[0]
                    await cur.execute("INSERT INTO user_inventory (user_id, item_id, quantity) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE quantity = quantity + 1", (user_id, item_id))
                    await cur.execute("DELETE FROM economy_cdk WHERE cdk = %s", (cdk,))
                    await conn.commit()
                    return {"status": True, "msg": f"🎉 兑换成功！你获得了：[{ITEM_MAP.get(item_id, {'name': '未知'})['name']}]。"}
                except Exception as e:
                    await conn.rollback(); raise e

    async def _add_xp(self, cur, user_id, amount):
        await cur.execute("SELECT level, xp FROM user_economy WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        lvl, xp = row if row else (0, 0)
        xp += amount
        leveled_up = False
        while xp >= (lvl + 1) * 100 and lvl < 100:
            xp -= (lvl + 1) * 100
            lvl += 1
            leveled_up = True
            
        await cur.execute("UPDATE user_economy SET level=%s, xp=%s WHERE user_id=%s", (lvl, xp, user_id))
        if leveled_up:
            for req_lv, title in LEVEL_TITLES.items():
                if lvl >= req_lv:
                    await cur.execute("INSERT IGNORE INTO user_titles (user_id, title_name) VALUES (%s, %s)", (user_id, title))
        return lvl, xp, leveled_up

    # ================= 疯狂星期四 v50 核心逻辑 =================
    async def join_v50_pool(self, user_id: int, user_name: str, group_id: int) -> dict:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id = %s FOR UPDATE", (user_id,))
                    row = await cur.fetchone()
                    if not row:
                        await conn.rollback()
                        return {"status": "failed", "msg": "⚠️ 尚未注册经济系统，请先发送【签到】！"}
                    
                    if row[0] < 200:
                        await conn.rollback()
                        return {"status": "failed", "msg": f"❌ 报名失败：资产不足！需要押注 200 PC，你当前仅有 {row[0]} PC。"}
                    
                    await cur.execute("SELECT user_id FROM economy_v50 WHERE user_id = %s", (user_id,))
                    if await cur.fetchone():
                        await conn.rollback()
                        return {"status": "failed", "msg": "⚠️ 你本周已经报名过了，静候周四开奖即可。"}
                    
                    await cur.execute("UPDATE user_economy SET balance = balance - 200 WHERE user_id = %s", (user_id,))
                    await cur.execute("INSERT INTO economy_v50 (user_id, user_name, group_id) VALUES (%s, %s, %s)", (user_id, user_name, group_id))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, -200, "疯狂星期四v50集资筹码"))
                    await conn.commit()
                    return {"status": "success", "msg": "🎉 成功扣除 200 PC 并加入疯狂星期四候奖池！"}
                except Exception as e:
                    await conn.rollback(); raise e

    async def execute_v50_draw(self) -> dict:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("SELECT user_id, user_name, group_id FROM economy_v50 FOR UPDATE")
                    pool_users = await cur.fetchall()
                    if not pool_users:
                        await conn.rollback()
                        return {"status": "empty"}
                    
                    total_users = len(pool_users)
                    jackpot = total_users * 200
                    
                    winner = random.choice(pool_users)
                    w_id, w_name, w_group = winner
                    
                    await cur.execute("UPDATE user_economy SET balance = balance + %s WHERE user_id = %s", (jackpot, w_id))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (w_id, jackpot, f"疯狂星期四乐透独揽大奖(集资共{total_users}人)"))
                    await cur.execute("TRUNCATE TABLE economy_v50")
                    await conn.commit()
                    return {"status": "success", "winner_id": w_id, "winner_name": w_name, "winner_group": w_group, "count": total_users, "pool": jackpot}
                except Exception as e:
                    await conn.rollback(); raise e

    # ================= 循环打工 =================
    async def work_process(self, user_id: int, user_name: str, jobs_dict: dict):
        STA_MAX = 100
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("INSERT IGNORE INTO user_economy (user_id, user_name) VALUES (%s, %s)", (user_id, user_name))
                    await cur.execute("""
                        SELECT balance, prof_physical, prof_social, prof_tech, today_luck, today_good,
                        buff_social_succ, buff_tech_succ, buff_no_injury, buff_exp_up, buff_pc_up, buff_sta_half,
                        stamina, last_stamina_update
                        FROM user_economy WHERE user_id = %s FOR UPDATE
                    """, (user_id,))
                    row = list(await cur.fetchone())
                    
                    bal = row[0]
                    prof_phys, prof_soc, prof_tech = row[1:4]
                    luck, good_evt = row[4], row[5]
                    b_soc, b_tech, b_inj, b_exp, b_pc, b_sta = row[6:12]
                    curr_sta, last_upd = row[12], row[13]

                    now = datetime.datetime.now()
                    if last_upd:
                        recover = int((now - last_upd).total_seconds() // 300) 
                        if recover > 0: curr_sta = min(STA_MAX, curr_sta + recover)
                    
                    job_keys = list(jobs_dict.keys())
                    work_times, succ_times, fail_times = 0, 0, 0
                    total_reward, total_xp, total_cost = 0, 0, 0

                    while True:
                        min_req = 10 if b_sta > 0 else 20
                        if curr_sta < min_req: break

                        max_possible = min(50, curr_sta if b_sta == 0 else curr_sta * 2)
                        raw_cost = random.randint(20, max_possible)
                        sta_cost = max(1, raw_cost // 2) if b_sta > 0 else raw_cost

                        if curr_sta < sta_cost: break

                        job_cfg = jobs_dict[random.choice(job_keys)]
                        prof_key = job_cfg["key"]
                        prof = prof_phys if prof_key == "prof_physical" else (prof_soc if prof_key == "prof_social" else prof_tech)

                        curr_sta -= sta_cost
                        total_cost += sta_cost
                        work_times += 1

                        base_rate = 0.85 + (0.1 if luck > 80 else 0) - (0.1 if luck < 20 else 0)
                        if prof_key == "prof_social" and b_soc > 0: base_rate += 0.20
                        if prof_key == "prof_tech" and b_tech > 0: base_rate += 0.20
                        
                        if random.random() < base_rate:
                            succ_times += 1
                            reward = random.randint(5, 15) + (prof // 10)
                            if b_pc > 0: reward *= 2; b_pc -= 1
                            prof_gain = 2 if (good_evt and prof_key in good_evt) else 1
                            xp_gain = prof_gain * 10
                            if b_exp > 0: xp_gain *= 2; b_exp -= 1
                            
                            total_reward += reward
                            total_xp += xp_gain
                            if prof_key == "prof_physical": prof_phys += prof_gain
                            elif prof_key == "prof_social": prof_soc += prof_gain
                            else: prof_tech += prof_gain
                            
                            if b_sta > 0: b_sta -= 1
                            if prof_key == "prof_social" and b_soc > 0: b_soc -= 1
                            if prof_key == "prof_tech" and b_tech > 0: b_tech -= 1
                        else:
                            fail_times += 1
                            if b_inj > 0: b_inj -= 1; reward = 0
                            else: reward = -random.randint(5, 10)
                            total_reward += reward
                            total_xp += 2
                            if b_sta > 0: b_sta -= 1

                    if work_times == 0:
                        await conn.rollback()
                        return {"status": "failed", "msg": f"⚠️ 体力不足！打工需要满足最低消耗要求。当前体力：{curr_sta}"}

                    bal = max(0, bal + total_reward)
                    lvl, xp, lvled = await self._add_xp(cur, user_id, total_xp)

                    await cur.execute(f"""
                        UPDATE user_economy SET 
                        balance=%s, stamina=%s, prof_physical=%s, prof_social=%s, prof_tech=%s,
                        buff_social_succ=%s, buff_tech_succ=%s, buff_no_injury=%s, buff_exp_up=%s, buff_pc_up=%s, buff_sta_half=%s,
                        last_stamina_update=%s, last_work_time=NOW()
                        WHERE user_id=%s
                    """, (bal, curr_sta, prof_phys, prof_soc, prof_tech, b_soc, b_tech, b_inj, b_exp, b_pc, b_sta, now, user_id))
                          
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, total_reward, f"一键打工(执行{work_times}次)"))
                    await conn.commit()
                    
                    return {"status": "success", "msg": f"连续执行了 {work_times} 次委托 (成功 {succ_times} 次，失败/受伤 {fail_times} 次)。", "reward": total_reward, "stamina": curr_sta, "cost": total_cost, "xp_add": total_xp, "leveled": lvled, "lvl": lvl}
                except Exception as e:
                    await conn.rollback(); raise e

    # ================= 数据查询与商城 =================
    async def sign_in(self, user_id: int, user_name: str, luck: int, quote: str, good: str, bad: str):
        today = datetime.date.today()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO user_economy (user_id, user_name, today_luck, today_quote, today_good, today_bad, last_sign_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE user_name=%s, today_luck=%s, today_quote=%s, today_good=%s, today_bad=%s, last_sign_date=%s
                """, (user_id, user_name, luck, quote, good, bad, today, user_name, luck, quote, good, bad, today))
                lvl, xp, _ = await self._add_xp(cur, user_id, 20)
                await cur.execute("SELECT active_title FROM user_economy WHERE user_id=%s", (user_id,))
                title_row = await cur.fetchone()
                return lvl, xp, (title_row[0] if title_row else "迷途的随从")

    async def get_user_detail(self, user_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT level, xp, balance, stamina, active_title, prof_physical, prof_tech, prof_social,
                    DATE_FORMAT(created_at, '%%Y-%%m-%%d'), theme FROM user_economy WHERE user_id=%s
                """, (user_id,))
                user_row = await cur.fetchone()
                if not user_row: return None
                await cur.execute("SELECT DATE_FORMAT(created_at, '%%m-%%d'), amount, description FROM economy_logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,))
                logs = await cur.fetchall()
                return {"lvl": user_row[0], "xp": user_row[1], "bal": user_row[2], "sta": user_row[3], "title": user_row[4],
                        "prof": [user_row[5], user_row[6], user_row[7]], "reg_date": user_row[8], "theme": user_row[9], "logs": logs}

    async def buy_item(self, user_id: int, item_id: int):
        if item_id not in ITEM_MAP: return {"status": False, "msg": "❌ 商品不存在。"}
        item = ITEM_MAP[item_id]
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("SELECT balance, level FROM user_economy WHERE user_id=%s FOR UPDATE", (user_id,))
                    row = await cur.fetchone()
                    if not row: return {"status": False, "msg": "⚠️ 请先签到。"}
                    bal, lvl = row
                    if lvl < item["lv"]: return {"status": False, "msg": f"⚠️ 需要 Lv.{item['lv']}。"}
                    if bal < item["price"]: return {"status": False, "msg": f"❌ 余额不足，需 {item['price']} PC。"}
                    
                    await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (item["price"], user_id))
                    await cur.execute("INSERT INTO user_inventory (user_id, item_id, quantity) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE quantity = quantity + 1", (user_id, item_id))
                    await conn.commit()
                    return {"status": True, "msg": f"✅ 购买成功！获得了 [{item['name']}]。"}
                except Exception as e:
                    await conn.rollback(); raise e

    async def get_shop_info(self, user_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT balance, level FROM user_economy WHERE user_id=%s", (user_id,))
                row = await cur.fetchone()
                return row if row else (0, 0)

    async def get_inventory(self, user_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT item_id, quantity FROM user_inventory WHERE user_id=%s AND quantity > 0", (user_id,))
                rows = await cur.fetchall()
                return [{"id": r[0], "qty": r[1], "info": ITEM_MAP[r[0]]} for r in rows if r[0] in ITEM_MAP]

    async def use_item(self, user_id: int, item_id: int):
        if item_id not in ITEM_MAP: return {"status": False, "msg": "❌ 物品无效。"}
        item = ITEM_MAP[item_id]
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("SELECT quantity FROM user_inventory WHERE user_id=%s AND item_id=%s FOR UPDATE", (user_id, item_id))
                    row = await cur.fetchone()
                    if not row or row[0] <= 0: return {"status": False, "msg": "🎒 你没有该物品。"}
                    await cur.execute("UPDATE user_inventory SET quantity=quantity-1 WHERE user_id=%s AND item_id=%s", (user_id, item_id))
                    await conn.commit()
                    return {"status": True, "msg": f"✨ 成功使用了 [{item['name']}]！"}
                except Exception as e:
                    await conn.rollback(); raise e