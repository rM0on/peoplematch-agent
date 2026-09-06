# PeopleMatch Agent 演示指南

本指南只使用 synthetic sandbox 数据。演示前先运行 `backend/.venv/Scripts/python.exe scripts/demo_doctor.py`；任何 `blocked` 项都应先处理。

Phase 12 冻结时的 live-provider smoke 状态为 `NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。默认 mock 演示与真实 Browser → Next.js → FastAPI → PostgreSQL/Qdrant E2E 已验证；不要把 mock transport PASS 说成外部 Provider live PASS。

## 3 分钟招聘者演示

1. 打开首页，用一句话定位：这是岗位 Query 驱动的 Candidate Retrieval + Ranking 推荐系统，LLM 不直接给排名。
2. 打开“人才库管理”，说明 Resume 先解析为 Structured Profile；点击“加载中文 Resume 示例”→“解析候选人”，查看预览后再确认加入 Candidate Pool。该 runtime 候选人不进入 Phase 11 数据集。
3. 回到“推荐工作台”，指出 JD 是检索 Query；点击“加载中文 JD 示例”→“开始推荐”，系统会从整个人才库执行候选召回与 Top-K 排序，不是给单份简历打分。
4. 在结果页指出三件事：`LTR Score` 是排序模型分值，不是概率、匹配百分比、录用概率或推荐成功率；推荐等级只按当前 Top-K 名次展示；切换候选人时解释来自对应历史结果。
5. 打开“推荐记录”或“复核历史结果”，说明 Feedback 是观察、BadCase 是调查，不会自动变成训练标签。
6. 回到 README 指标表：LTR Test NDCG@5 为 0.9593，但只能解释为 5 个已暴露 synthetic Test Jobs 上的描述性结果。

## 8–10 分钟技术演示

### 1. 输入与结构化

- 说明 mock 模式确保测试与 E2E 可复现；Real mode 复用 OpenAI-compatible transport。
- Resume 通过“解析预览 → 确认入库 → 刷新派生索引”进入 Candidate Pool；岗位 JD 始终作为推荐 Query。
- 强调 schema-first validation、长度上限、timeout/retry、错误脱敏；无法确认的信息保持 missing。

### 2. 召回与排序

- Dense 与 BM25 Sparse 形成 RRF Hybrid pool。
- 10 个冻结显式特征进入 `ltr_ranker_v1`；model margin 不是 probability。
- CE 只做可选 rerank。它更“新”不代表应当成为默认；冻结证据未证明它超过 LTR。

### 3. Evidence 与历史

- 展示“为什么推荐该候选人”、Evidence reference 与“不可变运行轨迹”。
- Explanation provider 只返回闭合计划；后端从 Evidence Facts 渲染最终文本。
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
EXTRACTION_PROVIDER=deepseek
EXPLANATION_PROVIDER=deepseek
EXPLANATION_DEEPSEEK_BASE_URL=https://api.deepseek.com
EXPLANATION_DEEPSEEK_MODEL=deepseek-chat
EXPLANATION_DEEPSEEK_API_KEY=
```

不要在演示、截图、日志或聊天中展示 Key。Live smoke 只使用 synthetic 输入；外部 Provider 不可用时切回 mock，不把 fallback 伪装成 real success。

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
