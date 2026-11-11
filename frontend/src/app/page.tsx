import { HealthStatus } from "@/components/system/HealthStatus";

// Placeholder landing page. P0-4 replaces it with the auth flow and the app shell.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-6 py-16">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">AI SDR</h1>
        <p className="text-muted-foreground">
          The B2B lead-generation agent. This is the scaffold page; the app shell arrives in P0-4.
        </p>
      </div>
      <HealthStatus />
    </main>
  );
}
