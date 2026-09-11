# PeopleMatch Agent

## Evidence-grounded AI Talent Matching System

**基于 LLM + Hybrid Retrieval + Learning-to-Rank 的智能人才推荐系统。**

招聘者输入一段岗位描述（JD），系统先用 LLM 将自然语言需求转成结构化职位画像，再从人才库执行混合检索（Hybrid Retrieval），用 LambdaMART 对候选人排序，最后基于本次匹配中已记录的 Evidence 生成推荐解释。

这不是聊天机器人，也不是“把简历和 JD 发给大模型，让它给一个匹配百分比”的套壳应用。**候选顺序由可评测的 Retrieval + Ranking 链路决定；LLM 负责理解与解释，不拥有最终排名。**

[3 分钟产品演示](docs/demo-guide.md) · [快速启动](#快速启动windows-powershell) · [系统架构](docs/architecture.md) · [离线评测](docs/offline-evaluation.md) · [作品集证据](docs/portfolio-evidence.md)

![PeopleMatch Agent Top-K 人才推荐结果](screenshots/phase15-top-k-recommendation.png)

| 系统能力 | 解决的问题 |
| --- | --- |
| **Hybrid Retrieval** | 结合 Embedding 语义召回与 BM25 精确匹配，构建可追踪的候选池 |
| **LambdaMART Ranking** | 基于显式匹配特征生成稳定、可复现的 Top-K 候选顺序 |
| **Evidence-grounded Explanation** | 让推荐原因、风险和面试建议只能引用已有证据，而非自由编造 |
| **MatchRun + Offline Evaluation** | 保存检索、排序和解释的运行轨迹，并在冻结协议下评测系统 |

---

## 产品演示

### 1. 输入任意岗位 JD

![JD 输入与 AI Provider 状态](screenshots/phase15-jd-provider-status-1440x1024.png)

**用户看到：** JD 是推荐 Query；在 OpenAI-compatible 模式下可以直接输入任意岗位需求，“加载中文 JD 示例”只是辅助。右上角显示当前 AI Provider 的配置状态。

**技术含义：** JD 先进入 schema-first Structured Extraction。Provider 状态只表示“已配置”，不把配置成功包装成网络连通性证明。

### 2. 获得 Top-K 人才推荐

![岗位候选池 Top-K 推荐](screenshots/phase15-top-k-recommendation.png)

**用户看到：** 系统从人才库召回候选人，展示推荐等级、召回名次、LTR 名次与候选人技术方向。

**技术含义：** 排序模型分值（LTR Score）是 LambdaMART 的原始 margin，只用于相对排序；它不是匹配概率、录用概率或成功率。

### 3. 查看候选人排序依据

![候选人排序详情](screenshots/phase15-candidate-detail.png)

**用户看到：** 每位候选人的技能匹配、项目证据、方向、地点和资历信号，以及可展开的技术 ID。

**技术含义：** 用户界面展示的是冻结 Feature Contract 的可读投影；展示层不会重算特征或覆盖模型顺序。

### 4. 阅读证据约束解释

![Evidence-grounded 候选人解释](screenshots/phase15-evidence-explanation.png)

**用户看到：** 推荐优势、风险提示和技术证据按候选人分别呈现。

**技术含义：** Provider 只看到脱敏的 opaque Evidence references。输出必须通过 `ExplanationPlanV1` Schema 与 Grounding Validation；无法被证据支持的内容会被拒绝，而不是直接显示。

### 5. 回看 MatchRun 运行轨迹

![MatchRun 不可变运行轨迹](screenshots/phase15-matchrun-trace.png)

**用户看到：** 输入解析、LambdaMART 排序、结果持久化等阶段及完成状态。

**技术含义：** MatchRun 固化当时的输入、候选顺序、模型/配置 provenance 和 Evidence snapshot，使解释、复核与评测可以回到同一次历史执行。

### 6. 管理 Candidate Lifecycle

![人才库管理与 Resume 入库](screenshots/phase15-talent-library-1440x1024.png)

**用户看到：** Resume 文本先被解析为 Candidate Profile，人工确认后才进入人才库；推荐入口始终保持 JD-first。

**技术含义：** PostgreSQL 是 Profile 事实源，Qdrant 是可重建的派生索引。Demo 的中文展示 metadata 不写回冻结 Candidate Profile，也不参与算法 fingerprint。

---

## 为什么需要这套系统

真实人岗推荐同时面对四类问题：

- **输入非结构化：** JD 与 Resume 的表达方式、粒度和语言并不一致；
- **关键词不等于能力：** 技能声明、项目证据、岗位方向和约束需要分别建模；
- **单一召回不够：** 语义相似能找近义表达，精确检索才能稳住技术名词与硬约束；
- **LLM 可能幻觉：** 流畅的解释不代表事实正确，更不能成为不可审查的排序黑盒。

PeopleMatch Agent 因此采用混合 AI 架构：让 LLM 做它擅长的语义结构化与语言规划，让 Retrieval / Learning-to-Rank 做可比较、可复现的候选排序，再由确定性验证层控制最终可展示内容。

## 系统架构

```mermaid
flowchart TD
    JD["用户输入 Job Description"] --> LLM1["LLM Job Understanding"]
    LLM1 --> Job["Structured Job Profile"]

    Resume["Resume Text"] --> LLM2["Structured Candidate Extraction"]
    LLM2 --> Candidate["Candidate Profile"]
    Candidate --> Pool[(Candidate Pool / PostgreSQL)]
    Pool --> Index[(Qdrant Derived Index)]

    Job --> Retrieval["Hybrid Retrieval"]
    Index --> Retrieval
    Pool --> Retrieval
    Retrieval --> Features["Feature Engineering"]
    Features --> LTR["LambdaMART Ranking<br/>DEFAULT RANKING OWNER"]
    LTR --> TopK["Top-K Candidates"]

    TopK --> Run["Immutable MatchRun"]
    Run --> Evidence["Evidence Builder"]
    Evidence --> LLM3["LLM Explanation Plan"]
    LLM3 --> Schema["Schema Validation"]
    Schema --> Grounding["Grounding Validation"]
    Grounding --> Output["Final Recommendation"]
    Output --> Review["Feedback / Bad Case Review"]

    LTR -. "optional experiment on the frozen shortlist" .-> CE["Cross-Encoder<br/>OPTIONAL EXPERIMENT"]
    CE -. "experimental order only" .-> CEOrder["Cross-Encoder Experimental Order"]
```

> **Ranking ownership：** 默认候选顺序来自冻结的 LambdaMART pipeline。LLM explanation 在排序完成后运行，不能修改 Candidate ordering、LTR Score 或 ranking fingerprint。

### Candidate Lifecycle

```text
Resume Text
    → Structured Profile Extraction
    → Human Confirmation
    → Candidate Profile in PostgreSQL
    → Derived Embedding Index in Qdrant
    → Future JD Retrieval & Ranking
```

推荐与入库是两个独立产品流程：招聘者用 JD 搜索人才；HR 用 Resume 扩充人才库。新增运行时候选人不会写入冻结的离线评测数据集。

---

## AI System Design

### LLM 的职责

- 将 JD / Resume 解析为受 Pydantic Schema 约束的结构化 Profile；
- 在已持久化 MatchRun 的 Evidence Bundle 上生成 explanation plan；
- 对已有事实进行表达与组织，不生成排序分数。

### Retrieval 与 Ranking 的职责

- **Dense Retrieval：** 使用 Embedding 捕捉语义层面的能力关联；
- **Sparse Retrieval：** 使用 BM25 保留技能名、工具名和岗位约束的精确匹配；
- **Hybrid Retrieval：** 通过 equal-weight RRF 合并两路召回，形成 first-stage candidate pool；
- **Feature Engineering：** 将 Candidate / Job pair 投影为 10 个冻结显式特征；
- **LambdaMART：** 学习 query-group 内的候选相对顺序，是默认 ranking owner；
- **Cross-Encoder：** 只在冻结实验路径中重排 LambdaMART shortlist；产品默认 Top-K 始终采用 LambdaMART order。

冻结的 `ltr_ranker_v1` 使用以下特征：

| 匹配信号 | 约束与风险 |
| --- | --- |
| `semantic_score` | `location_score` |
| `sparse_score` | `seniority_score` |
| `skill_fit_score` | `missing_penalty` |
| `project_evidence_score` | `overclaim_penalty` |
| `role_direction_score` |  |
| `ai_tool_score` |  |

### 为什么不让 LLM 直接排序

推荐排序需要固定候选池、可追踪特征、稳定比较和离线评测。LLM 输出具有采样性，也容易把表达流畅度误当成候选质量。将 Ranking 与 Explanation 解耦后：

1. 模型顺序可以被复现和比较；
2. LLM 故障不会改写已有排名；
3. 解释可以独立验证、拒绝和重试；
4. 每项结论都能回到对应 Evidence 与 MatchRun。

---

## Evidence-grounded Explanation

LLM 生成推荐解释时，最大的风险不是语法错误，而是**说出看似合理、实际不存在的候选经历**。本项目没有把 Provider response 直接交给前端，而是设置了闭合验证链路：

```text
Historical MatchRun
    → Evidence Facts
    → Opaque Reference Projection
    → Explanation Prompt v2
    → ExplanationPlanV1 Validation
    → Evidence Grounding Validation
    → Deterministic Rendering & Persistence
```

当 Provider 输出结构正确但引用关系不满足 grounding contract 时，系统允许一次受约束修复：

- 只向 Provider 返回错误类别和原有脱敏 evidence projection；
- Repair Output Normalizer 只对 repair attempt 中已有的 opaque reference 做确定性排序与去重；
- 不创建 reference、不补充事实、不删除 grounding violation；
- 未知 reference、虚构 requirement 或无证据 rewrite 仍然 fail closed。

最终显示的推荐优势、风险与面试建议，必须能够映射到 Candidate Evidence、Job Requirement 或明确的 missing requirement。

## Provider Architecture

Profile Extraction 与 Explanation 保持独立领域边界，但共享一套 OpenAI-compatible transport：

```mermaid
flowchart LR
    Config["Environment-backed Config"] --> Transport["Shared OpenAI-compatible Transport"]
    Transport --> Extraction["Extraction Task Adapter"]
    Transport --> Explanation["Explanation Task Adapter"]
    Mock["Deterministic Mock"] --> Extraction
    Mock --> Explanation
    Extraction --> Profile["Candidate / Job Profile"]
    Explanation --> Plan["Grounded Explanation Plan"]
```

| 能力 | 设计 |
| --- | --- |
| Provider 选择 | `mock` / `openai_compatible`，并保留 `deepseek` 兼容 selector |
| 任务隔离 | `EXTRACTION_PROVIDER` 与 `EXPLANATION_PROVIDER` 可独立配置 |
| Prompt 追踪 | Candidate extraction、Job extraction、Explanation 使用独立版本与 SHA-256 fingerprint |
| 密钥管理 | API Key 仅从本地环境变量读取，不进入前端、日志、响应或 artifact |
| 失败处理 | missing config、timeout、rate limit、provider unavailable、invalid output 均映射为稳定错误，不自动降级到 Mock |
| 状态展示 | 只读 API 展示模式与“已配置”状态，不声称 Provider 已连接 |

OpenAI-compatible 路径曾使用 **Qwen3.7-plus** 完成本机受控兼容性验证：Job Extraction、Evidence-grounded Explanation 与受约束 Grounding Repair 得到通过结果，且 explanation 前后的 Candidate ordering、LTR Score 和 ranking fingerprint 保持不变。该验证未形成可复现的仓库 artifact，不能替代已提交的 deterministic mock、MockTransport 与 E2E 证据，也不构成生产可用性、服务 SLA 或其他兼容模型已验证的声明。

---

## 工程设计亮点

| 设计决策 | 工程价值 |
| --- | --- |
| **Ranking Freeze** | Explanation 不能修改分数、顺序或历史 MatchRun |
| **Provider Isolation** | 外部 LLM 故障通过稳定错误边界隔离，不污染 Retrieval / Ranking |
| **Schema + Grounding Validation** | 同时验证输出结构和事实引用，拒绝 unsupported explanation |
| **Immutable Traceability** | MatchRun 保存阶段、顺序、配置、模型和 Evidence provenance |
| **Feedback ≠ Ground Truth** | Feedback / Bad Case 用于诊断，不自动变成训练标签或评测真值 |
| **Evaluation Before Claims** | 指标、策略、候选池和 Test seal 在正式 Test 前冻结 |
| **Deterministic Mock** | CI、本地演示与浏览器 E2E 不依赖外部 Provider |

## Offline Evaluation

Phase 11 使用冻结的 `phase11_eval_protocol_v1`，分别评测全语料 Retrieval 和同一候选池上的 Controlled Ranking。以下结果来自正式 Test artifact：[`20260831T173246Z_test_corrected_final`](data/eval/phase11/runs/20260831T173246Z_test_corrected_final/report.md)。

### R1 · Retrieval Recall@K

| Strategy | Recall@5 | Recall@10 | Recall@20 |
| --- | ---: | ---: | ---: |
| Dense V4 | 0.42 | 0.42 | 0.70 |
| **Sparse BM25 V4** | **0.67** | **0.80** | **0.95** |
| Hybrid RRF V4 | 0.47 | 0.66 | 0.90 |

### R2 · Controlled Ranking（同一 48-Candidate Pool）

| Strategy | NDCG@5 | NDCG@10 | MRR@10 | Explicit Pairwise |
| --- | ---: | ---: | ---: | ---: |
| Hybrid RRF V4 | 0.7920 | 0.8343 | 0.90 | 0.80 |
| **LambdaMART LTR** | **0.9593** | **0.9597** | **1.00** | **1.00** |
| Cross-Encoder experiment | 0.8991 | 0.9212 | **1.00** | 0.90 |

Sparse 与 LTR 是 Test 前按 Dev 规则预先选定的 leader；Test 没有用于重新选择策略。标准 **Precision@K 没有报告，也没有被包装成其他指标**：只有 25% Candidate / Job pairs 有显式 judgment，`unjudged != negative`，此时标准 Precision 会把未知样本错误计为负例。

> **评测边界必须与数字一起阅读：** 数据是 synthetic curated sandbox；包含 24 Jobs、48 Candidates、288 个显式 graded judgments；Test 只有 5 个 Jobs；Phase 4 期间这些 Test queries 曾被查看。因此这里只能做 **post-exposure fixed synthetic sandbox comparison**，不能解释为 pristine held-out、真实招聘准确率、统计显著提升或现实市场泛化能力。

---

## 技术栈

| 层 | 技术与职责 |
| --- | --- |
| Backend | Python 3.11、FastAPI、Pydantic、SQLAlchemy、Alembic |
| Storage | PostgreSQL（事实源）、Qdrant（派生向量索引）、Redis（基础设施预留，业务使用尚未实现） |
| Retrieval | Sentence Transformers、Dense Embedding、BM25、RRF Hybrid Retrieval |
| Ranking | 显式 Feature Engineering、LightGBM LambdaMART（默认 ranking owner）、Cross-Encoder（可选实验） |
| LLM Application | Provider-neutral 配置、OpenAI-compatible transport、版本化 Prompt、Structured Output、基于 MatchRun Evidence projection 的 grounded generation |
| Frontend | Next.js 16、React 19、TypeScript、Tailwind CSS 4、CSS Modules |
| Engineering | Docker Compose、pytest、Vitest、Playwright、ESLint、Git |

## 项目演进

| 阶段 | 形成的能力 |
| --- | --- |
| Phase 0–3 | 工程基线、Schema、PostgreSQL 持久化与 Structured Profile Extraction |
| Phase 4–7 | Dense / Sparse / Hybrid Retrieval、显式特征、LambdaMART 与可选 Cross-Encoder |
| Phase 8–10 | Immutable MatchRun、Evidence-grounded Explanation、Feedback / Bad Case Review |
| Phase 11 | 带 provenance、candidate-pool proof 与 Test seal 的 Offline Evaluation |
| Phase 12–14 | JD-first 产品工作台、Candidate Lifecycle、中文 Demo 与浏览器 E2E |
| Phase 15 | Provider-neutral runtime、Prompt provenance、安全错误映射、Qwen 兼容与 constrained repair |

关键工程里程碑：

- `6324be168` — `feat: add provider-neutral llm runtime`
- `4c0acf41` — `fix: normalize phase15 provider compatibility inputs`
- `27fad52f` — `feat: align qwen explanation grounding constraints`

---

## 快速启动（Windows PowerShell）

### 前置条件

- Python 3.11（与 `backend/Dockerfile` 的 canonical runtime 一致）
- Node.js 22 LTS、npm 10+
- Docker Desktop 与 Docker Compose v2
- Git；以下命令从 fresh clone 的仓库根目录执行

### 0. Fresh clone 依赖与模型 artifact

Fresh clone 不包含 `.env`、`backend/.venv`、`frontend/node_modules`，也不包含被 `.gitignore` 排除的模型二进制文件。先安装本地依赖：

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt

Push-Location frontend
npm ci
Pop-Location
```

完整推荐链路需要冻结的 LTR artifact：`artifacts/phase6/ltr_ranker_v1.txt`。该文件不会在应用启动或 `docker compose up` 时自动下载/生成；fresh clone 需要从项目所有者保存的 approved local artifact 恢复，或严格按照 [Phase 6 可复现训练说明](docs/ltr-ranking.md)生成。后者会实际执行训练，不应被当作 Demo 启动步骤，也不得用于改写冻结评测结论。

Cross-Encoder 不是默认 ranking owner，仅用于可选实验；若需要复现实验路径，可用仓库脚本准备固定 snapshot（fresh clone 首次执行需要访问模型源）：

```powershell
backend/.venv/Scripts/python.exe scripts/check_ltr_artifacts.py
backend/.venv/Scripts/python.exe scripts/prepare_cross_encoder_model.py
backend/.venv/Scripts/python.exe scripts/check_cross_encoder_model.py
```

模型 artifact 就绪后运行只读环境检查：

```powershell
backend/.venv/Scripts/python.exe scripts/demo_doctor.py
```

### 1. 创建本地配置并启动基础设施

```powershell
Copy-Item .env.example .env
docker compose up -d postgres redis qdrant
```

`.env` 只用于本机且已被 Git 忽略。默认 Provider 为 deterministic mock，不需要 API Key。

### 2. 初始化数据库与检索索引

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
```

```powershell
# Terminal B
Set-Location frontend
$env:NEXT_PUBLIC_API_BASE_URL='http://localhost:8000'
npm run dev
```

| 入口 | 地址 |
| --- | --- |
| 产品界面 | <http://localhost:3000> |
| Backend Health | <http://localhost:8000/health> |
| OpenAPI Docs | <http://localhost:8000/docs> |

默认 Mock 模式只接受仓库中已登记的 deterministic fixtures，请在“推荐工作台”加载中文 JD 示例。“人才库管理”可加载中文 Resume 示例，预览 Candidate Profile 并确认入库。配置 OpenAI-compatible Provider 后，推荐入口支持任意 JD 文本。

### 4. 可选：启用真实 OpenAI-compatible Provider

只在本地 `.env` 中填写，不要把密钥提交到 Git 或发送到 issue：

```dotenv
EXTRACTION_PROVIDER=openai_compatible
EXPLANATION_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-id
LLM_API_KEY=
```

也可以让两个任务分别使用 mock / real provider。缺少配置时系统会明确失败，不会静默切换到 Mock。

停止本地服务：

```powershell
docker compose stop
```

---

## 如何测试一个 AI 系统

本项目把测试分为四类，而不是只验证“API 返回 200”：

- **Backend contracts：** Profile schema、Provider selection、Prompt fingerprint、错误映射、Evidence grounding；
- **Ranking invariance：** 解释生成前后 Candidate ordering、LTR Score、ranking fingerprint 必须一致；
- **Frontend contracts：** 运行时响应校验、Provider 状态、loading / error / retry、中文产品语义；
- **Browser E2E：** Browser → Next.js → FastAPI → PostgreSQL / Qdrant → Retrieval → Ranking → Explanation，稳定测试使用 deterministic mock 或本地 MockTransport；
- **Offline Evaluation：** immutable manifest、file hashes、pool/order fingerprints 和 sealed Test provenance。

## 面试讨论入口

### 1. 为什么不直接让 LLM 给匹配分？

因为 LLM 输出难以稳定复现，也无法自然保证候选池公平比较。这里由 LambdaMART 负责排序，LLM 只处理结构化理解和受 Evidence 约束的解释。

### 2. 为什么要组合 Retrieval 与 LambdaMART？

Retrieval 解决大候选空间中的召回效率与覆盖，LambdaMART 在相同候选池上融合语义、关键词、技能、项目和约束信号；两个阶段优化目标不同。

### 3. 如何控制 explanation hallucination？

Provider 只能选择已有 opaque references；后端执行 Schema Validation、Grounding Validation 和确定性渲染。一次 constrained repair 只修复闭合契约违规，不允许创造事实。

### 4. 为什么 Sparse 在当前评测里优于 Hybrid？

这是固定 synthetic sandbox 中的描述性观察，可能来自关键技术词与岗位约束的精确匹配。项目保留真实结果，没有为了让 Hybrid 获胜而在 Test 后调权重。

### 5. 为什么 Cross-Encoder 没成为默认方案？

它使用冻结的 MS-MARCO 域模型且未针对本数据 fine-tune；Dev 证据没有证明它优于 LTR，因此仍是可选实验。

### 6. Feedback 为什么不自动变成训练标签？

Feedback 是特定上下文中的人工观察，Bad Case 是调查记录。未经独立 adjudication 就写入 truth，会把流程状态、偏见和噪声污染训练与评测。

### 7. Provider abstraction 如何保证可测试性？

Extraction / Explanation 各自拥有 task adapter，复用共享 transport；deterministic mock、MockTransport 与 live provider 使用相同业务边界，Provider 切换不触碰 Ranking。

---

## 项目结构

```text
backend/app/services/
  profile_extraction/   # Candidate / Job structured extraction
  llm/                  # provider-neutral config and status
  retrieval/            # Dense / BM25 / RRF
  features/             # frozen explicit feature contract
  ranking/              # LambdaMART ranking
  cross_encoder/        # optional reranking experiment
  match_runs/           # immutable execution history
  explanation/          # Evidence, Prompt v2, grounding and repair
  feedback/             # Feedback / Bad Case workflow
  evaluation/           # Phase 11 offline evaluator
frontend/src/           # JD 推荐、人才库、Provider 状态、历史与复核 UI
data/                   # synthetic data, contracts and frozen evidence
docs/                   # architecture, protocol, demo and portfolio evidence
scripts/                # readiness, data, index, model and evaluation tools
screenshots/            # verified product captures used by this README
```

## 当前边界

PeopleMatch Agent 是一个**可本地运行、可复现、可审计的 AI 人才推荐原型**，不是 production SaaS。当前没有真实用户、客户、招聘结果、在线 A/B、生产流量、QPS / SLA、商业收益、ATS / Bonjour 集成或现实市场代表性。

离线数据全部为 synthetic / sandbox；仓库不提交真实简历、个人信息或 Provider credential。认证、团队权限、异步任务队列、PDF ingestion 与云部署不属于当前 canonical scope。

---

**English abstract.** PeopleMatch Agent is an evidence-grounded talent recommendation prototype combining LLM-based structured extraction, hybrid retrieval, explicit features, LambdaMART ranking, validated explanations, immutable execution history, and leakage-aware offline evaluation. The LLM never owns the final ranking.
