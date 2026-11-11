import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthStatus } from "./HealthStatus";

function renderWithQuery() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HealthStatus />
    </QueryClientProvider>,
  );
}

describe("HealthStatus", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the backend status from /api/v1/health", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", db: "ok", redis: "ok" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithQuery();

    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health");
  });

  it("explains how to start the backend when it is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    renderWithQuery();

    expect(await screen.findByText(/Backend unreachable/)).toBeInTheDocument();
  });
});
