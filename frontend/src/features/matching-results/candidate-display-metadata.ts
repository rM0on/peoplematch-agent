type CandidatePresentation = {
  label: string;
  direction: string;
  strengths: readonly string[];
};

type RuntimeCandidatePresentationSource = {
  name: string;
  target_roles: readonly string[];
  skills: ReadonlyArray<{ name: string }>;
};

type PresentationGroup = {
  from: number;
  to: number;
  direction: string;
  strengths: readonly [string, string, ...string[]];
};

const groups: readonly PresentationGroup[] = [
  { from: 1, to: 4, direction: "LLM 应用与 Agent 工程方向", strengths: ["LLM 应用工程", "Agent 工作流设计"] },
  { from: 5, to: 8, direction: "推荐算法工程方向", strengths: ["Learning To Rank 建模", "Hybrid Retrieval 实践"] },
  { from: 9, to: 12, direction: "机器学习平台与 MLOps 方向", strengths: ["模型工程化", "训练与服务基础设施"] },
  { from: 13, to: 16, direction: "AI 产品工程方向", strengths: ["AI 功能交付", "跨团队产品协作"] },
  { from: 17, to: 20, direction: "RAG 与搜索算法方向", strengths: ["Embedding 检索", "RAG 检索链路"] },
  { from: 21, to: 24, direction: "NLP 模型算法方向", strengths: ["自然语言处理", "模型实验能力"] },
  { from: 25, to: 28, direction: "AI 安全工程方向", strengths: ["模型安全意识", "风险与权限治理"] },
  { from: 29, to: 32, direction: "后端 AI 工程方向", strengths: ["分布式后端", "AI 服务工程化"] },
  { from: 33, to: 36, direction: "数据算法与数据工程方向", strengths: ["数据管道建设", "数据质量治理"] },
  { from: 37, to: 40, direction: "前端 AI 产品工程方向", strengths: ["AI 产品交互", "前端工程能力"] },
  { from: 41, to: 44, direction: "算法项目实践方向", strengths: ["完整项目证据", "较强学习与落地能力"] },
  { from: 45, to: 48, direction: "候选资料待核验方向", strengths: ["技能声明覆盖较广", "建议重点核验项目证据"] },
];

export const candidateDisplayCatalog: Readonly<Record<string, CandidatePresentation>> = Object.freeze(
  Object.fromEntries(groups.flatMap((group) => Array.from(
    { length: group.to - group.from + 1 },
    (_, offset) => {
      const candidateNumber = group.from + offset;
      const padded = String(candidateNumber).padStart(3, "0");
      return [`cand_${padded}`, {
        label: `候选人 ${padded}`,
        direction: group.direction,
        strengths: group.strengths,
      } satisfies CandidatePresentation];
    },
  ))),
);

export function getCandidatePresentation(
  candidateId: string,
  runtimeCandidate?: RuntimeCandidatePresentationSource,
): CandidatePresentation {
  const frozenPresentation = candidateDisplayCatalog[candidateId];
  if (frozenPresentation) return frozenPresentation;

  const targetRole = runtimeCandidate?.target_roles[0]?.trim();
  const strengths = runtimeCandidate?.skills
    .map((skill) => skill.name.trim())
    .filter(Boolean)
    .slice(0, 3) ?? [];
  return {
    label: runtimeCandidate?.name.trim() || "人才库候选人",
    direction: targetRole ? `${targetRole}方向` : "候选方向待确认",
    strengths: strengths.length ? strengths : ["已完成结构化解析", "等待项目证据复核"],
  };
}

export type { CandidatePresentation };
