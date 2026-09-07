# PeopleMatch Agent

**AI-powered Talent Matching & Recommendation System**

一个面向 AI 人才推荐场景的本地算法原型：以岗位为 Query，通过混合检索（Hybrid Retrieval）、显式特征工程、学习排序（Learning To Rank, LambdaMART）和证据约束解释（Evidence-grounded Explanation），从候选池生成可追踪、可复核的 Top-K 推荐列表。

它不是“把一份简历和 JD 发给 LLM，让模型给出匹配百分比”的 Demo。**岗位需求驱动候选人召回与排序；LLM 只负责结构化理解和解释，不拥有最终排名。**

[3 分钟演示指南](docs/demo-guide.md) · [Quick Start](#quick-startwindows-powershell) · [架构文档](docs/architecture.md) · [离线评测协议](docs/offline-evaluation.md)

![PeopleMatch Agent 岗位候选池 Top-K 排序结果](screenshots/phase15-top-k-recommendation.png)

**核心能力**

- **Retrieval**：Dense Embedding + BM25 Sparse + RRF Hybrid 构建候选池。
- **Ranking**：10 个显式特征进入 LightGBM LambdaMART，输出可复现候选顺序。
- **LLM Application**：结构化 Profile；基于 Evidence Bundle 生成解释，不直接打分或重排。
- **Evaluation & Review**：Offline Evaluation、MatchRun、Feedback 与 Bad Case Analysis 形成可审计证据链。

[查看 JD 与 Provider 状态](screenshots/phase15-jd-provider-status-1440x1024.png) · [查看人才库](screenshots/phase15-talent-library-1440x1024.png) · [查看 Candidate 详情](screenshots/phase15-candidate-detail.png) · [查看 Evidence 解释](screenshots/phase15-evidence-explanation.png) · [查看 MatchRun 轨迹](screenshots/phase15-matchrun-trace.png) · [作品集证据](docs/portfolio-evidence.md)

## 推荐系统如何工作

默认入口是岗位推荐：招聘者输入 JD Query，系统从 Candidate Pool 执行 Hybrid Retrieval、显式特征计算与 LambdaMART Ranking，输出该岗位下的 Top-K 候选人。Resume 不再出现在推荐入口；它属于人才库管理，用于新增候选人。

### Candidate Lifecycle

```mermaid
flowchart LR
  Resume[Resume Text] --> Extract[Structured Profile Extraction]
  Extract --> Profile[Candidate Profile]
  Profile --> Pool[Candidate Pool]
  JD[岗位 JD Query] --> Retrieval[Hybrid Retrieval]
  Pool --> Retrieval
  Retrieval --> Ranking[Feature Engineering + LambdaMART]
  Ranking --> TopK[Top-K Recommendation]
  TopK --> Explain[Evidence-grounded Explanation]
  Explain --> Review[Feedback / Bad Case Review]
```

人才库页面采用“解析预览 → 人工确认 → PostgreSQL 持久化 → 刷新 Qdrant 派生索引”的显式流程。新候选人会参与后续岗位推荐，但不会写入冻结数据集、修改原有 48 人 Candidate Profile 或影响 Phase 11 Evaluation fingerprint。

冻结的 48 人基础 Candidate Pool 不因展示层变化而改变；中文姓名/方向/优势来自独立的前端 presentation metadata，不写回 Candidate Profile，也不参与 Retrieval、Feature Engineering、LambdaMART 或 Evaluation fingerprint。中文 Resume/JD 安全示例只服务交互演示，不进入 Phase 11 Offline Evaluation。

## Algorithm Pipeline

```mermaid
flowchart LR
  Resume[Resume 入库] --> Extract[Candidate Profile 抽取]
  Extract --> Pool[Candidate Pool]
  JD[岗位 JD Query] --> Job[Job Representation]
  Pool --> Retrieval[Hybrid Retrieval<br/>Dense + Sparse + RRF]
  Job --> Retrieval
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

### AI Provider Architecture

Profile Extraction 与 Explanation 保持两个独立任务边界，共享同一个 OpenAI-compatible Chat Completions transport：

- `EXTRACTION_PROVIDER` 负责 Resume / JD 的 schema-first 结构化；
- `EXPLANATION_PROVIDER` 只在已持久化 Evidence Bundle 上生成闭合解释计划；
- 两个任务可独立选择 `mock` 或 `openai_compatible`，不会把 Provider 变成排序所有者；
- Prompt 使用独立版本与 SHA-256 fingerprint，Provider 状态 API 只投影模式、配置完整性和非敏感模型标识；
- timeout、rate limit、无效结构输出与缺失配置会映射为稳定错误，前端提供可重试的中文提示，不自动降级到 Mock。

Provider 切换不会改写 Candidate ordering、LTR Score 或 MatchRun result fingerprint。OpenAI-compatible 表示兼容本项目使用的 Chat Completions JSON-object contract，不等于所有厂商都完成了 live smoke。

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

打开 `http://localhost:3000`：在“推荐工作台”点击“加载中文 JD 示例”即可运行岗位驱动的 Top-K 推荐；在“人才库管理”可加载中文 Resume 示例，先预览 Structured Profile，再确认加入本地人才库。

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
EXTRACTION_PROVIDER=openai_compatible
EXPLANATION_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-id
LLM_API_KEY=
```

`deepseek` selector 与旧的 `EXPLANATION_DEEPSEEK_*` 环境变量仍作为兼容别名；新配置优先使用上面的 provider-neutral 字段，通用与旧字段冲突时会 fail closed。未完成 live smoke 的 Provider 不会被宣称为已验证。原始 Resume / JD 不进入 Phase 11 artifact；正式演示使用 repository 内 synthetic fixture。

> **Live Provider 验证状态：** `NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。OpenAI-compatible transport、structured output、timeout/retry/error redaction 已通过 mock transport 测试，但仓库不会把未实际调用的外部 Provider 写成 live PASS。

停止本地服务：

```powershell
docker compose stop
```

## 项目结构

```text
backend/app/services/
  profile_extraction/   # schema-first Resume/JD parsing
  retrieval/            # Dense / BM25 / RRF
  ranking/              # feature + LTR + optional CE
  match_runs/           # immutable execution history
  explanation/          # Evidence Bundle and grounded output
  feedback/             # Feedback / BadCase review
  evaluation/           # Phase 11 offline evaluator
frontend/src/           # JD 推荐、人才库、推荐记录与复核 UI
data/                   # synthetic dataset, contracts, frozen evidence
docs/                   # architecture, protocol, demo and portfolio evidence
scripts/                # data, model, evaluation and readiness entrypoints
```

## 测试与工程证据

- Backend：pytest 单元、契约、PostgreSQL/Qdrant integration；
- Frontend：Vitest、TypeScript、ESLint、Next.js production build；
- Browser E2E：disposable PostgreSQL + isolated Qdrant，稳定 mock provider，不依赖外部 API；
- Offline evaluation：immutable manifest、file hashes、pool/order fingerprint、Test seal 与 claim limitations。

- Backend：全量 `865 passed, 58 skipped`；
- Frontend：`76 passed`，并在 Node `22.23.2` 下通过 typecheck、ESLint 与 production build；
- Browser E2E：`3 passed`；使用独立 disposable PostgreSQL + Qdrant，分别覆盖 deterministic mock 与本地 MockTransport 驱动的 OpenAI-compatible 任意 JD 主链路、ranking invariance 和 Provider 错误恢复；
- Real-provider live smoke：`NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。

## 当前边界

这是可独立运行的本地产品原型，不是 production SaaS。当前没有真实用户、客户、招聘结果、在线 A/B、流量、QPS、业务提升、ATS / Bonjour 集成或真实市场代表性。认证、团队权限、后台队列与云部署也不在 canonical scope。

## 项目状态

Phase 0–15 已 **Completed / Frozen**。Phase 14 将 JD 推荐与 Resume 入库拆成两个清晰产品流程；Phase 15 在不改变冻结算法的前提下加入 provider-neutral 配置、版本化 Prompt、只读 Provider 状态与安全失败映射。当前交付是可本地运行、可复现、可审计的产品原型，不是 production deployment。详见 [Development Roadmap](docs/development-roadmap.md)。

---

**English abstract.** PeopleMatch Agent is a local, evidence-aware talent matching prototype combining hybrid retrieval, explicit features, LambdaMART ranking, grounded LLM explanations, immutable review history, and leakage-aware offline evaluation. The LLM never owns the final ranking.
