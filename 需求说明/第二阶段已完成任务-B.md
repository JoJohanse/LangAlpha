# 第二阶段已完成任务-B（基于任务规划-B对照）

## 1. 文档说明
- 对比来源：`第二阶段任务规划-B.md` + 当前代码实现。
- 统计口径：以仓库内已落地代码与已补充测试用例为准；运行态验收标准仍以 Docker 为最终口径。
- 文档目标：明确 B 阶段已完成项、部分完成项与当前剩余收口项。

## 2. 总体对照结论
- `B1 资讯详情完整性`：已完成核心收口。
- `B2 国内新闻源生产化`：已完成主链路兼容与时间语义修正。
- `B4 Insight/简报一致性`：已完成核心能力收敛与提示词约束。
- `B3 Dashboard 信息架构收口`：已完成主要交互收口，仍有少量清理项。
- `B5 Docker 验收与运维闭环`：已完成测试入口与回归用例补充，仍需持续执行发布级 Docker 验收清单。

## 3. 已完成任务清单（按 B1~B5）

### 3.1 B1 资讯详情完整性（已完成）
- 已补齐新闻详情摘要兜底：当 `description` 为空或为无意义数字时，回退到 `title` 展示，避免详情出现空摘要或无效摘要。
- 已统一新闻详情主字段回退链路：缓存命中、provider 命中、snapshot 回退三条路径均可构造详情。
- 已补齐分类字段透传：`sector/topic/region/tags` 在缓存详情、provider详情、snapshot回退中均可返回。
- 已补齐前端详情空态/异常态处理：详情拉取失败时提供明确提示与外链兜底（有 fallback URL 时可直接打开原文）。
- 已新增/更新对应回归测试：
  - `tests/unit/server/app/test_news_phase2.py`（详情字段完整性、摘要兜底、404/snapshot回退等）。

### 3.2 B2 国内新闻源生产化（已完成主链路）
- 已接入并前置 `pobo-proxy` 新闻源，保留现有 provider fallback 机制。
- 已完成 `pobo` 新闻数据兼容映射：支持 `{count, items}` 与 `Info*` 字段映射到现有 news 契约。
- 已完成 `pobo-{InfoID}` 文章 ID 规范与详情反查路径。
- 已补齐 `get_news_article` 双路径：优先 `/news/{id}`，失败后回退列表扫描。
- 已修正 `CreateTime` 的时间语义：无时区时间按 `Asia/Shanghai` 解释，再统一转换为 UTC 存储/传输。
- 已强化“仅展示可追溯已入库新闻”策略：列表响应按已落库标签新闻过滤，降低详情/Ask AI 404 概率。
- 已新增/更新对应回归测试：
  - `tests/unit/data_client/test_pobo_proxy_news_source.py`
  - `tests/unit/server/app/test_news_phase2.py`（含 pobo 详情路径）。

### 3.3 B4 Insight / 简报一致性（已完成核心）
- 已将简报能力保持在 `insights` 主链路，不引入独立 `briefs` 主路径。
- 已落地早/晚报会话语义：
  - 后端 `insights` 响应补充 `brief_session`（`morning/evening`）；
  - 前端 `AIDailyBriefCard` 提供早/晚切换按钮并按会话过滤展示。
- 已补齐简报生成的新闻时间窗约束：
  - insight 生成时按窗口请求新闻；
  - 对返回新闻再次按窗口严格过滤，避免越界新闻混入。
- 已收敛语言与来源约束：
  - 提示词明确“仅使用提供的新闻列表”；
  - 输出文本要求为简体中文；
  - 去除“默认仅美国市场”假设。
- 已新增/更新对应回归测试：
  - `tests/unit/server/services/test_insight_service.py`
  - `tests/unit/server/app/test_news_phase2.py`（`brief_session` 推断相关用例）。

### 3.4 B3 Dashboard 信息架构收口（部分完成）
- 已完成资讯主入口收口到 `Events + 7x24`（不再保留 Raw News 入口）。
- 已完成 `Events` 下的 `Hot / All Events` 双视图切换，默认进入 `Hot`。
- 已补齐筛选增强：支持日期快捷范围 + 起止 `datetime-local`（小时粒度）精确筛选。
- 已保留并可用 Ask AI 链路：7x24 新闻卡片支持一键提问并带上下文跳转 Chat。

### 3.5 B5 Docker 验收与运维闭环（部分完成）
- 已补充并沉淀 Docker 测试/构建指令（见 `测试指令.txt`）。
- 已新增 B 阶段关键回归用例，覆盖 B1/B2/B4 的主要改动面。
- 已保持“测试在 Docker 中执行”的实施口径。

## 4. 仍需收口项（相对任务规划-B）

### 4.1 B3 剩余项
- Dashboard 数据层仍保留 `hotNewsItems` 查询用于上下文拼接，建议后续评估是否继续保留或重构为显式入口，避免信息架构歧义。
- 需进一步补齐“热榜-详情-Ask AI”关系的页面级说明与交互一致性回归用例（当前以链路可用为主）。

### 4.2 B5 剩余项
- 需按规划-B完成发布级 Docker 手工验收清单固化（含主源关闭 fallback、缓存残留清理验证、全链路巡检顺序）。
- 需在每次镜像发布前执行并记录固定回归组合（后端+前端+手工链路），形成可追踪验收记录。

## 5. 兼容性结论
- 第一阶段 `events / marker / deeplink` 主链路保持兼容，未引入破坏性接口变更。
- 第二阶段 A 已完成能力保持可用，B 阶段改动以收口和稳态增强为主。
- 当前第二阶段 B 的已完成内容可定义为：`B1 + B2 + B4 核心完成，B3/B5 进入收尾阶段`。
