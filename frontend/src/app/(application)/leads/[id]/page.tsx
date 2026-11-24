"use client";

import { useParams } from "next/navigation";
import { LeadDetailWorkspace } from "@/features/leads/components/lead-detail-workspace";

export default function LeadDetailsPage() {
  const { id } = useParams<{ id: string }>();
  return <LeadDetailWorkspace leadId={id} />;
}
