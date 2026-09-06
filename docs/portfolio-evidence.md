# PeopleMatch Agent 作品集证据

这份索引用于把简历与面试陈述绑定到 repository 证据，避免凭记忆夸大。

| Capability | Repository evidence | Demo evidence | 允许的表达 | 禁止的表达 |
| --- | --- | --- | --- | --- |
| Hybrid Retrieval | `backend/app/services/retrieval/`、Phase 4 docs | MatchRun retrieval step、R1 table | 实现 Dense/BM25/RRF 检索与可复现对比 | 检索普遍优于其他方案 |
| Explicit Features | `backend/app/services/features/`、`feature_schema_v1` | feature cards | 将技能、项目证据、方向、地点等显式特征化 | 特征等同真实招聘因果信号 |
| LambdaMART LTR | `data/eval/phase6/ltr_model_metadata_v1.json`、ignored native artifact | LTR Score 边界说明、R2 table | 构建并冻结 LambdaMART ranking baseline | 95.93% 招聘准确率 |
| Optional CE | Phase 7 manifest/report | R2 CE row | 评估 pinned Cross-Encoder 并基于证据保留为实验 | 使用 CE 所以更先进/更准 |
| MatchRun trace | Phase 8 services/contracts | Run ID、steps、fingerprint | 实现不可变排名历史与可追踪 provenance | 支持生产级审计合规 |
| Grounded Explanation | Phase 9 Evidence Bundle/provider/rendering | Evidence refs、为什么推荐该候选人 | 让 LLM 在闭合证据计划上生成可校验解释 | LLM 自主发现事实或决定排名 |
| Feedback / BadCase | Phase 10 services/API/UI | 历史复核与 BadCase 页面 | 实现 append-only review loop 与并发保护 | 已形成线上持续学习闭环 |
| Offline Evaluation | `docs/offline-evaluation.md`、final Test artifact | R1/R2 tables | 设计 incomplete-judgment、common-pool、Test-seal evaluator | 证明真实世界泛化或业务提升 |
| Real LLM boundary | Phase 12 extraction adapter + Phase 9 transport | Real mode config / mock E2E | 支持 OpenAI-compatible Provider 与 deterministic mock | 已验证所有 Provider 或已生产接入 DeepSeek |
| 推荐产品语义 | `candidate-display-metadata.ts`、中文 Demo-only fixtures | 七步 Story、48 人基础池、Top-K 卡片 | 将岗位 Query → Candidate Retrieval → Ranking 链路做成可交互中文 Demo | 中文展示 metadata 改善了模型效果或改变了离线结果 |
| Candidate Lifecycle | `candidate-pool-screen.tsx`、existing Candidate parse/list/index APIs | Resume 预览确认、人才库列表、JD-only 推荐 | 实现 Resume → Profile → Candidate Pool → 后续岗位推荐的显式本地流程 | 新增 runtime 候选人改变了冻结数据集或 Phase 11 结果 |

## 简历可用表述

> 独立构建基于 Dense/BM25 Hybrid Retrieval + LightGBM LambdaMART 的人岗匹配本地原型，实现 schema-first Resume/JD 结构化、Evidence-grounded LLM Explanation、不可变 MatchRun、Feedback/BadCase Review 与可复现 Offline Evaluation。

> 设计 incomplete-judgment 离线评测协议，在相同候选池上对比 Hybrid、LTR 与可选 Cross-Encoder；以 Test seal、artifact fingerprint 和明确 claim boundary 防止结果驱动调参。

> 复用 OpenAI-compatible transport 接入真实 LLM extraction/explanation boundary，同时保留 deterministic mock，验证 Provider 错误脱敏与 ranking invariance。

Phase 14 最终验证证据：backend 全量 `825 passed, 58 skipped`；frontend `62 passed` 并通过 typecheck/lint/build；Node 22 browser E2E `2 passed`。没有 live credential，因此只能说 OpenAI-compatible 边界与 mock transport 已验证，不能说外部 Provider live smoke 已通过。

## 高频面试问题

### 为什么不让 LLM 直接排序？

排名需要候选池可比、特征可追踪和结果可复现。LLM 擅长结构化和语言规划，但其输出不能覆盖 LTR margin 或重写历史顺序。

### 为什么使用 LambdaMART？

数据以 Job 为 query group，标签是 graded relevance，显式特征规模小；LambdaMART 与排序目标和 group 结构匹配，也便于 trace feature contract。

### Sparse 为什么比 equal-weight Hybrid 好？

只在当前 synthetic fixed sandbox 上观察到。可能来自关键技术词与岗位约束的精确匹配；正确工程决策是记录而不是重调 Hybrid 直到它赢。

### 为什么 CE 没成为默认？

模型是 MS-MARCO 域、未 fine-tune，冻结 Dev 对比未证明增益。产品默认保留较强且成本更低的 LTR，CE 只作为显式实验。

### 如何处理 unjudged？

未知不等于负例。Recall denominator 只含显式 relevant；R2 先证明完整相同 pool，再 condense 到相同 judged set；标准 Precision@K 被拒绝。

### Explanation 如何防幻觉？

Provider 看到 opaque Evidence refs，只能返回 closed plan；后端拥有 Evidence Facts 并通过固定 renderer 生成最终文本。未知信息不补写。

### Feedback 为什么不自动变标签？

反馈是特定上下文中的人类观察，BadCase 是调查聚合。没有独立 adjudication 就转换为 truth，会把流程状态和偏见污染训练/评测。

## 最终证据索引

- Git checkpoints：各 Phase freeze commits
- 架构：`docs/architecture.md`
- 产品入口：`README.md`
- Demo：`docs/demo-guide.md`
- 浏览器证据：`frontend/e2e/phase12.spec.ts`
- Offline evaluation：`data/eval/phase11/runs/20260831T173246Z_test_corrected_final/`
- LTR metadata：`data/eval/phase6/ltr_model_metadata_v1.json`
- CE evidence：`data/eval/phase7/`
- Explanation contract：`backend/app/services/explanation/`
- Review UI：`frontend/src/features/phase10/`
