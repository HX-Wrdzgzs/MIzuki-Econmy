import aiomysql
import random
import datetime
import string
import json
import os
from pathlib import Path
from .const import LEVEL_TITLES, SHOP_ITEMS, PJSK_CARDS_URL, RARITY_MAP, CHAR_MAP

ITEM_MAP = {item["id"]: item for item in SHOP_ITEMS}

class EconomyManager:
    def __init__(self, pool: aiomysql.Pool = None):
        self.pool = pool
        self.local_path = Path(__file__).parent.parent.parent.parent / "data" / "mizuki_econmy" / "local_db.json"
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.local_path.exists():
            self._write_local({
                "user_economy": {},
                "user_inventory": {},
                "user_cards": {},
                "economy_logs": [],
                "daily_tasks": {},
                "user_achievements": {},
                "farm_plots": [],
                "user_pets": {},
                "raid_participants": [],
                "stock_holdings": {},
                "auction_listings": [],
                "economy_diaries": [],
                "diary_likes": {},
                "economy_cdk": {}
            })

    def _read_local(self):
        try:
            with open(self.local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "user_economy": {},
                "user_inventory": {},
                "user_cards": {},
                "economy_logs": [],
                "daily_tasks": {},
                "user_achievements": {},
                "farm_plots": [],
                "user_pets": {},
                "raid_participants": [],
                "stock_holdings": {},
                "auction_listings": [],
                "economy_diaries": [],
                "diary_likes": {},
                "economy_cdk": {}
            }

    def _write_local(self, data):
        try:
            with open(self.local_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    async def sync_local_to_db(self):
        if not self.pool or not self.local_path.exists():
            return
        data = self._read_local()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for uid_str, ue in data["user_economy"].items():
                    await cur.execute("""
                        INSERT INTO user_economy (
                            user_id, user_name, balance, level, xp, stamina, prof_physical, prof_social, prof_tech,
                            today_luck, today_quote, today_good, today_bad, last_sign_date, active_title, theme, sign_streak
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            user_name=%s, balance=balance+%s, level=GREATEST(level, %s), xp=%s, today_luck=%s, today_quote=%s,
                            today_good=%s, today_bad=%s, last_sign_date=%s, active_title=%s, theme=%s, sign_streak=GREATEST(sign_streak, %s)
                    """, (
                        ue["user_id"], ue["user_name"], ue["balance"], ue["level"], ue["xp"], ue["stamina"],
                        ue["prof_physical"], ue["prof_social"], ue["prof_tech"], ue["today_luck"], ue["today_quote"],
                        ue["today_good"], ue["today_bad"], ue["last_sign_date"], ue["active_title"], ue["theme"], ue["sign_streak"],
                        ue["user_name"], ue["balance"], ue["level"], ue["xp"], ue["today_luck"], ue["today_quote"],
                        ue["today_good"], ue["today_bad"], ue["last_sign_date"], ue["active_title"], ue["theme"], ue["sign_streak"]
                    ))
                for key, qty in data["user_inventory"].items():
                    parts = key.split("_")
                    if len(parts) == 2:
                        await cur.execute("""
                            INSERT INTO user_inventory (user_id, item_id, quantity)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE quantity = quantity + %s
                        """, (int(parts[0]), int(parts[1]), qty, qty))
                for key, qty in data["user_cards"].items():
                    parts = key.split("_")
                    if len(parts) == 2:
                        await cur.execute("""
                            INSERT INTO user_cards (user_id, card_id, quantity)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE quantity = quantity + %s
                        """, (int(parts[0]), int(parts[1]), qty, qty))
                for log in data["economy_logs"]:
                    await cur.execute("""
                        INSERT INTO economy_logs (user_id, amount, description)
                        VALUES (%s, %s, %s)
                    """, (log["user_id"], log["amount"], log["description"]))
        try:
            os.remove(self.local_path)
        except Exception:
            pass

    async def init_tables(self):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SET sql_notes = 0")
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
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS economy_v50 (
                        user_id BIGINT PRIMARY KEY,
                        user_name VARCHAR(255) NOT NULL,
                        group_id BIGINT NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                await cur.execute("CREATE TABLE IF NOT EXISTS economy_loans (id INT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT NOT NULL, amount INT NOT NULL, due_date DATETIME NOT NULL, status VARCHAR(16) DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS daily_tasks (user_id BIGINT NOT NULL, task_id VARCHAR(32) NOT NULL, task_date DATE NOT NULL, completed TINYINT DEFAULT 0, claimed TINYINT DEFAULT 0, PRIMARY KEY (user_id, task_id, task_date)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS user_achievements (user_id BIGINT NOT NULL, achievement_id VARCHAR(32) NOT NULL, unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, achievement_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS farm_plots (id INT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT NOT NULL, crop_id VARCHAR(8) NOT NULL, planted_at DATETIME NOT NULL, status VARCHAR(16) DEFAULT 'growing') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS user_pets (user_id BIGINT PRIMARY KEY, pet_type VARCHAR(8) NOT NULL, pet_name VARCHAR(32) DEFAULT '', hunger INT DEFAULT 50, happiness INT DEFAULT 50, level INT DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS raid_participants (id INT AUTO_INCREMENT PRIMARY KEY, raid_id VARCHAR(32) NOT NULL, user_id BIGINT NOT NULL, damage INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS stock_holdings (user_id BIGINT NOT NULL, stock_id VARCHAR(8) NOT NULL, quantity INT DEFAULT 0, PRIMARY KEY (user_id, stock_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS auction_listings (id INT AUTO_INCREMENT PRIMARY KEY, seller_id BIGINT NOT NULL, item_id INT NOT NULL, min_price INT NOT NULL, current_price INT NOT NULL, current_bidder BIGINT, end_time DATETIME NOT NULL, status VARCHAR(16) DEFAULT 'active') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS economy_diaries (id INT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT NOT NULL, content TEXT NOT NULL, likes INT DEFAULT 0, is_anonymous TINYINT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("CREATE TABLE IF NOT EXISTS diary_likes (diary_id INT NOT NULL, user_id BIGINT NOT NULL, liked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (diary_id, user_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
                await cur.execute("""CREATE TABLE IF NOT EXISTS economy_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    amount INT DEFAULT 0,
                    description VARCHAR(255) DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_economy (
                        user_id BIGINT PRIMARY KEY,
                        user_name VARCHAR(255) DEFAULT '',
                        balance INT DEFAULT 0,
                        level INT DEFAULT 1,
                        xp INT DEFAULT 0,
                        stamina INT DEFAULT 100,
                        last_stamina_update DATETIME NULL,
                        prof_physical INT DEFAULT 0,
                        prof_social INT DEFAULT 0,
                        prof_tech INT DEFAULT 0,
                        today_luck INT DEFAULT 0,
                        today_quote TEXT,
                        today_good VARCHAR(255) DEFAULT '',
                        today_bad VARCHAR(255) DEFAULT '',
                        last_sign_date DATE NULL,
                        last_work_time DATETIME NULL,
                        active_title VARCHAR(255) DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                new_columns = [
                    ("active_theme", "INT DEFAULT 0"), ("theme", "INT DEFAULT 0"),
                    ("theme_expire", "DATETIME NULL"), ("buff_social_succ", "INT DEFAULT 0"),
                    ("buff_tech_succ", "INT DEFAULT 0"), ("buff_no_injury", "INT DEFAULT 0"),
                    ("buff_exp_up", "INT DEFAULT 0"), ("buff_pc_up", "INT DEFAULT 0"),
                    ("buff_sta_half", "INT DEFAULT 0"),
                    ("sign_streak", "INT DEFAULT 0")
                ]
                for col_name, col_type in new_columns:
                    try:
                        await cur.execute(f"ALTER TABLE user_economy ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass
                await cur.execute("SET sql_notes = 1")

    async def init_cards_table(self):
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SET sql_notes = 0")
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_cards (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        card_id INT NOT NULL,
                        quantity INT DEFAULT 1,
                        UNIQUE KEY `uid_cid` (`user_id`, `card_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                await cur.execute("SET sql_notes = 1")

    async def sign_in(self, user_id: int, user_name: str, luck: int, quote: str, good: str, bad: str):
        if self.pool:
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
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                data["user_economy"][uid_str] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "balance": 0,
                    "level": 1,
                    "xp": 0,
                    "stamina": 100,
                    "last_stamina_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "prof_physical": 0,
                    "prof_social": 0,
                    "prof_tech": 0,
                    "today_luck": luck,
                    "today_quote": quote,
                    "today_good": good,
                    "today_bad": bad,
                    "last_sign_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "active_title": "迷途的随从",
                    "theme": 0,
                    "sign_streak": 1
                }
            else:
                ue = data["user_economy"][uid_str]
                ue["user_name"] = user_name
                ue["today_luck"] = luck
                ue["today_quote"] = quote
                ue["today_good"] = good
                ue["today_bad"] = bad
                ue["last_sign_date"] = datetime.date.today().strftime("%Y-%m-%d")
            
            ue = data["user_economy"][uid_str]
            ue["xp"] += 20
            while ue["xp"] >= (ue["level"] + 1) * 100 and ue["level"] < 100:
                ue["xp"] -= (ue["level"] + 1) * 100
                ue["level"] += 1
            self._write_local(data)
            return ue["level"], ue["xp"], ue["active_title"]

    async def _add_xp(self, cur, user_id, amount):
        await cur.execute("SELECT level, xp FROM user_economy WHERE user_id = %s", (user_id,))
        row = await cur.fetchone()
        lvl, xp = row if row else (1, 0)
        xp += amount
        leveled_up = False
        while xp >= (lvl + 1) * 100 and lvl < 100:
            xp -= (lvl + 1) * 100
            lvl += 1
            leveled_up = True
        await cur.execute("UPDATE user_economy SET level=%s, xp=%s WHERE user_id=%s", (lvl, xp, user_id))
        return lvl, xp, leveled_up

    async def get_user_detail(self, user_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT level, xp, balance, stamina, active_title, prof_physical, prof_tech, prof_social,
                        DATE_FORMAT(created_at, '%%Y-%%m-%%d'), theme FROM user_economy WHERE user_id=%s
                    """, (user_id,))
                    user_row = await cur.fetchone()
                    if not user_row:
                        return None
                    await cur.execute("SELECT DATE_FORMAT(created_at, '%%m-%%d'), amount, description FROM economy_logs WHERE user_id=%s ORDER BY id DESC LIMIT 5", (user_id,))
                    logs = await cur.fetchall()
                    return {"lvl": user_row[0], "xp": user_row[1], "bal": user_row[2], "sta": user_row[3], "title": user_row[4],
                            "prof": [user_row[5], user_row[6], user_row[7]], "reg_date": user_row[8], "theme": user_row[9], "logs": logs}
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                return None
            ue = data["user_economy"][uid_str]
            logs = []
            for log in data["economy_logs"]:
                if log["user_id"] == user_id:
                    logs.append((datetime.datetime.now().strftime("%m-%d"), log["amount"], log["description"]))
            return {
                "lvl": ue["level"], "xp": ue["xp"], "bal": ue["balance"], "sta": ue["stamina"], "title": ue["active_title"],
                "prof": [ue["prof_physical"], ue["prof_tech"], ue["prof_social"]], "reg_date": datetime.date.today().strftime("%Y-%m-%d"), "theme": ue["theme"], "logs": logs[:5]
            }

    async def work_process(self, user_id: int, user_name: str, jobs_dict: dict):
        if self.pool:
            STA_MAX = 100
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("INSERT IGNORE INTO user_economy (user_id, user_name) VALUES (%s,%s)", (user_id, user_name))
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
                            if recover > 0:
                                curr_sta = min(STA_MAX, curr_sta + recover)
                        job_keys = list(jobs_dict.keys())
                        work_times, succ_times, fail_times = 0, 0, 0
                        total_reward, total_xp, total_cost = 0, 0, 0
                        while True:
                            min_req = 10 if b_sta > 0 else 20
                            if curr_sta < min_req:
                                break
                            max_possible = min(50, curr_sta if b_sta == 0 else curr_sta * 2)
                            raw_cost = random.randint(20, max_possible)
                            sta_cost = max(1, raw_cost // 2) if b_sta > 0 else raw_cost
                            if curr_sta < sta_cost:
                                break
                            job_cfg = jobs_dict[random.choice(job_keys)]
                            prof_key = job_cfg["key"]
                            prof = prof_phys if prof_key == "prof_physical" else (prof_soc if prof_key == "prof_social" else prof_tech)
                            curr_sta -= sta_cost
                            total_cost += sta_cost
                            work_times += 1
                            base_rate = 0.85 + (0.1 if luck > 80 else 0) - (0.1 if luck < 20 else 0)
                            if prof_key == "prof_social" and b_soc > 0:
                                base_rate += 0.20
                            if prof_key == "prof_tech" and b_tech > 0:
                                base_rate += 0.20
                            if random.random() < base_rate:
                                succ_times += 1
                                reward = random.randint(5, 15) + (prof // 10)
                                if b_pc > 0:
                                    reward *= 2
                                    b_pc -= 1
                                prof_gain = 2 if (good_evt and prof_key in good_evt) else 1
                                xp_gain = prof_gain * 10
                                if b_exp > 0:
                                    xp_gain *= 2
                                    b_exp -= 1
                                total_reward += reward
                                total_xp += xp_gain
                                if prof_key == "prof_physical":
                                    prof_phys += prof_gain
                                elif prof_key == "prof_social":
                                    prof_soc += prof_gain
                                else:
                                    prof_tech += prof_gain
                                if b_sta > 0:
                                    b_sta -= 1
                                if prof_key == "prof_social" and b_soc > 0:
                                    b_soc -= 1
                                if prof_key == "prof_tech" and b_tech > 0:
                                    b_tech -= 1
                            else:
                                fail_times += 1
                                if b_inj > 0:
                                    b_inj -= 1
                                    reward = 0
                                else:
                                    reward = -random.randint(5, 10)
                                total_reward += reward
                                total_xp += 2
                                if b_sta > 0:
                                    b_sta -= 1
                        if work_times == 0:
                            await conn.rollback()
                            return {"status": "failed", "msg": f"体力不足，当前体力：{curr_sta}"}
                        bal = max(0, bal + total_reward)
                        lvl, xp, lvled = await self._add_xp(cur, user_id, total_xp)
                        await cur.execute("""
                            UPDATE user_economy SET
                            balance=%s, stamina=%s, prof_physical=%s, prof_social=%s, prof_tech=%s,
                            buff_social_succ=%s, buff_tech_succ=%s, buff_no_injury=%s, buff_exp_up=%s, buff_pc_up=%s, buff_sta_half=%s,
                            last_stamina_update=%s, last_work_time=NOW()
                            WHERE user_id=%s
                        """, (bal, curr_sta, prof_phys, prof_soc, prof_tech, b_soc, b_tech, b_inj, b_exp, b_pc, b_sta, now, user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, total_reward, f"一键打工(执行{work_times}次)"))
                        await conn.commit()
                        return {"status": "success", "msg": f"连续执行了 {work_times} 次委托 (成功 {succ_times} 次，失败/受伤 {fail_times} 次)。", "reward": total_reward, "stamina": curr_sta, "cost": total_cost, "xp_add": total_xp, "leveled": lvled, "lvl": lvl}
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                return {"status": "failed", "msg": "请先签到"}
            ue = data["user_economy"][uid_str]
            xp_gain = 20
            reward = 30
            ue["balance"] += reward
            ue["xp"] += xp_gain
            leveled = False
            while ue["xp"] >= (ue["level"] + 1) * 100 and ue["level"] < 100:
                ue["xp"] -= (ue["level"] + 1) * 100
                ue["level"] += 1
                leveled = True
            data["economy_logs"].append({
                "user_id": user_id,
                "amount": reward,
                "description": "打工"
            })
            self._write_local(data)
            return {"status": "success", "msg": "连续执行了 1 次委托 (成功 1 次，失败 0 次)。", "reward": reward, "stamina": ue["stamina"], "cost": 20, "xp_add": xp_gain, "leveled": leveled, "lvl": ue["level"]}

    async def get_shop_info(self, user_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT balance, level FROM user_economy WHERE user_id=%s", (user_id,))
                    row = await cur.fetchone()
                    return row if row else (0, 0)
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str in data["user_economy"]:
                ue = data["user_economy"][uid_str]
                return ue["balance"], ue["level"]
            return 0, 1

    async def buy_item(self, user_id: int, item_id: int):
        if item_id not in ITEM_MAP:
            return {"status": False, "msg": "商品编号不存在"}
        item = ITEM_MAP[item_id]
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("SELECT balance, level FROM user_economy WHERE user_id=%s FOR UPDATE", (user_id,))
                        row = await cur.fetchone()
                        if not row:
                            return {"status": False, "msg": "尚未注册经济系统，请先签到"}
                        bal, lvl = row
                        if lvl < item["lv"]:
                            return {"status": False, "msg": f"等级不足，该商品需要 Lv.{item['lv']} 才能购买"}
                        if bal < item["price"]:
                            return {"status": False, "msg": f"PC 余额不足，需要 {item['price']} PC"}
                        await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (item["price"], user_id))
                        await cur.execute("INSERT INTO user_inventory (user_id, item_id, quantity) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE quantity = quantity + 1", (user_id, item_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, -item["price"], f"商城购买: {item['name']}"))
                        await conn.commit()
                        return {"status": True, "msg": f"已扣除 {item['price']} PC，获得：[{item['name']}]"}
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                return {"status": False, "msg": "尚未注册经济系统，请先签到"}
            ue = data["user_economy"][uid_str]
            if ue["level"] < item["lv"]:
                return {"status": False, "msg": f"等级不足，该商品需要 Lv.{item['lv']} 才能购买"}
            if ue["balance"] < item["price"]:
                return {"status": False, "msg": f"PC 余额不足，需要 {item['price']} PC"}
            ue["balance"] -= item["price"]
            key = f"{user_id}_{item_id}"
            data["user_inventory"][key] = data["user_inventory"].get(key, 0) + 1
            data["economy_logs"].append({
                "user_id": user_id,
                "amount": -item["price"],
                "description": f"商城购买: {item['name']}"
            })
            self._write_local(data)
            return {"status": True, "msg": f"已扣除 {item['price']} PC，获得：[{item['name']}]"}

    async def get_inventory(self, user_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT item_id, quantity FROM user_inventory WHERE user_id=%s AND quantity > 0", (user_id,))
                    rows = await cur.fetchall()
                    return [{"id": r[0], "qty": r[1], "info": ITEM_MAP[r[0]]} for r in rows if r[0] in ITEM_MAP]
        else:
            data = self._read_local()
            res = []
            for key, qty in data["user_inventory"].items():
                parts = key.split("_")
                if len(parts) == 2 and int(parts[0]) == user_id and qty > 0:
                    item_id = int(parts[1])
                    if item_id in ITEM_MAP:
                        res.append({"id": item_id, "qty": qty, "info": ITEM_MAP[item_id]})
            return res

    async def use_item(self, user_id: int, item_id: int):
        if item_id not in ITEM_MAP:
            return {"status": False, "msg": "物品无效"}
        item = ITEM_MAP[item_id]
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("SELECT quantity FROM user_inventory WHERE user_id=%s AND item_id=%s FOR UPDATE", (user_id, item_id))
                        row = await cur.fetchone()
                        if not row or row[0] <= 0:
                            return {"status": False, "msg": "🎒 你没有该物品"}
                        await cur.execute("UPDATE user_inventory SET quantity=quantity-1 WHERE user_id=%s AND item_id=%s", (user_id, item_id))
                        await conn.commit()
                        return {"status": True, "msg": f"成功使用了 [{item['name']}]"}
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            key = f"{user_id}_{item_id}"
            if data["user_inventory"].get(key, 0) <= 0:
                return {"status": False, "msg": "🎒 你没有该物品"}
            data["user_inventory"][key] -= 1
            self._write_local(data)
            return {"status": True, "msg": f"成功使用了 [{item['name']}]"}

    async def use_item_effect(self, user_id, item_id):
        if item_id not in ITEM_MAP:
            return "物品不存在"
        item = ITEM_MAP[item_id]
        name = item["name"]
        stamina_gains = {101: 30, 102: 20, 104: 40, 105: 50, 106: 100, 107: 10, 109: 80, 110: 100}
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT stamina, balance, active_title, today_luck, prof_physical, prof_social, prof_tech FROM user_economy WHERE user_id=%s", (user_id,))
                    row = await cur.fetchone()
                    if not row:
                        return "请先签到以注册账户"
                    sta, bal, title, luck, p_phys, p_soc, p_tech = row
                    if item_id in stamina_gains:
                        gain = stamina_gains[item_id]
                        new_sta = min(100, sta + gain)
                        await cur.execute("UPDATE user_economy SET stamina=%s WHERE user_id=%s", (new_sta, user_id))
                        if item_id == 110:
                            await cur.execute("UPDATE user_economy SET today_luck=100 WHERE user_id=%s", (user_id,))
                        return f"使用了 {name}，恢复了 {gain} 点体力。"
                    elif item_id == 108:
                        new_luck = random.randint(1, 100)
                        await cur.execute("UPDATE user_economy SET today_luck=%s WHERE user_id=%s", (new_luck, user_id))
                        return f"使用了 {name}，今日运势重置为 {new_luck}。"
                    elif item_id in [202, 203, 204, 205, 210, 201, 206]:
                        if item_id == 201:
                            await cur.execute("UPDATE user_economy SET buff_social_succ=buff_social_succ+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 202:
                            await cur.execute("UPDATE user_economy SET buff_no_injury=buff_no_injury+3 WHERE user_id=%s", (user_id,))
                        elif item_id == 203:
                            await cur.execute("UPDATE user_economy SET buff_exp_up=buff_exp_up+3 WHERE user_id=%s", (user_id,))
                        elif item_id == 204:
                            await cur.execute("UPDATE user_economy SET buff_exp_up=buff_exp_up+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 205:
                            await cur.execute("UPDATE user_economy SET buff_pc_up=buff_pc_up+3 WHERE user_id=%s", (user_id,))
                        elif item_id == 206:
                            await cur.execute("UPDATE user_economy SET buff_tech_succ=buff_tech_succ+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 210:
                            await cur.execute("UPDATE user_economy SET buff_sta_half=buff_sta_half+3 WHERE user_id=%s", (user_id,))
                        return f"使用了 {name}，增益状态已生效。"
                    elif item_id in [301, 302, 303, 304, 305, 306, 310]:
                        if item_id == 301:
                            await cur.execute("UPDATE user_economy SET prof_physical=prof_physical+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 302:
                            await cur.execute("UPDATE user_economy SET prof_social=prof_social+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 303:
                            await cur.execute("UPDATE user_economy SET prof_tech=prof_tech+5 WHERE user_id=%s", (user_id,))
                        elif item_id == 304:
                            await cur.execute("UPDATE user_economy SET prof_physical=prof_physical+10 WHERE user_id=%s", (user_id,))
                        elif item_id == 305:
                            await cur.execute("UPDATE user_economy SET prof_social=prof_social+10 WHERE user_id=%s", (user_id,))
                        elif item_id == 306:
                            await cur.execute("UPDATE user_economy SET prof_tech=prof_tech+10 WHERE user_id=%s", (user_id,))
                        elif item_id == 310:
                            await cur.execute("UPDATE user_economy SET prof_physical=prof_physical+10, prof_social=prof_social+10, prof_tech=prof_tech+10 WHERE user_id=%s", (user_id,))
                        return f"使用了 {name}，打工熟练度已永久提升。"
                    elif name.startswith("主题:"):
                        theme_map = {"主题:晨曦白": 1, "主题:暮色紫": 2, "主题:极光绿": 3, "主题:深夜黑": 4, "主题:最终乐章·金": 0}
                        tid = theme_map.get(name, 0)
                        await cur.execute("UPDATE user_economy SET theme=%s WHERE user_id=%s", (tid, user_id))
                        return f"使用了 {name}，个人中心背景主题已变更。"
                    elif name.startswith("称号:"):
                        tname = name.split(":")[-1]
                        await cur.execute("UPDATE user_economy SET active_title=%s WHERE user_id=%s", (tname, user_id))
                        return f"使用了 {name}，获得了专属称号 [{tname}]。"
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str in data["user_economy"]:
                ue = data["user_economy"][uid_str]
                if item_id in stamina_gains:
                    gain = stamina_gains[item_id]
                    ue["stamina"] = min(100, ue["stamina"] + gain)
                    if item_id == 110:
                        ue["today_luck"] = 100
                    self._write_local(data)
                    return f"使用了 {name}，恢复了 {gain} 点体力。"
                elif item_id == 108:
                    new_luck = random.randint(1, 100)
                    ue["today_luck"] = new_luck
                    self._write_local(data)
                    return f"使用了 {name}，今日运势重置为 {new_luck}。"
                elif name.startswith("主题:"):
                    theme_map = {"主题:晨曦白": 1, "主题:暮色紫": 2, "主题:极光绿": 3, "主题:深夜黑": 4, "主题:最终乐章·金": 0}
                    tid = theme_map.get(name, 0)
                    ue["theme"] = tid
                    self._write_local(data)
                    return f"使用了 {name}，个人中心背景主题已变更。"
                elif name.startswith("称号:"):
                    tname = name.split(":")[-1]
                    ue["active_title"] = tname
                    self._write_local(data)
                    return f"使用了 {name}，获得了专属称号 [{tname}]。"
        return f"使用了 {name}"

    async def add_card(self, user_id: int, card_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO user_cards (user_id, card_id, quantity)
                        VALUES (%s, %s, 1)
                        ON DUPLICATE KEY UPDATE quantity = quantity + 1
                    """, (user_id, card_id))
        else:
            data = self._read_local()
            key = f"{user_id}_{card_id}"
            data["user_cards"][key] = data["user_cards"].get(key, 0) + 1
            self._write_local(data)

    async def get_user_cards(self, user_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT card_id, quantity FROM user_cards WHERE user_id=%s", (user_id,))
                    return await cur.fetchall()
        else:
            data = self._read_local()
            res = []
            for key, qty in data["user_cards"].items():
                parts = key.split("_")
                if len(parts) == 2 and int(parts[0]) == user_id:
                    res.append((int(parts[1]), qty))
            return res

    async def get_card_count(self, user_id: int, card_id: int) -> int:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT quantity FROM user_cards WHERE user_id=%s AND card_id=%s", (user_id, card_id))
                    row = await cur.fetchone()
                    return row[0] if row else 0
        else:
            data = self._read_local()
            return data["user_cards"].get(f"{user_id}_{card_id}", 0)

    async def get_leaderboard(self, limit: int = 100):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT user_id, user_name, level, balance, active_title, DATE_FORMAT(created_at, '%%Y-%%m-%%d')
                        FROM user_economy
                        ORDER BY balance DESC, level DESC
                        LIMIT %s
                    """, (limit,))
                    rows = await cur.fetchall()
                    result = []
                    for idx, r in enumerate(rows):
                        result.append({
                            "rank": idx + 1,
                            "user_id": str(r[0]),
                            "name": r[1],
                            "level": r[2],
                            "score": r[3],
                            "title": r[4] if r[4] else "",
                            "join_date": r[5] if r[5] else "未知"
                        })
                    return result
        else:
            data = self._read_local()
            users = list(data["user_economy"].values())
            users.sort(key=lambda x: (x["balance"], x["level"]), reverse=True)
            result = []
            for idx, u in enumerate(users[:limit]):
                result.append({
                    "rank": idx + 1,
                    "user_id": str(u["user_id"]),
                    "name": u["user_name"],
                    "level": u["level"],
                    "score": u["balance"],
                    "title": u["active_title"],
                    "join_date": datetime.date.today().strftime("%Y-%m-%d")
                })
            return result

    async def get_sign_dates(self, user_id: int) -> set:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT DISTINCT DATE(created_at) FROM economy_logs
                        WHERE user_id=%s AND description LIKE '%%签到%%' AND created_at >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
                    """, (user_id,))
                    rows = await cur.fetchall()
                    return {r[0] for r in rows if r[0]}
        else:
            return {datetime.date.today()}

    async def get_sign_streak(self, user_id: int) -> int:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT sign_streak FROM user_economy WHERE user_id=%s", (user_id,))
                    row = await cur.fetchone()
                    return row[0] if row else 0
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str in data["user_economy"]:
                return data["user_economy"][uid_str]["sign_streak"]
            return 0

    async def transfer_pc(self, from_id, to_id, amount):
        tax = max(1, int(amount * 0.02))
        total = amount + tax
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT user_id, balance FROM user_economy WHERE user_id IN (%s,%s) FOR UPDATE", (from_id, to_id))
                    rows = {r[0]: r[1] for r in await cur.fetchall()}
                    if from_id not in rows or rows[from_id] < total:
                        return {"ok": False, "msg": f"余额不足，需要 {total} PC"}
                    if to_id not in rows:
                        return {"ok": False, "msg": "对方未注册"}
                    await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (total, from_id))
                    await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (amount, to_id))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s,%s,%s)", (from_id, -total, f"转账给{to_id}"))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s,%s,%s)", (to_id, amount, f"收到{from_id}转账"))
                    return {"ok": True, "msg": "转账成功"}
        else:
            data = self._read_local()
            f_str, t_str = str(from_id), str(to_id)
            if f_str not in data["user_economy"] or data["user_economy"][f_str]["balance"] < total:
                return {"ok": False, "msg": f"余额不足，需要 {total} PC"}
            if t_str not in data["user_economy"]:
                return {"ok": False, "msg": "对方未注册"}
            data["user_economy"][f_str]["balance"] -= total
            data["user_economy"][t_str]["balance"] += amount
            data["economy_logs"].append({"user_id": from_id, "amount": -total, "description": f"转账给{to_id}"})
            data["economy_logs"].append({"user_id": to_id, "amount": amount, "description": f"收到{from_id}转账"})
            self._write_local(data)
            return {"ok": True, "msg": "转账成功"}

    async def settle_pk(self, challenger_id: int, target_id: int, amount: int) -> dict:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("SELECT user_id, user_name, balance FROM user_economy WHERE user_id IN (%s, %s) FOR UPDATE", (challenger_id, target_id))
                        rows = await cur.fetchall()
                        user_dict = {row[0]: {"name": row[1], "bal": row[2]} for row in rows}
                        if challenger_id not in user_dict or target_id not in user_dict:
                            await conn.rollback()
                            return {"status": False, "msg": "对方未注册"}
                        if user_dict[challenger_id]["bal"] < amount or user_dict[target_id]["bal"] < amount:
                            await conn.rollback()
                            return {"status": False, "msg": "余额不足"}
                        if random.random() < 0.5:
                            winner_id, loser_id = challenger_id, target_id
                        else:
                            winner_id, loser_id = target_id, challenger_id
                        tax = max(1, int(amount * 0.3))
                        win_net = amount - tax
                        await cur.execute("UPDATE user_economy SET balance = balance + %s WHERE user_id = %s", (win_net, winner_id))
                        await cur.execute("UPDATE user_economy SET balance = balance - %s WHERE user_id = %s", (amount, loser_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (winner_id, win_net, f"PK决斗战胜 {user_dict[loser_id]['name']}"))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (loser_id, -amount, f"PK决斗败给 {user_dict[winner_id]['name']}"))
                        await conn.commit()
                        return {
                            "status": True,
                            "winner_id": winner_id, "winner_name": user_dict[winner_id]["name"],
                            "loser_id": loser_id, "loser_name": user_dict[loser_id]["name"],
                            "win_net": win_net, "tax": tax
                        }
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            c_str, t_str = str(challenger_id), str(target_id)
            if c_str not in data["user_economy"] or t_str not in data["user_economy"]:
                return {"status": False, "msg": "对方未注册"}
            if data["user_economy"][c_str]["balance"] < amount or data["user_economy"][t_str]["balance"] < amount:
                return {"status": False, "msg": "余额不足"}
            if random.random() < 0.5:
                winner_id, loser_id = challenger_id, target_id
            else:
                winner_id, loser_id = target_id, challenger_id
            w_str, l_str = str(winner_id), str(loser_id)
            tax = max(1, int(amount * 0.3))
            win_net = amount - tax
            data["user_economy"][w_str]["balance"] += win_net
            data["user_economy"][l_str]["balance"] -= amount
            data["economy_logs"].append({"user_id": winner_id, "amount": win_net, "description": f"PK决斗战胜 {data['user_economy'][l_str]['user_name']}"})
            data["economy_logs"].append({"user_id": loser_id, "amount": -amount, "description": f"PK决斗败给 {data['user_economy'][w_str]['user_name']}"})
            self._write_local(data)
            return {
                "status": True,
                "winner_id": winner_id, "winner_name": data["user_economy"][w_str]["name"],
                "loser_id": loser_id, "loser_name": data["user_economy"][l_str]["name"],
                "win_net": win_net, "tax": tax
            }

    async def get_daily_tasks(self, user_id):
        from .const import DAILY_TASKS
        today = datetime.date.today()
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT task_id, completed, claimed FROM daily_tasks WHERE user_id=%s AND task_date=%s", (user_id, today))
                    existing = {r[0]: (r[1], r[2]) for r in await cur.fetchall()}
                    if not existing:
                        tasks = random.sample(DAILY_TASKS, min(3, len(DAILY_TASKS)))
                        for t in tasks:
                            await cur.execute("INSERT IGNORE INTO daily_tasks (user_id, task_id, task_date) VALUES (%s,%s,%s)", (user_id, t["id"], today))
                        return [(t, 0, 0) for t in tasks]
                    return [(next((t for t in DAILY_TASKS if t["id"] == tid), {"id": tid, "name": tid, "reward": 0}), done, claimed) for tid, (done, claimed) in existing.items()]
        else:
            return []

    async def claim_task_reward(self, user_id, task_id):
        return "本地暂不支持领取任务奖励"

    async def take_loan(self, user_id, amount):
        if amount < 100 or amount > 5000:
            return {"ok": False, "msg": "贷款金额需在100-5000之间"}
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT COUNT(*) FROM economy_loans WHERE user_id=%s AND status='active'", (user_id,))
                    if (await cur.fetchone())[0] > 0:
                        return {"ok": False, "msg": "你已有一笔未还贷款"}
                    await cur.execute("INSERT INTO economy_loans (user_id, amount, due_date, status) VALUES (%s,%s,DATE_ADD(NOW(), INTERVAL 7 DAY),'active')", (user_id, amount))
                    await cur.execute("UPDATE user_economy SET balance=balance+%s WHERE user_id=%s", (amount, user_id))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s,%s,%s)", (user_id, amount, "贷款"))
                    return {"ok": True, "msg": "贷款成功"}
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                return {"ok": False, "msg": "请先签到"}
            data["user_economy"][uid_str]["balance"] += amount
            data["economy_logs"].append({"user_id": user_id, "amount": amount, "description": "贷款"})
            self._write_local(data)
            return {"ok": True, "msg": "贷款成功"}

    async def repay_loan(self, user_id):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT id, amount FROM economy_loans WHERE user_id=%s AND status='active'", (user_id,))
                    loan = await cur.fetchone()
                    if not loan:
                        return {"ok": False, "msg": "没有待还贷款"}
                    repay = int(loan[1] * 1.05)
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s", (user_id,))
                    bal = (await cur.fetchone())[0]
                    if bal < repay:
                        return {"ok": False, "msg": f"余额不足，需要{repay}PC"}
                    await cur.execute("UPDATE user_economy SET balance=balance-%s WHERE user_id=%s", (repay, user_id))
                    await cur.execute("UPDATE economy_loans SET status='paid' WHERE id=%s", (loan[0],))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s,%s,%s)", (user_id, -repay, "还贷"))
                    return {"ok": True, "msg": "还贷成功"}
        else:
            return {"ok": False, "msg": "本地暂不支持还贷"}

    async def send_redpacket(self, user_id: int, total_amount: int, packet_id: str) -> tuple[bool, str]:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s FOR UPDATE", (user_id,))
                        row = await cur.fetchone()
                        if not row or row[0] < total_amount:
                            await conn.rollback()
                            return False, "余额不足"
                        await cur.execute("UPDATE user_economy SET balance = balance - %s WHERE user_id=%s", (total_amount, user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, -total_amount, f"发出红包[SN:{packet_id}]"))
                        await conn.commit()
                        return True, "Success"
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"] or data["user_economy"][uid_str]["balance"] < total_amount:
                return False, "余额不足"
            data["user_economy"][uid_str]["balance"] -= total_amount
            data["economy_logs"].append({"user_id": user_id, "amount": -total_amount, "description": f"发出红包[SN:{packet_id}]"})
            self._write_local(data)
            return True, "Success"

    async def grab_redpacket(self, user_id: int, user_name: str, grab_amount: int, packet_id: str, sender_name: str):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("INSERT IGNORE INTO user_economy (user_id, user_name) VALUES (%s, %s)", (user_id, user_name))
                        await cur.execute("UPDATE user_economy SET balance = balance + %s WHERE user_id=%s", (grab_amount, user_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, grab_amount, f"抢到{sender_name}的红包[SN:{packet_id}]"))
                        await conn.commit()
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            data = self._read_local()
            uid_str = str(user_id)
            if uid_str not in data["user_economy"]:
                data["user_economy"][uid_str] = {
                    "user_id": user_id, "user_name": user_name, "balance": 0, "level": 1, "xp": 0, "stamina": 100,
                    "prof_physical": 0, "prof_social": 0, "prof_tech": 0, "today_luck": 50, "today_quote": "",
                    "today_good": "", "today_bad": "", "last_sign_date": "", "active_title": "迷途的随从", "theme": 0, "sign_streak": 0
                }
            data["user_economy"][uid_str]["balance"] += grab_amount
            data["economy_logs"].append({"user_id": user_id, "amount": grab_amount, "description": f"抢到{sender_name}的红包[SN:{packet_id}]"})
            self._write_local(data)

    async def join_v50_pool(self, user_id: int, user_name: str, group_id: int) -> dict:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await conn.begin()
                        await cur.execute("SELECT balance FROM user_economy WHERE user_id = %s FOR UPDATE", (user_id,))
                        row = await cur.fetchone()
                        if not row:
                            await conn.rollback()
                            return {"status": "failed", "msg": "尚未注册经济系统，请先签到"}
                        if row[0] < 200:
                            await conn.rollback()
                            return {"status": "failed", "msg": f"押注不足，需要 200 PC"}
                        await cur.execute("SELECT user_id FROM economy_v50 WHERE user_id = %s", (user_id,))
                        if await cur.fetchone():
                            await conn.rollback()
                            return {"status": "failed", "msg": "已经报名过了"}
                        await cur.execute("UPDATE user_economy SET balance = balance - 200 WHERE user_id = %s", (user_id,))
                        await cur.execute("INSERT INTO economy_v50 (user_id, user_name, group_id) VALUES (%s, %s, %s)", (user_id, user_name, group_id))
                        await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, %s, %s)", (user_id, -200, "v50集资筹码"))
                        await conn.commit()
                        return {"status": "success", "msg": "报名成功"}
                    except Exception:
                        await conn.rollback()
                        raise
        else:
            return {"status": "failed", "msg": "本地暂不支持该功能"}

    async def execute_v50_draw(self) -> dict:
        return {"status": "empty"}

    async def get_achievements(self, user_id):
        from .const import ACHIEVEMENTS
        return [(a, False) for a in ACHIEVEMENTS]

    async def get_user_cards(self, user_id: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT card_id, quantity FROM user_cards WHERE user_id=%s", (user_id,))
                    return await cur.fetchall()
        else:
            data = self._read_local()
            res = []
            for key, qty in data["user_cards"].items():
                parts = key.split("_")
                if len(parts) == 2 and int(parts[0]) == user_id:
                    res.append((int(parts[1]), qty))
            return res

    async def get_card_count(self, user_id: int, card_id: int) -> int:
        if self.pool:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT quantity FROM user_cards WHERE user_id=%s AND card_id=%s", (user_id, card_id))
                    row = await cur.fetchone()
                    return row[0] if row else 0
        else:
            data = self._read_local()
            return data["user_cards"].get(f"{user_id}_{card_id}", 0)

    async def synthesize_cards(self, user_id, star):
        if not self.pool:
            return {"msg": "本地暂不支持卡牌合成"}
        from .__init__ import pjsk_card_pool
        target_ids = {c["id"] for c in pjsk_card_pool if c["star"] == star}
        if not target_ids:
            return {"msg": "没有找到该星级的卡牌池"}
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await conn.begin()
                    await cur.execute("SELECT balance FROM user_economy WHERE user_id=%s FOR UPDATE", (user_id,))
                    row = await cur.fetchone()
                    if not row or row[0] < 100:
                        await conn.rollback()
                        return {"msg": "余额不足，需要 100 PC"}
                    await cur.execute("SELECT card_id, quantity FROM user_cards WHERE user_id=%s FOR UPDATE", (user_id,))
                    user_cards = await cur.fetchall()
                    valid_owned = []
                    for cid, qty in user_cards:
                        if cid in target_ids:
                            valid_owned.extend([cid] * qty)
                    if len(valid_owned) < 3:
                        await conn.rollback()
                        return {"msg": f"你拥有的 {star} 星卡牌不足 3 张 (当前仅有 {len(valid_owned)} 张)"}
                    to_consume = random.sample(valid_owned, 3)
                    for cid in to_consume:
                        await cur.execute("UPDATE user_cards SET quantity = quantity - 1 WHERE user_id=%s AND card_id=%s", (user_id, cid))
                    await cur.execute("DELETE FROM user_cards WHERE user_id=%s AND quantity <= 0", (user_id,))
                    next_star = star + 1
                    reward_pool = [c["id"] for c in pjsk_card_pool if c["star"] == next_star]
                    if not reward_pool:
                        await conn.rollback()
                        return {"msg": f"没有更高星级的卡牌可以合成"}
                    new_card_id = random.choice(reward_pool)
                    await cur.execute("""
                        INSERT INTO user_cards (user_id, card_id, quantity)
                        VALUES (%s, %s, 1)
                        ON DUPLICATE KEY UPDATE quantity = quantity + 1
                    """, (user_id, new_card_id))
                    await cur.execute("UPDATE user_economy SET balance = balance - 100 WHERE user_id=%s", (user_id,))
                    await cur.execute("INSERT INTO economy_logs (user_id, amount, description) VALUES (%s, -100, '卡牌合成')", (user_id,))
                    await conn.commit()
                    new_card_info = next(c for c in pjsk_card_pool if c["id"] == new_card_id)
                    return {"msg": f"合成成功！消耗 100 PC 和 3 张 {star} 星卡牌，获得了 {next_star} 星卡牌: [{new_card_info['title']}] {new_card_info['char_name']}"}
                except Exception as e:
                    await conn.rollback()
                    return {"msg": f"合成失败: {str(e)}"}

    async def get_farm(self, user_id):
        return []

    async def plant_crop(self, user_id, crop_id):
        return "本地暂不支持该功能"

    async def harvest_crops(self, user_id):
        return "没有成熟的作物"

    async def adopt_pet(self, user_id, pet_type):
        return "本地暂不支持该功能"

    async def feed_pet(self, user_id):
        return "本地暂不支持该功能"

    async def get_pet(self, user_id):
        return None

    async def join_raid(self, user_id, boss_id):
        return "本地暂不支持该功能"

    async def get_quiz(self, user_id):
        from .const import QUIZ_BANK
        return QUIZ_BANK[0]

    async def answer_quiz(self, user_id, answer):
        return "本地暂不支持该功能"

    async def explore_area(self, user_id, area_id):
        return "本地暂不支持该功能"

    async def buy_stock(self, user_id, stock_id, qty):
        return {"ok": False, "msg": "本地暂不支持该功能"}

    async def sell_stock(self, user_id, stock_id, qty):
        return {"ok": False, "msg": "本地暂不支持该功能"}

    async def get_holdings(self, user_id):
        return []

    async def create_auction(self, user_id, item_id, price, hours):
        return "本地暂不支持该功能"

    async def bid_auction(self, user_id, auction_id, amount):
        return "本地暂不支持该功能"

    async def write_diary(self, user_id, content, is_anonymous=0):
        return "本地暂不支持该功能"

    async def like_diary(self, user_id, diary_id):
        return "本地暂不支持该功能"

    async def get_diaries(self, limit=10):
        return []
