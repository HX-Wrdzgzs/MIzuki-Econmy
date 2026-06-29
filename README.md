# 🎧 Mizuki Economy (25时经济系统)

<p align="left">
  <img src="https://img.shields.io/badge/NoneBot2-2.0.0+-red.svg" alt="NoneBot2">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Database-MySQL-orange.svg" alt="MySQL">
</p>

`mizuki_econmy` 是一款为 NoneBot2 框架设计的群聊经济与社交互动插件。本项目针对 QQ 官方机器人的底层 API 进行了深度定制，在保证高并发数据安全的前提下，提供了丰富的经济体系与极具表现力的原生 UI 交互。

## ✨ 核心特性 (Features)

- 📱 **原生官方 UI 深度适配**
  - **动态降级策略**：通过特判 `bot.self_id`，对官方机器人实例下发原生的 **Markdown** 与 **内联按钮 (Inline Keyboard)**；对非官方实例（小号）自动执行平滑降级，以纯文本形式输出，保障多实例兼容性。
  - **规范化组件**：基于 `lib_msg.py` 抽象规范，统一采用一维扁平化 Tuple/Dict 列表构建按钮，自动处理布局排版与跳转逻辑。
- 🎨 **异步图像渲染 (Dynamic Rendering)**
  - 基于 `Pillow` 库实现全量 UI 图像化，涵盖【签到面板】、【个人信息卡片】、【打工作业结算】及【背包概览】。
  - 采用瑞希（Mizuki）定制粉色系 UI 规范，自动拉取并绘制用户 QQ 头像。
- 🛡️ **事务级并发控制 (Transaction Safety)**
  - 底层基于 `aiomysql`，全面启用 InnoDB 引擎。
  - 在核心资金流转（如抢红包、集资扣款）中严格遵循 `FOR UPDATE` 行级锁与事务隔离机制，彻底杜绝高并发场景下的超卖与死锁异常。
- 🎲 **高并发社交应用**
  - **拼手气红包**：引入微信同款“二倍均值算法”进行资金拆分，采用内存队列 (Memory Queue) 承载抢夺请求，内置系统税收流转。
  - **V50 全服大乐透**：结合 `nonebot-plugin-apscheduler` 实现跨群定时任务。周三/周四自动触发预热广播，周四正午自动截断报名池并进行全网一致性开奖。
- 💼 **完善的经济模型**
  - 内置运势签到、多维度体力打工、等级跃升系统以及支持限制购买条件的道具商城。

## 📦 依赖 (Dependencies)

- `nonebot2` >= 2.0.0
- `nonebot-adapter-onebot` (兼容官方频道 API 及 NapCat / LLOneBot)
- `nonebot-plugin-apscheduler` (用于驱动 V50 定时广播系统)
- `aiomysql`
- `Pillow`
- `httpx`

## ⚙️ 环境配置 (Configuration)

在 NoneBot2 项目的 `.env` 或 `.env.prod` 文件中追加以下数据库配置项：

```env
# Mizuki Economy 数据库配置参数
SIGN_MYSQL_HOST=127.0.0.1
SIGN_MYSQL_PORT=3306
SIGN_MYSQL_USER=your_username
SIGN_MYSQL_PASSWORD=your_password
SIGN_MYSQL_DB=your_database_name
