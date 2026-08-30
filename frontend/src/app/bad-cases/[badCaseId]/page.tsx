import { BadCaseDetailScreen } from "@/features/phase10/bad-case-detail-screen";
import { ReviewShell } from "@/features/phase10/review-shell";


export default async function BadCaseDetailPage({ params }: { params: Promise<{ badCaseId: string }> }) {
  const { badCaseId } = await params;
  return <ReviewShell detail><BadCaseDetailScreen badCaseId={badCaseId} /></ReviewShell>;
}
