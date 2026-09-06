# Phase 14 JD-first Productization Design

## Decision

PeopleMatch 的默认入口改为岗位 Query 驱动的人才推荐：招聘者只输入 JD，系统从现有 Candidate Pool 执行 Hybrid Retrieval、Feature Engineering、LambdaMART Ranking，并为 Top-K 生成 Evidence-grounded Explanation。

Resume 从推荐入口移到独立的“人才库管理”页面。用户先预览 Structured Profile，确认后才持久化候选人并刷新派生检索索引；此候选人会参与未来岗位推荐。

## Architecture

- 推荐工作台复用现有 Job parse、Demo index rebuild、MatchRun 与 Explanation API，不引入新的排序或编排后端。
- 人才库管理复用现有 Candidate parse/list API；预览使用 `persist=false`，确认入库使用 `persist=true`，之后显式重建派生索引。
- 推荐记录复用现有 MatchRun/Feedback 历史读取组件。
- Candidate Pool 原始 48 人、Retrieval、Feature、LTR、CE、Evidence contract 和 Phase 11 artifacts 全部保持不变。
- 推荐等级是按当前 Top-K 名次生成的 presentation metadata，不读取或转换 raw LTR margin。

## Product Flow

1. 招聘者进入推荐工作台，只看到 JD Query。
2. 加载按钮只填充中文 JD 示例。
3. 系统解析并持久化 Job，刷新派生索引，执行现有 LTR MatchRun，生成解释。
4. HR 在人才库页面粘贴 Resume，预览结构化档案，确认后加入 Candidate Pool。
5. 后续 JD 推荐自动从包含已入库候选人的当前人才库检索。

## UI Semantics

- 主标题：`AI 人才推荐工作台`。
- 结果首先显示推荐名次和展示等级；LTR Score 收纳为技术信息，并持续声明它不是概率或录用率。
- Explanation 分为“推荐优势”“风险提示”“技术证据”，只重组现有历史解释字段。
- 导航只包含可用入口：推荐工作台、人才库管理、推荐记录、Bad Case 复核。

## Failure And Integrity Semantics

- Job、Resume、索引、MatchRun 或 Explanation 任一步失败都显示可恢复错误，不制造部分成功。
- Candidate 已持久化但索引刷新失败时，明确告知用户重试刷新，不能声称已进入检索池。
- Mock 模式只保证已注册 synthetic fixtures；任意真实文本需要本地 OpenAI-compatible Provider credential。
- Explanation、展示等级和中文 metadata 均不能改变 ranking order、raw score 或 fingerprint。

## Rejected Alternatives

- 新增后端“一键 Demo 编排”接口：会重复现有 API/Service 责任并扩大冻结风险。
- 让首页继续接受可选 Resume：仍会保留产品误解。
- 将 raw LTR margin 映射为百分比或概率：语义错误，明确拒绝。

## Acceptance

- JD-only 首页、人才入库、推荐记录和 Bad Case 四个入口可用。
- 加载 JD 示例不填充或创建 Candidate。
- 新候选人经显式确认后进入当前索引，并可参与未来推荐。
- 前端 tests/typecheck/lint/build、后端回归和 disposable Browser E2E 通过。
- Phase 11、冻结 48 人数据、Retrieval、Feature、LTR、CE 与 evaluation result 相对 `fd453f0` 为零差异。
