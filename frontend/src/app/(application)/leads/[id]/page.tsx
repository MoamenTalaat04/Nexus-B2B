"use client";

import { useParams } from "next/navigation";

export default function LeadDetailsPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-1">
      <h1 className="text-xl font-bold tracking-tight text-foreground">Lead Details</h1>
      <p className="text-sm text-muted-foreground">ID: {id}</p>
    </div>
  );
}

