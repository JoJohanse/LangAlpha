## Phase 1 MVP Implementation Plan (LangAlpha)

### Summary
按你确认的决策执行第一阶段 `MVP`：
- 范围：`MVP精简版`
- AI交互：新增 `interpret` 接口（不走聊天预填）
- 事件数据：持久化入库（最小事件模型 + 最小聚合任务）

本次只覆盖“资讯事件化 + Dashboard事件流 + MarketView事件marker + 事件解读接口”，不进入研报线。

### Key Changes
1. Backend data/model layer
- 新增 Alembic 迁移（next revision）创建 3 张表：
  - `market_events`（事件主表，含 `event_id/title/short_summary/importance_score/sentiment/start_time/primary_symbol/symbols/tags/article_count/ai_takeaway/status/created_at/updated_at`）
  - `market_event_articles`（`event_id + article_id + relevance_score + is_primary`）
  - `symbol_event_links`（`event_id + symbol + event_time + impact_direction + impact_score + display_title`）
- 新增数据库访问模块（按现有 `src/server/database/*` 风格）用于事件 CRUD、热榜、symbol 维度查询、marker 查询。

2. Backend service & jobs
- 新增 `event_service`（最小可用聚合）：
  - 数据源：复用现有 `NewsDataProvider` 新闻结果。
  - 聚合窗口：最近 24h，任务周期 5 分钟。
  - 聚合规则（MVP固定规则，避免实现期再决策）：
    - 必须共享至少 1 个 ticker，且发布时间差 <= 6h；
    - 标题关键词 Jaccard 相似度 >= 0.55 归并为同事件；
    - `primary_symbol` 取出现频次最高 ticker；
    - `importance_score` 由 `article_count + unique_source_count + sentiment_presence` 线性评分并归一到 0-100。
  - 入库策略：upsert 事件与关联表，保证 `event_id` 稳定（基于主 symbol + 时间桶 + 聚类签名哈希）。
- 在应用启动/关闭流程挂载事件聚合后台循环（对齐 `InsightService` 生命周期管理方式）。

3. Backend API layer
- 新增 `events` 路由：
  - `GET /api/v1/events`（分页事件流）
  - `GET /api/v1/events/hot`（importance 排序）
  - `GET /api/v1/events/{event_id}`（事件详情 + 关联文章）
  - `GET /api/v1/events/by-symbol/{symbol}`（symbol 相关事件）
  - `POST /api/v1/events/{event_id}/interpret`（事件AI解读，按需生成并可回填 `ai_takeaway`）
  - `POST /api/v1/news/{article_id}/interpret`（单新闻AI解读）
- 扩展 `market_data` 路由：
  - `GET /api/v1/market-data/stocks/{symbol}/events`（给 K 线 marker 使用）
- 在 `setup.py` 注册新路由并启动事件后台任务。

4. Frontend Dashboard (资讯主页 MVP)
- `useDashboardData` 增加事件数据查询（事件流 + 热点榜）。
- `NewsFeedCard` 改为双模式：`Events`（默认） + `Raw News`（保留现有新闻流）。
- 新增 `EventDetailModal`：
  - 展示事件摘要、相关 symbols、关联新闻；
  - 支持“打开 MarketView”；
  - 支持调用 `POST /events/{id}/interpret` 显示解读结果。
- 保留现有 `AIDailyBriefCard`，不改其主逻辑。

5. Frontend MarketView (K线联动 MVP)
- 从 URL 读取 `symbol/event/event_time` 参数，进入时定位 symbol。
- 新增事件 marker 数据拉取（`fetchSymbolEvents`）并接入现有 marker 机制（扩展 `useChartOverlays` 输入）。
- marker 点击弹出事件摘要卡（最小信息：标题、时间、方向、跳详情按钮）。
- 保持现有图表/聊天主流程不变。

6. Public interfaces/types to add
- 新增后端 Pydantic 模型：
  - `EventListItem`, `EventDetail`, `EventMarker`, `InterpretRequest`, `InterpretResponse`
- 新增前端类型：
  - `MarketEvent`, `MarketEventDetail`, `SymbolEventMarker`, `InterpretResult`
- 新增前端 API client：
  - Dashboard `eventsApi.ts`
  - MarketView `fetchSymbolEvents(...)`
  - `interpretEvent(...) / interpretNews(...)`

### Test Plan
1. Backend
- 事件聚合服务单测：
  - 同事件归并、不同事件分裂、score 计算、event_id 稳定性。
- 路由测试：
  - `/events` 列表/详情/hot/by-symbol；
  - `/market-data/stocks/{symbol}/events`；
  - `interpret` 两个 POST 接口（成功、超时、无数据）。
- 迁移测试：
  - `alembic upgrade head` 可通过，新增表索引可查询。

2. Frontend
- `useDashboardData` 增加事件查询映射测试（含空态）。
- `NewsFeedCard` 模式切换与过滤逻辑测试（Events/Raw News）。
- `EventDetailModal` interpret 调用与结果渲染测试。
- MarketView marker 显示与点击行为测试（事件参数跳转场景）。

3. Manual acceptance (对应MVP 6点)
- 首页有 AI 简报；
- 首页有事件流；
- 事件详情有摘要 + 相关 symbol + 相关新闻；
- 事件可跳 K 线；
- K 线可看到事件 marker；
- 事件可一键触发 AI 解读。

### Assumptions and Defaults
- 仅实现第一阶段 MVP，不做研报页面、观点一致性、地图、TTS、自定义看板。
- 市场范围默认 US（沿用现有 insight/news 方向）。
- 事件聚合先用规则+轻量 LLM 摘要，不追求“完美聚类”。
- interpret 接口默认同步返回（带超时保护），失败不影响事件主流程。
- 现有 `/api/v1/news` 与 Dashboard 现有新闻功能保持兼容。
