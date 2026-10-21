# V5 工程案例：从任务契约到可信浏览器验收

PeopleMatch 的原 Recruiter View 能展示候选人排序、解释和来源，但招聘人员仍需要逐条核实岗位要求。V5 新增只读 Requirement Review Workbench：展示 must-have / nice-to-have、证据状态、Unknown、历史来源和人工核实目标。它不改变正式排名，也不把缺失材料推断成能力不足。

## 任务和冻结边界

实际任务材料在本地版本 `signature-v5/engineering/mission.md`、`context-map.md` 与 `acceptance-contract.md` 保存；公开源码中的服务、API、客户端和测试可直接审查。本页对任务流程的描述是**基于真实产物的工程复盘**，不是恢复的逐字 Codex 聊天。允许新增只读 Backend→typed GET API→Next.js 路由；禁止重新运行 Qwen、改变 Ranking、历史 MatchRun、ExplanationRun 或 Grounding 标准。验收依据是实际代码、拒绝性测试、数据库读回和浏览器行为，不是 Agent 的完成声明。

## 可检查的实现

| 层 | 文件 | 要检查的契约 |
|---|---|---|
| 后端 | `backend/app/services/requirement_review/service.py` | 从历史 Evidence Bundle 和 canonical Proposition 建立要求投影；只交付实际命题使用的来源；候选、岗位引用和指纹不匹配时拒绝。 |
| API | `backend/app/api/routes/requirement_reviews.py`、`backend/app/schemas/requirement_review.py` | 只读 typed GET；不存在与不可信输入分别失败。 |
| 前端 | `frontend/src/lib/requirement-review.ts`、`frontend/src/features/requirement-review/requirement-review-screen.tsx` | 对 Run、Candidate、Rank、Explanation、fingerprint 与来源闭包再次校验；失败不展示可信内容。 |
| 测试 | `backend/tests/test_requirement_review_workbench.py`、`frontend/src/lib/requirement-review.test.ts`、组件测试 | 正例、缺失/额外/跨候选来源及身份错误的拒绝。 |

真实截图 `docs/images/requirement-review-v5.png` 来自先前隔离 PostgreSQL 的 synthetic 浏览器验收；不是线上招聘客户、生产部署或本轮重新调用 Provider 的截图。

## 独立审查改变了什么

历史审查发现可变 Profile 不能覆盖历史 Evidence 的来源标签，JD 必须绑定实际岗位要求，跨要求聚合命题不能伪装成单项要求的证明。随后 PostgreSQL 历史回读揭示另一个语义冲突：Backend 返回 HTTP 200，但它交付了页面命题没有使用的额外候选来源，可信客户端因此拒绝。HTTP 成功与业务契约拒绝可以同时成立。修正后服务端仍验证必要引用，却只投影本次展示真正使用的历史来源；客户端拒绝逻辑继续保留。相关反例见上述后端/前端测试。

## 验证层级与限制

- **本候选当前重跑（独立审查修复后）**：相关后端回归 117 项、前端 104 项、TypeScript、ESLint；历史 ExplanationRun 链接与 HTTP 200 额外来源拒绝经过桌面/手机 synthetic HTTP 浏览器检查。最终构建结果与新增来源 ID 语法拒绝见[审查修复记录](independent-review-closure.md)。不等于 PostgreSQL 本轮重跑。
- **先前保存的独立审计**（2026-10-18）：隔离 tmpfs PostgreSQL、Alembic、31 项持久化测试及 1 项 seed 测试；新建 synthetic MatchRun 的 GET/可信客户端/1440px 与 390px 浏览器链路。与历史 Fresh Top-3 不同。发布证据包提供经筛选的记录；原始一次性数据库不随包提供。
- **历史 V5 验证**：同一历史 synthetic Fresh Run 的 PostgreSQL 只读回读、3/3 客户端验收和排序/指纹不变量。不能称为本候选重跑。
- **未验证**：普通公开 fresh clone 的 Level B 数据库一键演示、生产招聘效果，以及未来远端 Push 后的实际 GitHub 页面状态。

详见 [复现层级](../../v5-reproduction-guide.md)。API 并不调用 Provider、重训模型或写入数据库；真实系统的付费 Provider 和历史排序不属于此次发布候选测试。
