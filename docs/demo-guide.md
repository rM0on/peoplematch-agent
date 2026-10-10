# PeopleMatch Agent 演示指南

本指南只使用 synthetic sandbox 数据。演示前先运行 `backend/.venv/Scripts/python.exe scripts/demo_doctor.py`；任何 `blocked` 项都应先处理。

Phase 15 冻结时的 live-provider smoke 状态为 `NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`，这是历史状态。后续独立的 synthetic Fresh Top-3 Trusted Chain 实验已真实验证 Extraction 与 Phase 9 Explanation；它不代表生产部署或真实候选人场景。Mock 回归与真实 Provider 结果仍须分开说明。

## 演示前准备

- 需要 Docker Desktop、匹配 metadata / fingerprint 的本地 LambdaMART artifact，以及已持久化的 synthetic Fresh MatchRun `22326fc2-1766-4c3c-a8f0-2cc81f70849c`。该记录不存在时不要把其他运行冒充为截图中的 Fresh Top-3。
- 在仓库根目录用 PowerShell 执行 `docker compose up -d`、`docker compose ps`，确认 PostgreSQL、Redis、Qdrant、backend、frontend healthy；再打开 `http://localhost:8000/health` 和 `http://localhost:3000`。Docker 不可用时先启动 Docker Desktop，不要重跑 Ranking 来绕过环境问题。
- 主演示是已持久化结果的只读路径，不需要 Provider 在线。若额外演示新 JD 而 Provider 不可用，应明确停止该可选步骤或在独立 mock 配置下演示；不要把 mock 说成 real，也不要更改已持久化 Fresh 结果。

## 3–5 分钟作品集演示

1. 打开 [Fresh Top-3 Recruiter View](http://localhost:3000/?runId=22326fc2-1766-4c3c-a8f0-2cc81f70849c)：这是 synthetic sandbox 的已持久化结果，不重新执行排序或调用模型。先指出复核动作、技术信号、核心未知与首要核实目标；复核不是录用建议或匹配概率。对应 [Hero 截图](images/portfolio-final/01-recruiter-view.png)。
2. 在 cand_019、cand_033、cand_006 间切换，并在首位候选人的“查看依据”下钻到项目/技能来源和岗位 requirement；未知表示证据未建立，不是候选人缺陷。对应 [Evidence 截图](images/portfolio-final/02-evidence-provenance.png)。
3. 展开 Engineering View：展示特征、Retrieval rank、LTR raw score、MatchRun 与 ranking fingerprint。原始分值只用于相对排序，不是概率。再打开 [Agent Run](http://localhost:3000/agent-run)，区分 persisted trace 与 derived explanation metadata。对应 [Engineering](images/portfolio-final/03-engineering-view.png) 与 [Agent Run](images/portfolio-final/04-agent-run.png) 截图。
4. 打开 [离线评估](http://localhost:3000/evaluation)：同源比较 Hybrid、LambdaMART 与可选 CE，并指出 synthetic / post-exposure / incomplete judgments 的边界；CE 未超过默认 LTR。对应 [Eval 截图](images/portfolio-final/05-eval-dashboard.png)。
5. 说明 Bad Case 人工复核闭环：独立 [Bad Case 截图](images/portfolio-final/06-bad-case-review.png) 来自一次性 synthetic review fixture，展示人工反馈、证据、根因与规划行动；它不是 Fresh Top-3 的真实模型失败。普通开发数据库若无复核记录，该页面可为空，不要临场伪造记录。

如需演示新输入，再进入 `/workbench` 输入 synthetic JD；它可能调用配置的真实 Provider，不属于上述只读截图路径。自由 Recruiter Narrative 不是可信主视图的事实源，若展示必须标注“AI Narrative Draft / Requires Human Review”。

## 8–10 分钟技术演示

### 1. 输入与结构化

- 说明 mock 模式确保测试与 E2E 可复现；Real mode 让 extraction/explanation 两个独立任务 adapter 共享 OpenAI-compatible transport。
- Resume 通过“解析预览 → 确认入库 → 刷新派生索引”进入 Candidate Pool；岗位 JD 始终作为推荐 Query。
- 强调 schema-first validation、长度上限、timeout/retry、错误脱敏；无法确认的信息保持 missing。

### 2. 召回与排序

- Dense 与 BM25 Sparse 形成 RRF Hybrid pool。
- 10 个冻结显式特征进入 `ltr_ranker_v1`；model margin 不是 probability。
- CE 只做可选 rerank。它更“新”不代表应当成为默认；冻结证据未证明它超过 LTR。

### 3. Evidence 与历史

- 展示 Recruiter View 的岗位关联、技术信号、未知与核实目标，并按需展开来源；不要把内部 ref ID 堆在默认页面。
- Phase 9 Provider 只选择 candidate-scoped semantic options，程序确定性绑定 canonical ExplanationPlanV1；Grounding 验证后持久化。RecruiterProposition 从已存来源只读重建。
- 生成解释前后 ranking order、score 与 fingerprint 不变。

### 4. Review loop

- 从历史结果进入 Feedback，展示 BadCase 生命周期与 stale revision 保护。
- 明确 `VERIFIED` 只代表该 case 有不可变验证引用，不证明模型整体提升。

### 5. Offline Evaluation

- R1 比较同 corpus 下 Dense/Sparse/Hybrid Recall。
- R2 在相同 48-Candidate pool 上比较 Hybrid/LTR/CE，再 condense 到同一 12 个 judged Candidates。
- 解释不计算 standard Precision@K：75% pair 未判断，`unjudged != negative`。
- Test 在协议、策略、metric 与 source fingerprint seal 后才执行；但 Phase 4 曾查看 Test，因此不能称 pristine held-out。

## Mock Mode

`.env` 保持：

```dotenv
EXTRACTION_PROVIDER=mock
EXPLANATION_PROVIDER=mock
```

Mock 只识别注册的 synthetic fixture；它不是通用简历解析器。

## Real LLM Mode

仅在本地 `.env` 配置：

```dotenv
EXTRACTION_PROVIDER=openai_compatible
EXPLANATION_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-id
LLM_API_KEY=
```

页面只显示“已配置”，不声称网络已连接。任意 JD 由 extraction task 结构化，Phase 9 explanation task 只在安全 Evidence catalog 中选择；LambdaMART 始终拥有排序。不要在演示、截图、日志或聊天中展示 Key。Live smoke 只使用 synthetic 输入；若要切回 mock，必须显式修改本地配置，系统不会把自动 fallback 伪装成 real success。

## 常见故障恢复

| 现象 | 检查 | 安全处理 |
| --- | --- | --- |
| Doctor 报 Node blocked | `node --version` | 使用 Node 22 LTS；不要降低项目要求 |
| Docker blocked | `docker info` | 启动 Docker Desktop 后重试 |
| Backend unavailable | `http://localhost:8000/health` | 检查 venv、migrations、DATABASE_URL |
| 模型 artifact missing | doctor / check scripts | 按版本化 metadata 准备，不自动换模型 |
| Provider unavailable | Provider config | 不打印 Key；可切回 deterministic mock |
| structured output invalid | UI request ID / backend safe error | 重试；不要直接信任或手工修补 provider JSON |
| retrieval failure | Qdrant health / collection names | 重建派生索引，不改 PostgreSQL profile truth |

## 演示时不要说

- “匹配准确率 95.93%”
- “已经用于真实招聘 / 生产环境”
- “CE、Hybrid 或 LTR 在真实市场普遍更好”
- “Feedback 会自动持续学习”
- “VERIFIED 证明模型已经修复”
