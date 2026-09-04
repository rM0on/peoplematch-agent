import { describe, expect, it } from "vitest";

import { candidateDisplayCatalog, getCandidatePresentation } from "./candidate-display-metadata";


describe("candidate display metadata", () => {
  it("covers the frozen 48-person pool without changing profile data", () => {
    const ids = Array.from({ length: 48 }, (_, index) => `cand_${String(index + 1).padStart(3, "0")}`);

    expect(Object.keys(candidateDisplayCatalog).sort()).toEqual(ids);
    expect(new Set(Object.values(candidateDisplayCatalog).map((item) => item.label)).size).toBe(48);
    for (const candidateId of ids) {
      const presentation = getCandidatePresentation(candidateId);
      expect(presentation.label).toMatch(/^候选人 \d{3}$/);
      expect(presentation.direction).toMatch(/方向$/);
      expect(presentation.strengths.length).toBeGreaterThanOrEqual(2);
      expect(presentation.strengths.every((item) => item.length > 0)).toBe(true);
    }
  });

  it("keeps presentation directions aligned with the frozen candidate archetype ranges", () => {
    expect(getCandidatePresentation("cand_013").direction).toBe("AI 产品工程方向");
    expect(getCandidatePresentation("cand_017").direction).toBe("RAG 与搜索算法方向");
    expect(getCandidatePresentation("cand_021").direction).toBe("NLP 模型算法方向");
    expect(getCandidatePresentation("cand_025").direction).toBe("AI 安全工程方向");
    expect(getCandidatePresentation("cand_029").direction).toBe("后端 AI 工程方向");
    expect(getCandidatePresentation("cand_033").direction).toBe("数据算法与数据工程方向");
    expect(getCandidatePresentation("cand_037").direction).toBe("前端 AI 产品工程方向");
  });

  it("uses the parsed draft only for unknown runtime candidate presentation", () => {
    const presentation = getCandidatePresentation("cand_parse_runtime", {
      name: "中文演示候选人",
      target_roles: ["推荐算法工程师"],
      skills: [{ name: "Python" }, { name: "RAG" }],
    });

    expect(presentation).toEqual({
      label: "中文演示候选人",
      direction: "推荐算法工程师方向",
      strengths: ["Python", "RAG"],
    });
    expect(candidateDisplayCatalog).not.toHaveProperty("cand_parse_runtime");
  });
});
