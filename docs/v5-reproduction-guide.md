# V5 Requirement Review：复现层级与边界

本修订新增只读的岗位要求核实工作台。请区分以下三个层级；源码和测试可运行，不等于历史数据库、模型 artifact 或 Provider 结果可从普通 clone 自动恢复。所有示例只使用 synthetic 数据，**不要连接含真实资料的数据库**。

## A — 源码和确定性测试

环境：Python 3.11+、Node.js（遵循 `frontend/package.json` 和 lockfile）、npm。先阅读根目录 `.env.example`，只在本机配置环境；不要提交 `.env`。Windows PowerShell 中从仓库根目录执行：

```powershell
py -m venv backend/.venv
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
& backend/.venv/Scripts/python.exe -m pytest backend/tests/test_requirement_review_workbench.py -q
Set-Location frontend
npm ci
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

`test_requirement_review_workbench.py` 使用 synthetic fixtures；它验证只读投影、候选隔离、岗位引用和拒绝条件，不依赖真实 Provider，也不证明 PostgreSQL 链路。客户端测试位于 `frontend/src/lib/requirement-review.test.ts`、`frontend/src/features/requirement-review/requirement-review-screen.test.tsx` 与 `frontend/src/lib/trusted-recruiter.test.ts`。2026-10-20 修复后的隔离发布工作区实际运行相关后端回归 117/117、前端 104/104、TypeScript、ESLint 与默认 Turbopack `next build`（退出码均为 0）。详见[审查修复记录](release/v5-publication/independent-review-closure.md)。这些是本地候选执行记录，不是远端 fresh clone 或本轮 PostgreSQL 重跑。

## B — 独立 synthetic V5 演示

仅在**已确认身份的隔离测试数据库**中执行迁移和 seed。普通 `docker compose up -d --build` 会启用具名数据卷并暴露默认端口，不能当作一次性隔离数据库，更不能指向现有开发库。安全演示的顺序是：建立独立 PostgreSQL → 核对 host/port/database/user 及 `DATABASE_URL`、`TEST_DATABASE_URL` → 在该数据库执行 `alembic upgrade head` → 写入明确的 synthetic MatchRun / ExplanationRun / Evidence Bundle → 调用 `GET /api/v1/match-explanations/{id}/requirement-review` → 在真实 `/requirement-review` 页面核对候选切换、来源下钻、Unknown 与拒绝状态。

现有文档和测试中没有随 Git 发布的、可由普通 clone 一条命令完成上述全部步骤的安全 seed/harness；因此 **Level B fresh-clone 一键复现尚未验证**。2026-10-18 的独立审计在单独 tmpfs PostgreSQL 中完成过新建 synthetic fixture 的迁移、31 项持久化测试、1 项 seed 测试以及 PostgreSQL→GET API→可信客户端→桌面/移动浏览器验收。该保存结果是**历史审计证据**，不是本次发布工作区的新数据库运行。审计素材的选择性摘录见 [工程案例](release/v5-publication/engineering-case.md) 与 [公开证据包](portfolio/v5/PeopleMatch-AI-Native-Engineering-Evidence-Pack.zip)。

如只需查看 UI，可使用前端组件测试或独立 synthetic HTTP fixture；这不等于真实数据库集成。`/requirement-review` 是只读视图，不会运行 Ranking 或调用 Qwen。没有合适的持久化 synthetic Run 时，页面不会凭空创建“成功”数据。

## C — 历史 Fresh Trusted Run

历史受控 synthetic Fresh Top-3 使用当时的真实 Provider、已保存 MatchRun、Explanation 和模型 artifact。它的 3/3 可信投影及只读 PostgreSQL 回读有保存记录，但普通 clone 不包含原数据库或忽略的模型文件；也不应为演示而重写历史 Run、重新选模型或默认产生付费 Provider 调用。Level A/B 的通过不能升级为 Level C 重跑成功。任何生产招聘准确性和线上效果均未验证。

## 常规本地服务（非隔离测试数据库）

根目录 `docker-compose.yml` 定义 PostgreSQL、Redis、Qdrant、Backend 与 Frontend；`.env.example` 给出**本地开发示例值**，不是云端凭据。确认 Docker Engine、端口、模型 artifact 和现有数据卷状态后，才可按 [README](../README.md) 执行 `docker compose up -d --build`。Backend 容器会运行 `alembic upgrade head`。不要将这一步写成 Level B 的一次性独立数据库验证；不要用 `docker compose down -v` 清理不属于本次任务的数据。

## 证据与停止条件

- 无法确认数据库身份：停止写入/迁移，标记 `NOT VERIFIED`。
- 缺少历史模型 artifact 或运行记录：只运行不依赖它们的定向测试，不伪造历史视图。
- HTTP 200 但客户端拒绝：检查 Run/Candidate/Rank/Explanation、fingerprint、来源闭包和岗位引用；不要关闭可信校验。
- 无真实 Provider 测试配置：保持 mock，不把 mock 说成 Qwen 实时验收。
