# PeopleMatch Agent

**AI-powered Talent Matching & Recommendation System**

一个面向 AI 人才推荐场景的本地算法原型：以岗位为 Query，通过混合检索（Hybrid Retrieval）、显式特征工程、学习排序（Learning To Rank, LambdaMART）和证据约束解释（Evidence-grounded Explanation），从候选池生成可追踪、可复核的 Top-K 推荐列表。

它不是“把一份简历和 JD 发给 LLM，让模型给出匹配百分比”的 Demo。**岗位需求驱动候选人召回与排序；LLM 只负责结构化理解和解释，不拥有最终排名。**

[3 分钟演示指南](docs/demo-guide.md) · [Quick Start](#quick-startwindows-powershell) · [架构文档](docs/architecture.md) · [离线评测协议](docs/offline-evaluation.md)

![PeopleMatch Agent 岗位候选池 Top-K 排序结果](screenshots/phase12-top-k-ranking-1440x1280.png)

**核心能力**

- **Retrieval**：Dense Embedding + BM25 Sparse + RRF Hybrid 构建候选池。
- **Ranking**：10 个显式特征进入 LightGBM LambdaMART，输出可复现候选顺序。
- **LLM Application**：结构化 Profile；基于 Evidence Bundle 生成解释，不直接打分或重排。
- **Evaluation & Review**：Offline Evaluation、MatchRun、Feedback 与 Bad Case Analysis 形成可审计证据链。

[查看产品首页](screenshots/phase12-product-home-1440x1024.png) · [查看算法工作台](screenshots/phase12-algorithm-workbench-1440x1024.png) · [查看 Evidence 解释](screenshots/phase12-evidence-explanation-1440x1024.png) · [作品集证据](docs/portfolio-evidence.md)

## 推荐系统如何工作

交互区允许粘贴一份 Resume 和一份 JD，是为了演示“新增候选人 + 新岗位 Query”的完整链路。系统并不是拿这两个文本直接输出一个分数：

1. Resume 被解析并加入本地候选池；
2. JD 被解析为岗位 Query；
3. 系统从整个候选池执行召回、特征计算和排序；
4. 最终返回该岗位下的 Top-K 候选人推荐，其中会标出本次输入的候选人。

这让 Demo 保留真实推荐系统语义，而不是退化成一对一文本相似度工具。

## Algorithm Pipeline

```mermaid
flowchart LR
  Input[Resume / JD 输入] --> Extract[结构化信息抽取]
  Extract --> Representation[Candidate / Job Representation]
  Representation --> Retrieval[Hybrid Retrieval<br/>Dense + Sparse + RRF]
  Retrieval --> Features[Feature Engineering<br/>10 个冻结特征]
  Features --> LTR[LambdaMART Ranking<br/>默认排序所有者]
  LTR -. optional .-> CE[Cross-Encoder Reranking]
  LTR --> Evidence[Evidence Bundle]
  CE --> Evidence
  Evidence --> Explain[Evidence-grounded Explanation]
  Explain --> Review[Feedback / Bad Case Analysis]
  LTR --> Eval[Offline Evaluation]
```

### Retrieval：先回答“谁有资格进入候选池”

- **Dense Retrieval** 使用 Embedding 捕捉岗位与候选经历之间的语义关联。
- **Sparse Retrieval** 使用 BM25 保留技能名、工具名和岗位关键词的精确匹配能力。
- **Hybrid Retrieval** 通过 equal-weight RRF 融合两路排序，作为 first-stage recall，而不是最终排名。

### Ranking：再回答“候选池应该如何排序”

冻结的 `ltr_ranker_v1` 使用 LambdaMART，对每个 Candidate / Job pair 的以下 10 个特征进行排序：

1. `semantic_score`
2. `sparse_score`
3. `skill_fit_score`
4. `project_evidence_score`
5. `role_direction_score`
6. `ai_tool_score`
7. `location_score`
8. `seniority_score`
9. `missing_penalty`
10. `overclaim_penalty`

LTR 输出是模型 margin，只用于候选人相对排序；它不是概率、匹配百分比或录用概率。Cross-Encoder 仅作为冻结的可选 Reranking 实验，没有因为模型更“新”就被提升为默认策略。

### Ranking Ownership

- **LTR 负责排序**：候选池、特征、模型版本和结果 fingerprint 均可追踪。
- **LLM 负责理解与解释**：解析 Resume/JD，并在已有 Evidence Bundle 上规划解释。
- Explanation 不能覆盖 LTR Score、改变候选顺序或修改历史 MatchRun。

## 为什么做这个项目

人岗匹配不是关键词检索问题。一个可解释的推荐至少需要回答：候选人是否进入候选池、哪些事实支持匹配、模型为何改变顺序、解释是否只引用已有证据、人工反馈是否被误当成 ground truth，以及离线数字能支持什么结论。

本项目因此将系统拆成可验证的阶段，而不是把职责交给单次 Prompt。

## 系统架构

```mermaid
flowchart LR
  UI[Next.js 产品工作台] --> API[FastAPI]
  API --> Extract[结构化 Profile<br/>Mock / OpenAI-compatible LLM]
  Extract --> PG[(PostgreSQL)]
  PG --> Docs[Versioned retrieval documents]
  Docs --> Q[(Qdrant derived index)]
  Q --> Dense[Dense Retrieval]
  PG --> Sparse[BM25 Sparse]
  Dense --> Hybrid[RRF Hybrid Pool]
  Sparse --> Hybrid
  Hybrid --> Features[Explicit Features]
  Features --> LTR[LambdaMART LTR<br/>默认排序]
  LTR -. 可选实验 .-> CE[Cross-Encoder]
  LTR --> Run[Immutable MatchRun]
  CE --> Run
  Run --> Facts[Evidence Facts]
  Facts --> Explain[Grounded LLM Plan<br/>+ deterministic rendering]
  Explain --> Review[Feedback / BadCase Review]
  Run --> Eval[Offline Evaluation]
```

运行时依赖方向保持为 `API → Service → Repository → PostgreSQL`。Qdrant 是可重建的检索状态；PostgreSQL 是 Profile 和历史记录的事实源。

## 工程阶段与数据边界

1. **Structured Profile**：Resume / JD → Pydantic schema；未知信息保持 missing，不让模型补写项目、年限或证明。
2. **Candidate / Job Representation**：声明、项目证据和约束保持结构化分离。
3. **Retrieval & Ranking**：Hybrid 负责候选池，LambdaMART 负责最终默认排序。
4. **Historical Trace**：MatchRun 固化输入、阶段、候选顺序和 fingerprint。
5. **Explanation**：Provider 只能返回闭合结构计划；Evidence Facts 与最终文案由后端控制。
6. **Review**：Feedback 是观察，BadCase 是调查；二者都不会自动成为训练标签。
7. **Offline Evaluation**：固定协议比较 Retrieval、LTR 与可选 CE，Test 结果不反向改变策略。

## LLM 在哪里使用

LLM 可以做：

- 将真实风格 Resume / JD 文本解析成受约束的 CandidateProfile / JobProfile；
- 在对应历史 MatchRun 的 Evidence Bundle 上规划 explanation。

LLM 不可以做：

- 直接决定候选人顺序或覆盖 LTR score；
- 生成不存在的技能、项目、结果或 Evidence Fact；
- 修改 MatchRun、离线评测结果或 Feedback 历史。

默认 mock 模式不需要网络，适合测试与可复现演示。Real mode 复用 Phase 9 的 OpenAI-compatible transport、timeout、retry、错误映射与 secret redaction，不引入第二套 LLM client。

## Evidence First 与 Evaluation Driven Development

Explanation 的每个关键陈述必须映射到对应 MatchRun 的 Evidence Facts。Provider 不是事实源，无法从证据中确认的信息保持 missing、risk 或待验证，避免把自然语言流畅度误当成事实可靠性。

算法变更也不能依靠单个漂亮案例判断。Phase 11 在固定 dataset、split、候选池和 metric semantics 下保存 immutable evaluation artifact；Phase 10 Feedback 与 `VERIFIED` BadCase 只用于诊断，不会自动变成 relevance ground truth。

## 离线评测结果

以下数字来自冻结 Test artifact：[`20260831T173246Z_test_corrected_final`](data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.md)。Sparse 与 LTR 是在 Dev 上按预声明规则选出的 leader；Test 结果不用于重新选择策略。

### R1 Retrieval — Recall@K

| Strategy | Recall@5 | Recall@10 | Recall@20 |
| --- | ---: | ---: | ---: |
| Dense V4 | 0.42 | 0.42 | 0.70 |
| Sparse BM25 V4 | **0.67** | **0.80** | **0.95** |
| Hybrid RRF V4 | 0.47 | 0.66 | 0.90 |

### R2 Controlled Ranking — 同一 48-Candidate pool

| Strategy | NDCG@5 | NDCG@10 | MRR@10 | Explicit Pairwise |
| --- | ---: | ---: | ---: | ---: |
| Hybrid RRF V4 | 0.7920 | 0.8343 | 0.90 | 0.80 |
| LambdaMART LTR | **0.9593** | **0.9597** | **1.00** | **1.00** |
| Cross-Encoder experiment | 0.8991 | 0.9212 | **1.00** | 0.90 |

> **评测边界：**数据为 `synthetic_curated`；48 Candidates × 24 Jobs 中只有 288 个显式 graded judgments（25% coverage）；Test 仅 5 个 Jobs；Phase 4 构建期间 Test queries 曾被查看。因此它是 **post-exposure fixed synthetic sandbox evaluation**，不是 pristine held-out、真实招聘准确率或现实市场泛化证据。

标准 Precision@K 被拒绝：judgment matrix 不完整，`unjudged != negative`。协议使用 Recall、judged-condensed NDCG/MRR 与独立显式 pairwise preferences，避免把未知候选人静默计为负例。

## 几个关键工程决策

- **为什么不让 LLM 排序？** 排序需要可复现的候选池、特征和模型 provenance；自然语言解释不应反向改变分数。
- **为什么 Sparse 能超过 Hybrid？** 这是当前固定 synthetic sandbox 上的观察，不是一般规律；项目保留真实结果，没有为美化报告重调权重。
- **为什么 CE 不是默认？** 它是 MS-MARCO 域模型且未 fine-tune；冻结 Dev 证据未证明它优于 LTR。
- **为什么历史 artifact 不可变？** 解释、复核和后续评测必须能回到当时的输入、顺序和 Evidence snapshot。
- **为什么 Test 先 seal？** metric、策略、slice、report 与 source fingerprint 在 Test 前冻结，防止看结果后改规则。

## Quick Start（Windows PowerShell）

### 前置条件

- Python 3.12 与 `backend/.venv`
- **Node.js 22 LTS**、npm 10+
- Docker Desktop、Docker Compose v2
- 本地已有冻结的 LTR 与 CE artifacts；二者被 `.gitignore` 排除，fresh clone 需按下文准备

先运行只读 doctor：

```powershell
backend/.venv/Scripts/python.exe scripts/demo_doctor.py
```

### 1. 配置并启动基础设施

```powershell
Copy-Item .env.example .env
docker compose up -d postgres redis qdrant
```

### 2. 准备数据库、数据与索引

```powershell
$env:DATABASE_URL='postgresql+asyncpg://peoplematch:peoplematch_local@127.0.0.1:5432/peoplematch'
$env:QDRANT_URL='http://127.0.0.1:6333'
Push-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
Pop-Location
backend/.venv/Scripts/python.exe scripts/seed_database.py
backend/.venv/Scripts/python.exe scripts/build_retrieval_index.py
```

### 3. 启动 Backend 与 Frontend

```powershell
# Terminal A
Set-Location backend
$env:DATABASE_URL='postgresql+asyncpg://peoplematch:peoplematch_local@127.0.0.1:5432/peoplematch'
$env:QDRANT_URL='http://127.0.0.1:6333'
.venv/Scripts/python.exe -m uvicorn app.main:app --reload

# Terminal B
Set-Location frontend
$env:NEXT_PUBLIC_API_BASE_URL='http://localhost:8000'
npm install
npm run dev
```

打开 `http://localhost:3000`，点击“加载安全示例”后运行完整匹配。

### Model artifact 准备

Artifact 不提交到 Git。使用固定 metadata 与校验脚本：

```powershell
backend/.venv/Scripts/python.exe scripts/check_ltr_artifacts.py
backend/.venv/Scripts/python.exe scripts/prepare_cross_encoder_model.py
backend/.venv/Scripts/python.exe scripts/check_cross_encoder_model.py
```

LTR fresh generation 涉及训练，只应遵循 [Phase 6 文档](docs/ltr-ranking.md)；不要为了 Demo 或 Test 结果重训。

## Demo Mode 与 Real LLM Mode

Mock 默认值：

```dotenv
EXTRACTION_PROVIDER=mock
EXPLANATION_PROVIDER=mock
```

Real mode 在本地 `.env` 填写，不要把 Key 发到 issue、聊天或 Git：

```dotenv
EXTRACTION_PROVIDER=deepseek
EXPLANATION_PROVIDER=deepseek
EXPLANATION_DEEPSEEK_BASE_URL=https://api.deepseek.com
EXPLANATION_DEEPSEEK_MODEL=deepseek-chat
EXPLANATION_DEEPSEEK_API_KEY=
```

这是一条 OpenAI-compatible compatibility path。未完成 live smoke 的 Provider 不会被宣称为已验证。原始 Resume / JD 不进入 Phase 11 artifact；正式演示使用 repository 内 synthetic fixture。

> **Live Provider 验证状态：** `NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。OpenAI-compatible transport、structured output、timeout/retry/error redaction 已通过 mock transport 测试，但仓库不会把未实际调用的外部 Provider 写成 live PASS。

停止本地服务：

```powershell
docker compose stop
```

## 项目结构

```text
backend/app/services/
  profile_extraction/   # schema-first mock / real provider parsing
  retrieval/            # Dense / BM25 / RRF
  ranking/              # feature + LTR + optional CE
  match_runs/           # immutable execution history
  explanation/          # Evidence Bundle and grounded output
  feedback/             # Feedback / BadCase review
  evaluation/           # Phase 11 offline evaluator
frontend/src/           # Next.js product and review UI
data/                   # synthetic dataset, contracts, frozen evidence
docs/                   # architecture, protocol, demo and portfolio evidence
scripts/                # data, model, evaluation and readiness entrypoints
```

## 测试与工程证据

- Backend：pytest 单元、契约、PostgreSQL/Qdrant integration；
- Frontend：Vitest、TypeScript、ESLint、Next.js production build；
- Browser E2E：disposable PostgreSQL + isolated Qdrant，稳定 mock provider，不依赖外部 API；
- Offline evaluation：immutable manifest、file hashes、pool/order fingerprint、Test seal 与 claim limitations。

- Backend Docker explanation contract：`10 passed`；全量 backend：`823 passed, 58 skipped`（条件性 integration skip 不计为 PASS）。
- Frontend（Node `22.23.2`）：`49 passed`，typecheck / ESLint / production build 均 PASS。
- Browser E2E：`2 passed`；使用独立 disposable PostgreSQL + Qdrant，覆盖主链路、ranking invariance、历史复核与 Provider 错误恢复。
- Real-provider live smoke：`NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。

## 当前边界

这是可独立运行的本地产品原型，不是 production SaaS。当前没有真实用户、客户、招聘结果、在线 A/B、流量、QPS、业务提升、ATS / Bonjour 集成或真实市场代表性。认证、团队权限、后台队列与云部署也不在 canonical scope。

## 项目状态

Phase 0–12 已 **Completed / Frozen**。当前交付是可本地运行、可复现、可审计的产品原型，不是 production deployment。详见 [Development Roadmap](docs/development-roadmap.md)。

---

**English abstract.** PeopleMatch Agent is a local, evidence-aware talent matching prototype combining hybrid retrieval, explicit features, LambdaMART ranking, grounded LLM explanations, immutable review history, and leakage-aware offline evaluation. The LLM never owns the final ranking.
