"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppSidebar } from "@/features/matching-results/app-sidebar";
import { getCandidatePresentation } from "@/features/matching-results/candidate-display-metadata";
import layoutStyles from "@/features/matching-results/matching-results.module.css";
import {
  addCandidateToPool,
  DemoApiError,
  fetchDemoSamples,
  listCandidates,
  previewCandidate,
} from "@/lib/demo-api";
import type { CandidateParseData, CandidateRecord } from "@/types/demo";

import styles from "./candidate-pool.module.css";


const sourceLabels: Record<CandidateRecord["data_origin"], string> = {
  synthetic_sandbox: "冻结 Synthetic 数据",
  user_created: "人工创建",
  mock_parsed: "Mock 结构化解析",
  llm_parsed: "LLM 结构化解析",
};

function safeError(error: unknown): string {
  if (!(error instanceof DemoApiError)) return "请求未完成，请检查本地服务后重试。";
  const messages: Record<string, string> = {
    provider_unavailable: "模型服务暂不可用。Mock 模式请加载中文 Resume 示例；自定义简历需要配置 Real Provider。",
    provider_timeout: "模型服务响应超时，请稍后重试。",
    provider_output_invalid: "模型返回的结构化档案未通过校验，请修改输入后重试。",
    mock_input_not_supported: "Mock 模式只接受已登记的安全示例；自定义简历请配置 Real Provider。",
    network_error: "无法连接后端，请确认本地服务已启动。",
  };
  return messages[error.code] ?? "请求未完成，请检查输入与本地服务后重试。";
}

export function CandidatePoolScreen() {
  const [candidates, setCandidates] = useState<CandidateRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [poolLoading, setPoolLoading] = useState(true);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [preview, setPreview] = useState<CandidateParseData | null>(null);
  const [busy, setBusy] = useState<"sample" | "preview" | "persist" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [indexedCount, setIndexedCount] = useState<number | null>(null);

  const loadPool = useCallback(async () => {
    try {
      const page = await listCandidates();
      setCandidates(page.items);
      setTotal(page.total);
      setPoolError(null);
    } catch (error) {
      setPoolError(safeError(error));
    } finally {
      setPoolLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    listCandidates().then((page) => {
      if (!active) return;
      setCandidates(page.items);
      setTotal(page.total);
      setPoolError(null);
    }).catch((error) => {
      if (active) setPoolError(safeError(error));
    }).finally(() => {
      if (active) setPoolLoading(false);
    });
    return () => { active = false; };
  }, []);

  const inputError = useMemo(() => {
    const length = resumeText.length;
    if (length > 0 && length < 40) return "候选人简历至少需要 40 个字符。";
    if (length > 5_000) return "候选人简历不能超过 5,000 个字符。";
    return null;
  }, [resumeText]);

  async function loadSample() {
    setBusy("sample"); setActionError(null); setSuccess(null);
    try {
      const samples = await fetchDemoSamples();
      setResumeText(samples.candidate_text);
      setPreview(null);
    } catch (error) {
      setActionError(safeError(error));
    } finally {
      setBusy(null);
    }
  }

  async function createPreview() {
    if (inputError || !resumeText.trim()) {
      setActionError(inputError ?? "请先填写候选人简历文本。");
      return;
    }
    setBusy("preview"); setActionError(null); setSuccess(null);
    try {
      setPreview(await previewCandidate(resumeText));
    } catch (error) {
      setActionError(safeError(error));
    } finally {
      setBusy(null);
    }
  }

  async function confirmCandidate() {
    if (!preview) return;
    setBusy("persist"); setActionError(null); setSuccess(null);
    try {
      const added = await addCandidateToPool(resumeText);
      setSuccess("候选人已加入人才库，将参与后续岗位 Retrieval 与 Ranking。");
      setIndexedCount(added.index.candidate_count);
      setPreview(null);
      await loadPool();
    } catch (error) {
      setActionError(safeError(error));
    } finally {
      setBusy(null);
    }
  }

  return <div className={layoutStyles.appShell}>
    <a className={layoutStyles.skipLink} href="#candidate-pool">跳转到人才库工作区</a>
    <AppSidebar active="candidates" />
    <main className={layoutStyles.mainSurface} id="candidate-pool">
      <div className={styles.contentFrame}>
        <header className={styles.hero}>
          <div><p className={styles.eyebrow}>Candidate Lifecycle · 人才库</p><h1>人才库管理</h1><p>Resume 先经过 Structured Profile Extraction，确认后加入 Candidate Pool；后续岗位 JD 推荐会自动从该人才库执行 Retrieval 与 Ranking。</p></div>
          <div className={styles.poolCount}><strong>{total} 位候选人</strong><span>Candidate Pool</span></div>
        </header>

        <section className={styles.ingestionPanel} aria-labelledby="candidate-ingestion-title">
          <div className={styles.sectionHeader}><div><p className={styles.eyebrow}>添加候选人</p><h2 id="candidate-ingestion-title">Resume → Structured Profile → Candidate Pool</h2><p>仅支持纯文本。Mock 模式使用登记的中文安全示例；自定义真实简历需要在本地配置 OpenAI-compatible Provider，且不应提交到 Git。</p></div><button className={styles.secondaryButton} type="button" disabled={busy !== null} onClick={loadSample}>加载中文 Resume 示例</button></div>
          <label className={styles.resumeField}>候选人简历文本<textarea aria-label="候选人简历文本" maxLength={5_000} value={resumeText} onChange={(event) => { setResumeText(event.target.value); setPreview(null); setSuccess(null); }} placeholder="粘贴中文简历，可包含 Python、RAG、Embedding、FastAPI 等英文技术词" /></label>
          <div className={styles.formFooter}><div>{inputError ? <span className={styles.validation}>{inputError}</span> : <span>解析阶段不会写入人才库；确认后才会持久化并刷新派生索引。</span>}</div><button className={styles.primaryButton} type="button" disabled={busy !== null} onClick={createPreview}>{busy === "preview" ? "正在解析…" : "解析候选人"}</button></div>
          {actionError ? <div className={styles.error} role="alert">{actionError}</div> : null}
          {success ? <div className={styles.success} role="status"><strong>{success}</strong>{indexedCount !== null ? <span>派生检索索引已刷新：{indexedCount} 位候选人</span> : null}</div> : null}
        </section>

        {preview ? <section className={styles.previewPanel} aria-labelledby="candidate-preview-title">
          <div className={styles.sectionHeader}><div><p className={styles.eyebrow}>确认前预览</p><h2 id="candidate-preview-title">Structured Profile 预览</h2></div><button className={styles.primaryButton} type="button" disabled={busy !== null} onClick={confirmCandidate}>{busy === "persist" ? "正在加入…" : "确认加入人才库"}</button></div>
          <div className={styles.previewGrid}><div><span>候选人</span><strong>{preview.draft.name}</strong></div><div><span>目标方向</span><strong>{preview.draft.target_roles.join(" / ")}</strong></div><div><span>资历</span><strong>{preview.draft.seniority}</strong></div><div><span>解析方式</span><strong>{preview.extraction.provider_kind === "mock" ? "Deterministic Mock" : "OpenAI-compatible Provider"}</strong></div></div>
          <div className={styles.profileColumns}><div><h3>核心技能</h3><div className={styles.tags}>{preview.draft.skills.map((skill) => <span key={`${skill.category}:${skill.name}`}>{skill.name}</span>)}</div></div><div><h3>项目经历</h3>{preview.draft.projects.map((project) => <article key={project.project_id}><strong>{project.name}</strong><p>{project.summary}</p><small>{project.technologies.join(" · ")}</small></article>)}</div></div>
          {preview.draft.missing_fields.length ? <p className={styles.missing}>待补充：{preview.draft.missing_fields.join("、")}</p> : null}
        </section> : null}

        <section className={styles.libraryPanel} aria-labelledby="candidate-list-title">
          <div className={styles.sectionHeader}><div><p className={styles.eyebrow}>Candidate Pool</p><h2 id="candidate-list-title">候选人列表</h2></div><p>展示层使用友好名称与方向；技术 ID 保留用于 MatchRun 与 Evidence 审计。</p></div>
          {poolLoading ? <div className={styles.emptyState}>正在读取人才库…</div> : poolError ? <div className={styles.error} role="alert">{poolError}</div> : candidates.length === 0 ? <div className={styles.emptyState}>人才库暂时为空</div> : <div className={styles.candidateGrid}>{candidates.map((candidate) => { const presentation = getCandidatePresentation(candidate.candidate_id, candidate); return <article className={styles.candidateCard} key={candidate.candidate_id}><div><p>{presentation.label}</p><h3>{presentation.direction}</h3></div><div className={styles.tags}>{candidate.skills.slice(0, 4).map((skill) => <span key={`${candidate.candidate_id}:${skill.name}`}>{skill.name}</span>)}</div><dl><div><dt>来源</dt><dd>{sourceLabels[candidate.data_origin]}</dd></div><div><dt>技术 ID</dt><dd><code>{candidate.candidate_id}</code></dd></div></dl></article>; })}</div>}
        </section>
      </div>
    </main>
  </div>;
}
