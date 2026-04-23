# LangAlpha 第二阶段任务定义（Phase 2A + 2B）

## Summary
基于`后续改造任务规划.md`，第二阶段定义为“资讯增强 + 日报闭环”，目标是在不改动第一阶段事件闭环能力的前提下，补齐资讯侧高频使用路径，并交付可回看的早报/晚报文本版。  
完成标准：用户可完成“发现资讯 -> 筛选/排序 -> 详情查看 -> 一键提问 -> 查看日报”的端到端流程，且 Docker 部署下可稳定验收。

## Key Changes

### 1) Phase 2A：资讯增强（P0，2个迭代）
1. 资讯标签与筛选
- 后端新增新闻标签建模与查询维度：`sector/topic/region/symbols`。
- 在现有新闻/事件数据流中补齐标签生成与入库（优先规则提取，缺失时允许空值）。
- 前端资讯页增加筛选入口：按板块、主题、品种过滤；与现有 Events/Raw News 兼容。

2. 热榜治理（Hot Rank）
- 新增热榜排序服务：综合`importance_score + recency + source_count`。
- 新增热点接口`GET /api/v1/news/hot-rank`，支持分页与时间窗口参数（默认24h）。
- 前端 Hot 列表展示排序依据字段，支持切换“事件热榜/资讯热榜”。

3. 单条资讯一键提问
- 新增接口`POST /api/v1/news/{article_id}/ask`，将文章核心上下文注入现有 AI 对话入口。
- 前端在 News 卡片和详情弹窗增加“Ask AI”按钮，点击后跳转 Chat 并自动附带上下文。
- 失败回退：上下文注入失败时仍可打开空白对话，不阻断用户路径。

4. 7x24 快讯模式
- 新增快讯列表数据源与展示模式，作为`Events / Raw News / 7x24`第三视图。
- 保持与现有资讯卡组件共用渲染骨架，仅扩展字段适配与标签样式。

### 2) Phase 2B：日报能力（P1，1个迭代）
1. 日报生成与存储
- 新增日报数据模型（晨报/晚报），字段至少包含：日期、类型、状态、正文、生成时间、错误信息。
- 新增定时任务：每日两次生成文本日报；支持手动重试。
- 生成失败不影响主资讯服务，状态可追踪（`pending/running/success/failed`）。

2. 日报接口与页面
- 新增接口`GET /api/v1/briefs/daily?date=YYYY-MM-DD&type=morning|evening`。
- 可选新增`POST /api/v1/briefs/{brief_id}/interpret`复用 AI 解读能力。
- 前端新增日报入口与日期选择，支持历史回看和空态提示。

3. 交付策略
- 第二阶段仅上线文本版日报。
- TTS 保留配置位但默认关闭，不进入本阶段验收范围。

## Public Interfaces / Types

1. 新增后端接口
- `GET /api/v1/news/hot-rank`
- `GET /api/v1/news/by-sector/{sector}`
- `GET /api/v1/news/by-topic/{topic}`
- `POST /api/v1/news/{article_id}/ask`
- `GET /api/v1/briefs/daily`
- `POST /api/v1/briefs/{brief_id}/interpret`（可选，建议纳入）

2. 新增/扩展类型
- `NewsTag`
- `NewsHotRankItem`
- `NewsAskRequest` / `NewsAskResponse`
- `DailyBrief`
- `DailyBriefStatus`

3. 兼容性要求
- 第一阶段接口行为不变：`/api/v1/events*`、`/api/v1/market-data/stocks/{symbol}/events`保持兼容。
- Dashboard 与 MarketView 的事件跳转链路不回归。

## Test Plan

1. 后端测试
- 标签提取与筛选：sector/topic/symbol 过滤正确性、空标签容错。
- 热榜排序：importance/recency/source_count权重生效与稳定性。
- 一键提问：上下文注入成功、文章不存在、AI超时回退。
- 日报任务：定时生成、重试、失败状态落库、按日期查询。

2. 前端测试
- 资讯页筛选联动、清空筛选、空态渲染。
- Hot Rank 列表渲染与排序字段展示。
- News 卡片“Ask AI”跳转与上下文携带。
- 日报页面日期切换、晨/晚报切换、失败态提示。

3. Docker 验收（发布门槛）
- `docker compose up -d`后服务可自动迁移并正常启动。
- 资讯闭环：筛选 -> 热榜 -> 详情 -> Ask AI 全链路可用。
- 日报闭环：可读取指定日期晨/晚报，失败时可见状态并可重试。
- 回归：第一阶段 events/marker/deeplink 行为无异常。

## Assumptions and Defaults
- 第二阶段不进入研报模块，不实现地图、命中率、自定义看板。
- 标签提取先采用规则优先，模型增强后置。
- 日报先文本输出，TTS 默认关闭。
- 所有新增能力以 Docker 运行态验收结果为最终准入标准。
