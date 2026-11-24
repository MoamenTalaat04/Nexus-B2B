import { ActivityDetail } from "@/features/activity/components/activity-detail";

export default async function ActivityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ActivityDetail runId={id} />;
}
