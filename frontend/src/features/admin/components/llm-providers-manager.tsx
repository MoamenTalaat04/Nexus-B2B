"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, Cpu, Plus, Star, Trash2, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError, api } from "@/lib/api";

type ProviderType = "groq" | "openai" | "gemini" | "colab_vllm" | "custom";

interface LlmProviderItem {
  id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key_masked: string;
  model_smart: string;
  model_fast: string;
  reasoning_models: string;
  priority: number;
  is_active: boolean;
  is_primary: boolean;
}

interface LlmProviderListOut {
  items: LlmProviderItem[];
  total: number;
  env_fallback_model_smart: string;
  env_fallback_base_url: string;
}

interface LlmProviderTestOut {
  ok: boolean;
  status_code: number | null;
  latency_ms: number;
  models_count: number;
  error: string | null;
}

const PRESETS: Record<
  ProviderType,
  { name: string; baseUrl: string; modelSmart: string; modelFast: string }
> = {
  groq: {
    name: "Groq Cloud",
    baseUrl: "https://api.groq.com/openai/v1",
    modelSmart: "openai/gpt-oss-120b",
    modelFast: "openai/gpt-oss-20b",
  },
  openai: {
    name: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    modelSmart: "gpt-4o",
    modelFast: "gpt-4o-mini",
  },
  gemini: {
    name: "Google Gemini (OpenAI-Compat)",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai/",
    modelSmart: "gemini-2.5-flash",
    modelFast: "gemini-2.5-flash",
  },
  colab_vllm: {
    name: "Google Colab (Qwen vLLM)",
    baseUrl: "https://your-tunnel.trycloudflare.com/v1",
    modelSmart: "Qwen/Qwen2.5-14B-Instruct-AWQ",
    modelFast: "Qwen/Qwen2.5-14B-Instruct-AWQ",
  },
  custom: {
    name: "Custom OpenAI-Compatible",
    baseUrl: "https://",
    modelSmart: "",
    modelFast: "",
  },
};

export function LlmProvidersManager() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "super_admin";

  const [providers, setProviders] = useState<LlmProviderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [providerType, setProviderType] = useState<ProviderType>("groq");
  const [name, setName] = useState(PRESETS.groq.name);
  const [baseUrl, setBaseUrl] = useState(PRESETS.groq.baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [modelSmart, setModelSmart] = useState(PRESETS.groq.modelSmart);
  const [modelFast, setModelFast] = useState(PRESETS.groq.modelFast);
  const [priority, setPriority] = useState(2);
  const [isPrimary, setIsPrimary] = useState(false);

  const adminHeaders = { "X-Admin-Role": user?.role ?? "" };

  const loadProviders = useCallback(async () => {
    if (!isSuperAdmin) {
      setLoading(false);
      return;
    }
    try {
      const res = await api.get<LlmProviderListOut>("/admin/llm-providers", {
        headers: adminHeaders,
        suppressUnauthorizedRedirect: true,
      });
      setProviders(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load LLM providers.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin, user?.role]);

  useEffect(() => {
    void Promise.resolve().then(() => loadProviders());
  }, [loadProviders]);

  function applyPreset(nextType: ProviderType) {
    setProviderType(nextType);
    const preset = PRESETS[nextType];
    setName(preset.name);
    setBaseUrl(preset.baseUrl);
    setModelSmart(preset.modelSmart);
    setModelFast(preset.modelFast);
  }

  async function handleAddProvider(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      await api.post<LlmProviderItem>(
        "/admin/llm-providers",
        {
          name: name.trim(),
          provider_type: providerType,
          base_url: baseUrl.trim(),
          api_key: apiKey.trim(),
          model_smart: modelSmart.trim(),
          model_fast: modelFast.trim(),
          priority: Number(priority),
          is_active: true,
          is_primary: isPrimary,
        },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setApiKey("");
      setMessage(`Added LLM provider "${name.trim()}".`);
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create LLM provider.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSetPrimary(id: string) {
    setError(null);
    setMessage(null);
    try {
      const updated = await api.post<LlmProviderItem>(
        `/admin/llm-providers/${id}/set-primary`,
        undefined,
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setMessage(`"${updated.name}" is now the Primary LLM provider.`);
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not set primary provider.");
    }
  }

  async function handleToggleActive(item: LlmProviderItem) {
    setError(null);
    try {
      await api.put(
        `/admin/llm-providers/${item.id}`,
        { is_active: !item.is_active },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update provider.");
    }
  }

  async function handleChangePriority(item: LlmProviderItem, delta: number) {
    const nextPriority = Math.max(1, item.priority + delta);
    try {
      await api.put(
        `/admin/llm-providers/${item.id}`,
        { priority: nextPriority },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update priority.");
    }
  }

  async function handleTest(item: LlmProviderItem) {
    setError(null);
    setMessage(null);
    setTestingId(item.id);
    try {
      const res = await api.post<LlmProviderTestOut>(
        `/admin/llm-providers/${item.id}/test`,
        undefined,
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      if (res.ok) {
        setMessage(
          `Connection to "${item.name}" succeeded in ${res.latency_ms} ms (${res.models_count} models available).`,
        );
      } else {
        setError(`Connection to "${item.name}" failed: ${res.error ?? `HTTP ${res.status_code}`}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Test request failed.");
    } finally {
      setTestingId(null);
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    setMessage(null);
    try {
      await api.delete(`/admin/llm-providers/${id}`, {
        headers: adminHeaders,
        suppressUnauthorizedRedirect: true,
      });
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete provider.");
    }
  }

  if (!isSuperAdmin) {
    return (
      <Card className="border-border/80 bg-card">
        <CardContent className="p-6 text-sm text-muted-foreground">
          Only Super Admin accounts can view and manage platform LLM providers.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">LLM Providers & Priority</h1>
        <p className="text-sm text-muted-foreground">
          Configure AI providers (Groq, OpenAI, Gemini, Google Colab vLLM), manage encrypted API keys, and set primary/fallback priority without editing .env.
        </p>
      </div>

      {message && (
        <p className="rounded-lg border border-lime-500/30 bg-lime-50 px-3 py-2 text-xs text-lime-800 dark:bg-lime-950/60 dark:text-lime-200">
          {message}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Cpu className="size-4 text-primary dark:text-lime-400" />
            Configured Providers (Ordered by Priority)
          </CardTitle>
          <CardDescription>
            Agents always call the Primary active provider first and automatically fall back in priority order.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-xs text-muted-foreground">Loading providers...</p>
          ) : providers.length === 0 ? (
            <p className="text-xs text-muted-foreground">No providers configured yet.</p>
          ) : (
            providers.map((item) => (
              <div
                key={item.id}
                className="flex flex-col gap-3 rounded-xl border border-border/80 bg-surface/50 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-[#223D27] dark:bg-[#0A140C]/60"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-foreground">{item.name}</span>
                    <Badge variant="outline">Priority #{item.priority}</Badge>
                    {item.is_primary && (
                      <Badge className="bg-gradient-to-r from-[#10B981] to-[#84CC16] text-[#0A140C]">
                        <Star className="mr-1 size-3" />
                        Primary
                      </Badge>
                    )}
                    <Badge variant={item.is_active ? "default" : "secondary"}>
                      {item.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    URL: <span className="font-mono">{item.base_url}</span> · Key:{" "}
                    <span className="font-mono">{item.api_key_masked}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Smart: <span className="font-mono text-foreground">{item.model_smart}</span> · Fast:{" "}
                    <span className="font-mono text-foreground">{item.model_fast}</span>
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={testingId === item.id}
                    onClick={() => void handleTest(item)}
                  >
                    <Zap className="mr-1 size-3.5" />
                    {testingId === item.id ? "Testing..." : "Test"}
                  </Button>
                  {!item.is_primary && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void handleSetPrimary(item.id)}
                    >
                      <CheckCircle2 className="mr-1 size-3.5" />
                      Set Primary
                    </Button>
                  )}
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Higher priority"
                    onClick={() => void handleChangePriority(item, -1)}
                  >
                    <ArrowUp className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Lower priority"
                    onClick={() => void handleChangePriority(item, 1)}
                  >
                    <ArrowDown className="size-4" />
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleToggleActive(item)}
                  >
                    {item.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => void handleDelete(item.id)}
                    className="text-muted-foreground hover:text-red-600"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Add New LLM Provider</CardTitle>
          <CardDescription>
            Choose a preset (Groq, OpenAI, Gemini, Google Colab vLLM) or enter any OpenAI-compatible endpoint.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddProvider} className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {(Object.keys(PRESETS) as ProviderType[]).map((key) => (
                <Button
                  key={key}
                  type="button"
                  size="sm"
                  variant={providerType === key ? "default" : "outline"}
                  onClick={() => applyPreset(key)}
                >
                  {PRESETS[key].name}
                </Button>
              ))}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="llm-name">Display Name *</Label>
                <Input
                  id="llm-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="llm-base-url">Base URL *</Label>
                <Input
                  id="llm-base-url"
                  required
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="llm-api-key">API Key *</Label>
                <Input
                  id="llm-api-key"
                  type="password"
                  required
                  placeholder="gsk_... or sk-..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="llm-smart">Smart Model *</Label>
                <Input
                  id="llm-smart"
                  required
                  value={modelSmart}
                  onChange={(e) => setModelSmart(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="llm-fast">Fast Model *</Label>
                <Input
                  id="llm-fast"
                  required
                  value={modelFast}
                  onChange={(e) => setModelFast(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <div className="grid w-32 gap-1.5">
                <Label htmlFor="llm-priority">Priority</Label>
                <Input
                  id="llm-priority"
                  type="number"
                  min={1}
                  max={100}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                />
              </div>
              <label className="mt-5 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isPrimary}
                  onChange={(e) => setIsPrimary(e.target.checked)}
                  className="size-4 accent-primary"
                />
                Set as Primary Provider immediately
              </label>
            </div>

            <Button type="submit" disabled={saving}>
              <Plus className="mr-1.5 size-4" />
              {saving ? "Saving..." : "Add Provider"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
