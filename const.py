import datetime

QUOTES = [
    [1, "……まだ、起きてるの？", "……还醒着吗？"],
    [2, "音乐だけが、私の居場所……", "音乐，是我唯一的容身之处……"],
    [3, "夜が深いほど、気持ちが溢れる……", "夜越深，情绪就越满溢……"],
    [4, "この曲、届くかな……", "这首歌，能传达出去吗……"],
    [5, "闇の中でも、少しだけ光が見える。", "即使在黑暗里，也能看见些许光芒。"],
    [6, "消えたい……じゃなくて、生きたい。", "想消失……不，是想活下去。"],
    [7, "ここには、同じ夜を過ごす人がいる。", "在这里，有人和我度过着同一个深夜。"],
    [8, "音乐がなければ、もう……", "如果没有音乐的话，已经……"],
    [9, "怖い夜だけど、ここだけは安全だよ。", "虽然夜晚令人恐惧，但至少这里是安全的。"],
    [10, "ふふ……まだ見つからない。", "呵呵……还没被发现呢。"],
    [11, "モニターの光が、私の太陽。", "屏幕的光，就是我的太阳。"],
    [12, "あなたの曲、届きました。", "你的曲子，我已经收到了。"],
    [13, "25時——ここでは素颜でいい。", "25时——在这里可以做真实的自己。"],
    [14, "窓の外は真っ暗、でもここには光がある。", "窗外一片漆黑，但这里有光。"],
    [15, "おやすみ……また、明日の夜に。", "晚安……明天夜里再见。"],
]

LEVEL_TITLES = {
    1: "夜の旅人", 5: "夜の探索者", 10: "夜の観察者",
    15: "夜の守護者", 20: "夜の紡ぎ手", 30: "夜の詩人",
    40: "夜の作曲家", 50: "夜の夢見者", 60: "夜の幻影",
    70: "夜の伝説", 80: "夜の神話", 99: "25時からの贈り物"
}

FORTUNE_POOL = [
    "【大吉】闇夜に星が瞬くように、今日は全てが輝く一日。最も暗い場所で、最も美しい光を見つけられる。",
    "【吉】静かな夜に、小さくても確かな一步を。焦らずゆっくり進もう。音乐が道を照らしてくれる。",
    "【中吉】窓の外を眺めて深呼吸。溜め込んだ気持ちを、少し解放していい。",
    "【小吉】深夜の散步で、普段見逃している小さな幸せに気づくかも。",
    "【吉】匿名の誰かが、あなたの曲を聴いて微笑んでいる。それだけで十分。",
    "【大吉】今日は特別な日。夜更けに小さな奇跡が待っている。目を逸らさず受け取って。",
    "【凶】眠れない夜——でも、それは新しい曲の灵感が降りてくる前兆かもしれない。",
    "【半吉】窓の外は真っ暗だけど、ここには光がある。その光を信じて。",
    "【末吉】起きてるだけで偉い。今日はそれだけで十分。",
    "【大凶】消えたい夜——定义、ここで待っていてくれる人がいる。朝まで一緒にいよう。",
    "【吉】不器用でいい。音乐は上手じゃなきゃいけないなんて誰も言ってない。",
    "【中吉】あなたの歌には意味がある。たとえ一人で録っても。",
    "【小吉】目が疲れた？モニターの明るさを少し下げて、温かいお茶でも飲もう。",
    "【吉】逃げ場のない夜だけど、25時では走らなくていい。",
    "【大吉】届けたい気持ちが、今夜誰かの心に届く。信じて。",
    "【半吉】窓に映る自分の顔——疲れてるけど、ちゃんと生きてる顔してる。",
    "【凶】ネットが不安定——でも、この気持ちが途切れることは永远不会。",
    "【末吉】知らない曲を聴いてみよう。新しい世界が待ってるかも。",
    "【中吉】一人じゃないよ。この時間帯に起きてる人が何人もいる。",
    "【吉】あなたの「好き」は間違ってない。たとえ周りが理解しなくても。",
]

DAILY_ITEMS = [
    {"good": "深夜の作曲 | 灵感如泉涌，一气完成了满意的作品", "bad": "早起 | 阳光太刺眼，一整天精神萎靡"},
    {"good": "匿名投稿 | 你的新作品反响极佳，获得大量关注", "bad": "整理桌面 | 不小心删除了重要的工程文件草稿"},
    {"good": "モニター越しのご会話 | 和陌生人聊得很投机，心情舒畅", "bad": "断网 | 语音会议被迫中断，情绪变得烦躁"},
    {"good": "新しいイヤフォンを試す | 音质超群，世界都变清晰了", "bad": "シャワー | 无视了自己的极限，体力大幅下降"},
    {"good": "好きな曲をかける | 周围的人都安静下来聆听着", "bad": "忘れ物 | 忘带重要物品，计划全部推迟"},
    {"good": "夜風に当たる | 凉风吹过，心情奇迹般地平静了", "bad": "コーヒー | 喝多了，心跳加速根本睡不着"},
    {"good": "歌词を書く | 一句话直击灵魂深处", "bad": "鏡を見る | 不小心看到了自己憔悴的脸"},
    {"good": "生放送开始 | 观众人数比平时多了三倍", "bad": "モチベーション | 什么都不想做的瘫痪状态"},
    {"good": "プレイリストを作る | 精心挑选的曲子获得了好评", "bad": "バッテリー切れ | 关键时刻设备没电了"},
    {"good": "夜食を買う | 罕见地买到了限量口味", "bad": "隣人の音 | 隔壁太吵，完全无法集中精神"},
    {"good": "コードを書く | 一次通过，连debug都不用", "bad": "セーブ忘れ | 忘记保存，两小时的工作白费了"},
    {"good": "喜欢的艺术家回复了 | 收到了偶像的私信回复", "bad": "寝坊 | 睡过了约定时间，非常抱歉"},
    {"good": "花を買う | 路边花店还开着，买了一束回来", "bad": "エラー | 频繁出现bug，怎么也修不好"},
    {"good": "朋友と通话 | 久违地和好友打了个电话", "bad": "指が痛い | 弹奏过度，手指隐隐作痛"},
    {"good": "新しい音源を入手 | 找到了一直在找的稀有音源", "bad": "遅延 | 工作进度严重落后"},
    {"good": "深呼吸 | 什么都不想，只是静静呼吸了一会儿", "bad": "ネット炎上 | 不小心卷入了网络纠纷"},
    {"good": "散歩 | 夜晚的街道意外地令人心旷神怡", "bad": "天気 | 突然的暴雨把计划全打乱了"},
    {"good": "ライブ | 意外地获得了前排的机会", "bad": "空腹 | 太专注于作曲而忘记吃饭了"},
    {"good": "新しい服 | 试穿后发现意外地合适", "bad": "財布 | 月末了，钱包空空如也"},
    {"good": "届けた曲がバズった | 发布的歌曲上了热搜", "bad": "眠れない | 怎么也睡不着，盯着天花板到天亮"},
]

SHOP_ITEMS = [
    {"id": 101, "name": "瑞希的起司蛋糕", "price": 60, "lv": 1, "desc": "吃下后可以恢复 30 点体力。", "type": 1},
    {"id": 102, "name": "甜甜圈", "price": 40, "lv": 1, "desc": "普通的甜点，恢复 20 点体力。", "type": 1},
    {"id": 103, "name": "运动饮料", "price": 100, "lv": 5, "desc": "喝下后，1小时内自然体力恢复速度翻倍。", "type": 1},
    {"id": 104, "name": "绘名的能量棒", "price": 80, "lv": 5, "desc": "熬夜画画必备，恢复 40 点体力。", "type": 1},
    {"id": 105, "name": "宵崎家的淡味茶", "price": 100, "lv": 8, "desc": "K泡的茶，非常提神，恢复 50 点体力。", "type": 1},
    {"id": 106, "name": "奏的特制杯面", "price": 180, "lv": 10, "desc": "只有K才知道配方的绝赞杯面，体力直接全满。", "type": 1},
    {"id": 107, "name": "薄荷糖", "price": 50, "lv": 12, "desc": "清除疲劳感，恢复 10 点体力。", "type": 1},
    {"id": 108, "name": "命运的缎带", "price": 120, "lv": 15, "desc": "神奇的道具，使用后重置你今天的今日运势。", "type": 1},
    {"id": 109, "name": "营养补给餐", "price": 150, "lv": 20, "desc": "营养均衡的一餐，恢复 80 点体力。", "type": 1},
    {"id": 110, "name": "SEKAI的奇迹水", "price": 350, "lv": 30, "desc": "不仅体力全满，还能将今日运势强行锁定为100。", "type": 1},
    
    {"id": 201, "name": "传单扩音器", "price": 150, "lv": 10, "desc": "接下来 5 次【社交打工】成功率大幅提升。", "type": 2},
    {"id": 202, "name": "搬运加力支架", "price": 200, "lv": 5, "desc": "接下来 3 次打工失败时免除工伤扣款。", "type": 2},
    {"id": 203, "name": "社交媒体推流", "price": 250, "lv": 15, "desc": "接下来 3 次打工获取的经验值翻倍。", "type": 2},
    {"id": 204, "name": "灵感爆发药水", "price": 200, "lv": 20, "desc": "极其强效的药水，接下来 5 次经验获取翻倍。", "type": 2},
    {"id": 205, "name": "25时加班津贴", "price": 150, "lv": 25, "desc": "接下来 3 次打工获取 of PC 翻倍。", "type": 2},
    {"id": 206, "name": "编程深度插件", "price": 200, "lv": 25, "desc": "接下来 3 次【技术打工】成功率大幅提升。", "type": 2},
    {"id": 207, "name": "舞台灯光", "price": 350, "lv": 20, "desc": "激活后，经验值大幅增加。", "type": 2},
    {"id": 208, "name": "核心代码库", "price": 350, "lv": 25, "desc": "技术大佬的结晶，经验值大幅增加。", "type": 2},
    {"id": 209, "name": "黄金时段通行证", "price": 400, "lv": 30, "desc": "极其稀有，下一次打工 PC 获取极大幅度增加。", "type": 2},
    {"id": 210, "name": "效率优化模块", "price": 300, "lv": 35, "desc": "接下来 3 次打工，体力消耗减半（只需10点）。", "type": 2},

    {"id": 301, "name": "加固物流箱", "price": 500, "lv": 15, "desc": "购买后使用，永久提升 5 点搬运熟练度。", "type": 3},
    {"id": 302, "name": "通讯录", "price": 600, "lv": 15, "desc": "购买后使用，永久提升 5 点社交熟练度。", "type": 3},
    {"id": 303, "name": "高精密焊台", "price": 800, "lv": 20, "desc": "购买后使用，永久提升 5 点技术熟练度。", "type": 3},
    {"id": 304, "name": "耐磨手套", "price": 1000, "lv": 25, "desc": "购买后使用，永久提升 10 点搬运熟练度。", "type": 3},
    {"id": 305, "name": "友情手链", "price": 1200, "lv": 25, "desc": "购买后使用，永久提升 10 点社交熟练度。", "type": 3},
    {"id": 306, "name": "定制键盘", "price": 1500, "lv": 30, "desc": "购买后使用，永久提升 10 点技术熟练度。", "type": 3},
    {"id": 310, "name": "SEKAI地图", "price": 3000, "lv": 50, "desc": "稀有道具，使用后永久提升所有打工熟练度。", "type": 3},

    {"id": 401, "name": "主题:晨曦白", "price": 800, "lv": 15, "desc": "使用后，更改你个人中心的基础背景色。", "type": 4},
    {"id": 403, "name": "主题:暮色紫", "price": 1200, "lv": 25, "desc": "使用后，更改你个人中心的基础背景色。", "type": 4},
    {"id": 405, "name": "主题:极光绿", "price": 1500, "lv": 35, "desc": "使用后，更改你个人中心的基础背景色。", "type": 4},
    {"id": 407, "name": "主题:深夜黑", "price": 2500, "lv": 50, "desc": "酷炫的高级纯黑背景主题。", "type": 4},
    {"id": 406, "name": "称号:蝴蝶结编织者", "price": 500, "lv": 40, "desc": "购买后永久获得专属称号。", "type": 4},
    {"id": 408, "name": "称号:永恒的25时", "price": 1000, "lv": 50, "desc": "购买后永久获得专属称号。", "type": 4},
    {"id": 409, "name": "称号:被秘密守护者", "price": 1500, "lv": 60, "desc": "购买后永久获得专属称号。", "type": 4},
    {"id": 410, "name": "主题:最终乐章·金", "price": 5000, "lv": 100, "desc": "最终的荣耀配色，个人信息卡片全动态特效感。", "type": 4}
]

DAILY_TASKS = [
    {"id": "task_sign", "name": "签到", "desc": "完成一次签到", "reward": 50, "check": "sign_today"},
    {"id": "task_buy", "name": "消费", "desc": "在商店购买任意物品", "reward": 80, "check": "buy_today"},
    {"id": "task_transfer", "name": "转账", "desc": "向其他玩家转账", "reward": 60, "check": "transfer_today"},
    {"id": "task_draw", "name": "抽卡", "desc": "进行一次抽卡", "reward": 70, "check": "draw_today"},
    {"id": "task_guess", "name": "猜数字", "desc": "参与一次猜数字游戏", "reward": 50, "check": "guess_today"},
    {"id": "task_collect", "name": "收藏", "desc": "查看自己的收藏", "reward": 30, "check": "collect_today"},
    {"id": "task_loan", "name": "贷款", "desc": "向系统申请一笔贷款", "reward": 100, "check": "loan_today"},
    {"id": "task_synthesize", "name": "合成", "desc": "进行一次卡牌合成", "reward": 90, "check": "synthesize_today"},
]

ACHIEVEMENTS = [
    {"id": "ach_first_sign", "name": "初次签到", "desc": "完成第一次签到", "reward": 100, "type": "sign_count", "target": 1},
    {"id": "ach_sign_7", "name": "一周坚持", "desc": "累计签到7天", "reward": 300, "type": "sign_count", "target": 7},
    {"id": "ach_sign_30", "name": "月度签到", "desc": "累计签到30天", "reward": 1000, "type": "sign_count", "target": 30},
    {"id": "ach_sign_100", "name": "百日坚持", "desc": "累计签到100天", "reward": 5000, "type": "sign_count", "target": 100},
    {"id": "ach_lv5", "name": "初出茅庐", "desc": "达到5级", "reward": 200, "type": "level", "target": 5},
    {"id": "ach_lv10", "name": "小有成就", "desc": "达到10级", "reward": 500, "type": "level", "target": 10},
    {"id": "ach_lv15", "name": "资深成员", "desc": "达到15级", "reward": 1000, "type": "level", "target": 15},
    {"id": "ach_lv20", "name": "传奇存在", "desc": "达到20级", "reward": 2000, "type": "level", "target": 20},
    {"id": "ach_first_5star", "name": "首次五星", "desc": "获得第一张5星卡牌", "reward": 500, "type": "has_5star", "target": 1},
    {"id": "ach_collect_10", "name": "收藏家", "desc": "收集10张不同卡牌", "reward": 800, "type": "unique_cards", "target": 10},
    {"id": "ach_collect_50", "name": "大师收藏", "desc": "收集50张不同卡牌", "reward": 3000, "type": "unique_cards", "target": 50},
    {"id": "ach_first_buy", "name": "首次消费", "desc": "在商店购买第一件物品", "reward": 50, "type": "buy_count", "target": 1},
    {"id": "ach_rich", "name": "小富翁", "desc": "持有10000 PC", "reward": 1000, "type": "balance", "target": 10000},
    {"id": "ach_super_rich", "name": "大富豪", "desc": "持有100000 PC", "reward": 5000, "type": "balance", "target": 100000},
    {"id": "ach_first_syn", "name": "首次合成", "desc": "进行第一次卡牌合成", "reward": 100, "type": "syn_count", "target": 1},
    {"id": "ach_syn_10", "name": "合成达人", "desc": "合成10次", "reward": 500, "type": "syn_count", "target": 10},
    {"id": "ach_first_raid", "name": "初次挑战", "desc": "参与第一次团队副本", "reward": 200, "type": "raid_count", "target": 1},
    {"id": "ach_raid_10", "name": "副本常客", "desc": "参与10次团队副本", "reward": 800, "type": "raid_count", "target": 10},
]

RAID_BOSSES = [
    {
        "id": "boss_kanade",
        "name": "奏的噩梦",
        "hp": 5000,
        "desc": "奏的噩梦具现化，需要用音乐的力量击败它",
        "reward_pool": 2000,
        "min_damage": 10,
        "max_damage": 100,
        "cost": 50,
        "duration_hours": 24,
    },
    {
        "id": "boss_mafuyu",
        "name": "まふゆ的虚无",
        "hp": 8000,
        "desc": "まふゆ内心的虚无化身，需要全员合力对抗",
        "reward_pool": 3500,
        "min_damage": 20,
        "max_damage": 150,
        "cost": 80,
        "duration_hours": 48,
    },
    {
        "id": "boss_ena",
        "name": "絵名的自我怀疑",
        "hp": 12000,
        "desc": "絵名对自己的否定具现化，需要用肯定的力量击破",
        "reward_pool": 5000,
        "min_damage": 30,
        "max_damage": 200,
        "cost": 120,
        "duration_hours": 72,
    },
    {
        "id": "boss_mizuki",
        "name": "みずき的秘密",
        "hp": 15000,
        "desc": "みずき隐藏的秘密实体化，是最强的Boss",
        "reward_pool": 8000,
        "min_damage": 50,
        "max_damage": 300,
        "cost": 200,
        "duration_hours": 96,
    },
]

SYNTHESIS_RULES = {
    (1, 3): 2,
    (2, 3): 3,
    (3, 3): 4,
    (4, 3): 5,
}
SYNTHESIS_COST = 100

LOAN_CONFIG = {
    "max_loan": 5000,
    "interest_rate": 0.05,
    "max_days": 7,
    "min_loan": 100,
}

MONTHLY_POOL = {
    1: {"name": "新年限定", "cards": [501, 502], "bonus": 1.5},
    2: {"name": "情人节限定", "cards": [503, 504], "bonus": 1.3},
    3: {"name": "春日限定", "cards": [505, 506], "bonus": 1.2},
    4: {"name": "樱花限定", "cards": [507, 508], "bonus": 1.4},
    5: {"name": "初夏限定", "cards": [509, 510], "bonus": 1.3},
    6: {"name": "雨季限定", "cards": [511, 512], "bonus": 1.2},
    7: {"name": "盛夏限定", "cards": [513, 514], "bonus": 1.5},
    8: {"name": "夏日祭限定", "cards": [515, 516], "bonus": 1.4},
    9: {"name": "秋日限定", "cards": [517, 518], "bonus": 1.3},
    10: {"name": "万圣节限定", "cards": [519, 520], "bonus": 1.5},
    11: {"name": "深秋限定", "cards": [521, 522], "bonus": 1.2},
    12: {"name": "圣诞限定", "cards": [523, 524], "bonus": 1.5},
}

ECONOMY_TZ = datetime.timezone(datetime.timedelta(hours=8))
DAILY_RESET_HOUR = 4

CURRENT_DB_VERSION = 1

PJSK_LOCAL_PROXY = "http://127.0.0.1:9008"
PJSK_PROXY_URL = "https://proxy.mizuki.top"
PJSK_SEKAI_BEST_BASE = "https://storage.sekai.best/sekai-jp-assets/character/member"
PJSK_CARDS_URL = f"{PJSK_PROXY_URL}/api-db/sekai-master-db-diff/cards.json"
PJSK_CARD_IMAGE_BASE = f"{PJSK_PROXY_URL}/api-assets/sekai-jp-assets/character/member"

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
    "rarity_1": {"star": 1, "label": "☆1", "weight": 50},
    "rarity_2": {"star": 2, "label": "☆2", "weight": 25},
    "rarity_3": {"star": 3, "label": "☆3", "weight": 15},
    "rarity_4": {"star": 4, "label": "☆4", "weight": 8},
    "rarity_birthday": {"star": 3, "label": "BD", "weight": 2},
}

STAR_COLORS = {1: (180, 180, 180), 2: (100, 200, 100), 3: (100, 150, 255), 4: (220, 160, 255), 5: (255, 215, 0)}

CARD_POOL = []
CARD_MAP = {}

STOCK_LIST = [
    {"id": "S001", "name": "25时唱片", "base_price": 100},
    {"id": "S002", "name": "深夜电台", "base_price": 50},
    {"id": "S003", "name": "虚拟偶像事务所", "base_price": 200},
    {"id": "S004", "name": "匿名社交平台", "base_price": 80},
    {"id": "S005", "name": "耳机制造商", "base_price": 150},
]

CROP_TYPES = [
    {"id": "c01", "name": "深夜咖啡豆", "grow_hours": 2, "harvest": 30, "seed_cost": 10},
    {"id": "c02", "name": "月光草莓", "grow_hours": 4, "harvest": 60, "seed_cost": 20},
    {"id": "c03", "name": "星尘小麦", "grow_hours": 8, "harvest": 120, "seed_cost": 40},
    {"id": "c04", "name": "梦之花", "grow_hours": 12, "harvest": 200, "seed_cost": 70},
    {"id": "c05", "name": "25时限定南瓜", "grow_hours": 24, "harvest": 500, "seed_cost": 150},
]
CROP_MAP = {c["id"]: c for c in CROP_TYPES}

PET_TYPES = [
    {"id": "p01", "name": "夜猫", "desc": "深夜最活跃的伙伴", "base_cost": 200},
    {"id": "p02", "name": "柴犬", "desc": "忠诚的深夜陪伴者", "base_cost": 300},
    {"id": "p03", "name": "猫头鹰", "desc": "25时的智慧守护者", "base_cost": 500},
]
PET_MAP = {p["id"]: p for p in PET_TYPES}

MAP_AREAS = [
    {"id": 1, "name": "深夜录音室", "cost": 0, "reward_pc": 50, "desc": "一切开始的地方"},
    {"id": 2, "name": "匿名聊天室", "cost": 100, "reward_pc": 80, "desc": "虚拟世界的第一站"},
    {"id": 3, "name": "星空天台", "cost": 200, "reward_pc": 150, "desc": "能看到星星的屋顶"},
    {"id": 4, "name": "25时咖啡馆", "cost": 400, "reward_pc": 300, "desc": "通宵营业的秘密咖啡店"},
    {"id": 5, "name": "虚拟Live会场", "cost": 800, "reward_pc": 600, "desc": "传说中的线上演唱会场地"},
    {"id": 6, "name": "ナイトコード本部", "cost": 1500, "reward_pc": 1200, "desc": "25时的核心据点"},
]

QUIZ_BANK = [
    {"q": "25时、ナイトコードで。中，谁是作曲担当？", "a": "宵崎奏", "options": ["宵崎奏", "朝比奈まふゆ", "東雲絵名", "暁山みずき"]},
    {"q": "以下哪个不是25时的成员？", "a": "星乃一歌", "options": ["宵崎奏", "朝比奈まふゆ", "星乃一歌", "暁山みずき"]},
    {"q": "深夜几点被很多人称为「逢魔时刻」？", "a": "凌晨3点", "options": ["凌晨1点", "凌晨3点", "凌晨5点", "午夜12点"]},
    {"q": "KFC疯狂星期四是每周几？", "a": "周四", "options": ["周三", "周四", "周五", "周六"]},
    {"q": "NoneBot2 是用什么语言写的？", "a": "Python", "options": ["JavaScript", "Python", "Go", "Rust"]},
    {"q": "在25时世界观中，成员们通过什么方式联系？", "a": "网络", "options": ["电话", "网络", "书信", "面对面"]},
    {"q": "「音楽だけが、私の居場所」的中文意思是？", "a": "音乐是我唯一的容身之处", "options": ["音乐是我唯一的容身之处", "音乐改变了我的命运", "音乐是我的全部", "只有音乐理解我"]},
]

FORTUNE_EVENTS = DAILY_ITEMS

JOBS = {
    "composer": {"name": "深夜作曲", "key": "prof_tech"},
    "writer": {"name": "写词讨论", "key": "prof_social"},
    "illustrator": {"name": "美术设计", "key": "prof_physical"},
}
