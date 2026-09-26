import { BackendReleaseReview } from "../../../components/BackendReleaseReview";

export default async function SessionPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  return <BackendReleaseReview sessionId={sessionId} />;
}
