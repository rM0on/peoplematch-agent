# PeopleMatch Agent

> 一个面向人岗匹配场景的 **Evidence-aware AI Matching & Ranking** 本地原型：用混合召回、显式特征、LambdaMART 排序和证据约束的大模型解释，生成可追踪、可复核的候选人推荐。

PeopleMatch Agent 不是“把简历和 JD 发给 LLM，让它给一个分数”的 Demo。系统把候选人理解、召回、排序、解释、人工复核与离线评测拆成独立阶段：**LLM 负责结构化与解释，但不拥有最终排名**。默认排序由冻结的 Hybrid Retrieval → Feature Engineering → LambdaMART 流水线产生。

[3 分钟演示指南](docs/demo-guide.md) · [Quick Start](#quick-startwindows-powershell) · [架构文档](docs/architecture.md) · [离线评测协议](docs/offline-evaluation.md)

![PeopleMatch Agent 匹配结果、证据解释与 MatchRun 轨迹](screenshots/phase12-hero-matching-results-1440x1280.png)

**核心能力**

- Resume / JD 文本可交互输入；支持 deterministic mock 与 OpenAI-compatible Provider。
- Dense + BM25 Sparse + RRF Hybrid 召回，显式区分“声称能力”和“项目证据”。
- LightGBM LambdaMART 是默认 ranking baseline；Cross-Encoder 仅保留为可选实验。
- MatchRun、Evidence Facts、ExplanationRun 与 Feedback / BadCase 历史不可变且可审计。
- 冻结的离线评测协议明确处理 incomplete judgments、同候选池可比性和 Test seal。

[查看输入工作台截图](screenshots/phase12-input-workbench-1440x1024.png) · [作品集证据](docs/portfolio-evidence.md)

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

## Matching Pipeline

1. **Structured Profile**：Resume / JD → Pydantic schema；未知信息保持 missing，不让模型补写项目、年限或证明。
2. **Retrieval**：Dense、Sparse、equal-weight RRF Hybrid 只负责 first-stage recall。
3. **Feature Engineering**：固定 10 个模型特征，项目证据与自述能力分开。
4. **LTR**：冻结的 `ltr_ranker_v1` 产生 raw model margin；它不是概率，也不是最终招聘分。
5. **Optional CE**：只对 shortlist rerank；因冻结证据未证明优于 LTR，未被提升为默认策略。
6. **Explanation**：Provider 只能返回闭合结构计划；Evidence Facts 与最终文案由后端控制。
7. **Review**：Feedback 是观察，BadCase 是调查；都不会自动成为训练标签。

## LLM 在哪里使用

LLM 可以做：

- 将真实风格 Resume / JD 文本解析成受约束的 CandidateProfile / JobProfile；
- 在对应历史 MatchRun 的 Evidence Bundle 上规划 explanation。

LLM 不可以做：

- 直接决定候选人顺序或覆盖 LTR score；
- 生成不存在的技能、项目、结果或 Evidence Fact；
- 修改 MatchRun、离线评测结果或 Feedback 历史。

默认 mock 模式不需要网络，适合测试与可复现演示。Real mode 复用 Phase 9 的 OpenAI-compatible transport、timeout、retry、错误映射与 secret redaction，不引入第二套 LLM client。

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

- Backend Phase 12 focused：`80 passed`；全量 backend：`822 passed, 58 skipped`（条件性 integration skip 不计为 PASS）。
- Frontend（Node `22.23.2`）：`49 passed`，typecheck / ESLint / production build 均 PASS。
- Browser E2E：`2 passed`；使用独立 disposable PostgreSQL + Qdrant，覆盖主链路、ranking invariance、历史复核与 Provider 错误恢复。
- Real-provider live smoke：`NOT RUN — LOCAL PROVIDER CREDENTIAL REQUIRED`。

## 当前边界

这是可独立运行的本地产品原型，不是 production SaaS。当前没有真实用户、客户、招聘结果、在线 A/B、流量、QPS、业务提升、ATS / Bonjour 集成或真实市场代表性。认证、团队权限、后台队列与云部署也不在 canonical scope。

## 项目状态

Phase 0–12 已 **Completed / Frozen**。当前交付是可本地运行、可复现、可审计的产品原型，不是 production deployment。详见 [Development Roadmap](docs/development-roadmap.md)。

---

**English abstract.** PeopleMatch Agent is a local, evidence-aware talent matching prototype combining hybrid retrieval, explicit features, LambdaMART ranking, grounded LLM explanations, immutable review history, and leakage-aware offline evaluation. The LLM never owns the final ranking.
