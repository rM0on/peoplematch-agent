import { Suspense } from "react";
import { RequirementReviewScreen } from "@/features/requirement-review/requirement-review-screen";

export default function RequirementReviewPage() { return <Suspense fallback={<p>正在读取岗位要求…</p>}><RequirementReviewScreen /></Suspense>; }
