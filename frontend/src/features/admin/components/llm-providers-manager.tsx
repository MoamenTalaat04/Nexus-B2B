"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Reorder } from "motion/react";
import { ArrowDown, ArrowUp, CheckCircle2, Cpu, GripVertical, Pencil, Plus, Star, Trash2, X, Zap } from "lucide-react";
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
  model_checked?: string | null;
  reply_preview?: string | null;
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
    modelSmart: "qwen",
    modelFast: "qwen",
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
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const latestProvidersRef = useRef<LlmProviderItem[]>([]);
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

  const [editingItem, setEditingItem] = useState<LlmProviderItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editBaseUrl, setEditBaseUrl] = useState("");
  const [editApiKey, setEditApiKey] = useState("");
  const [editModelSmart, setEditModelSmart] = useState("");
  const [editModelFast, setEditModelFast] = useState("");
  const [editSaving, setEditSaving] = useState(false);

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
          model_fast: modelFast.trim() || modelSmart.trim(),
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

  async function persistOrder(nextList: LlmProviderItem[]) {
    const reindexed = nextList.map((item, idx) => ({
      ...item,
      priority: idx + 1,
      is_primary: idx === 0,
    }));
    setProviders(reindexed);
    try {
      const res = await api.post<LlmProviderListOut>(
        "/admin/llm-providers/reorder",
        { ordered_ids: reindexed.map((item) => item.id) },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setProviders(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save new priority order.");
      await loadProviders();
    }
  }

  async function handleMove(index: number, delta: number) {
    const targetIndex = index + delta;
    if (targetIndex < 0 || targetIndex >= providers.length) return;
    const next = [...providers];
    const [moved] = next.splice(index, 1);
    next.splice(targetIndex, 0, moved);
    await persistOrder(next);
  }

  function handleReorder(nextList: LlmProviderItem[]) {
    const reindexed = nextList.map((item, idx) => ({
      ...item,
      priority: idx + 1,
      is_primary: idx === 0,
    }));
    latestProvidersRef.current = reindexed;
    setProviders(reindexed);
  }

  async function handleDragEnd() {
    setDraggedId(null);
    if (latestProvidersRef.current.length > 0) {
      await persistOrder(latestProvidersRef.current);
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
        const replyNote = res.reply_preview ? ` · ${res.model_checked ?? item.model_smart} replied: "${res.reply_preview}"` : "";
        setMessage(
          `Connection to "${item.name}" succeeded in ${res.latency_ms} ms (${res.models_count} models)${replyNote}.`,
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

  function openEditModal(item: LlmProviderItem) {
    setEditingItem(item);
    setEditName(item.name);
    setEditBaseUrl(item.base_url);
    setEditApiKey("");
    setEditModelSmart(item.model_smart);
    setEditModelFast(item.model_fast);
    setError(null);
    setMessage(null);
  }

  async function handleSaveEdit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editingItem) return;
    setEditSaving(true);
    setError(null);
    try {
      const payload: Record<string, string> = {
        name: editName.trim(),
        base_url: editBaseUrl.trim(),
        model_smart: editModelSmart.trim(),
        model_fast: editModelFast.trim() || editModelSmart.trim(),
      };
      if (editApiKey.trim()) {
        payload.api_key = editApiKey.trim();
      }
      await api.put(`/admin/llm-providers/${editingItem.id}`, payload, {
        headers: adminHeaders,
        suppressUnauthorizedRedirect: true,
      });
      setMessage(`Updated provider "${editName.trim()}".`);
      setEditingItem(null);
      await loadProviders();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update provider.");
    } finally {
      setEditSaving(false);
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
            <Reorder.Group
              axis="y"
              values={providers}
              onReorder={handleReorder}
              className="space-y-3"
            >
              {providers.map((item, index) => {
                const isDragging = draggedId === item.id;
                return (
                  <Reorder.Item
                    key={item.id}
                    value={item}
                    layout
                    transition={{ type: "spring", stiffness: 420, damping: 32 }}
                    onDragStart={() => {
                      latestProvidersRef.current = providers;
                      setDraggedId(item.id);
                    }}
                    onDragEnd={() => {
                      void handleDragEnd();
                    }}
                    whileDrag={{
                      scale: 1.015,
                      zIndex: 50,
                    }}
                    className={`relative flex cursor-grab flex-col gap-3 rounded-xl p-4 select-none active:cursor-grabbing sm:flex-row sm:items-center sm:justify-between ${isDragging
                      ? "z-50 border-2 border-emerald-500 bg-card opacity-100 ring-2 ring-emerald-500/30 shadow-[0_12px_30px_rgba(16,185,129,0.28)] dark:border-lime-400 dark:bg-[#112014] dark:ring-lime-400/30 dark:shadow-[0_12px_30px_rgba(132,204,22,0.24)]"
                      : "border border-border/80 bg-surface/50 dark:border-[#223D27] dark:bg-[#0A140C]/60"
                      }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <span
                        title="Drag to reorder"
                        className="mt-1 text-muted-foreground hover:text-foreground"
                      >
                        <GripVertical className="size-4" />
                      </span>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">{item.name}</span>
                          <Badge variant="outline">Priority #{index + 1}</Badge>
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
                    </div>

                    <div
                      className="flex flex-wrap items-center gap-1.5"
                      onPointerDown={(e) => e.stopPropagation()}
                    >
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
                        disabled={index === 0}
                        onClick={() => void handleMove(index, -1)}
                      >
                        <ArrowUp className="size-4" />
                      </Button>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        title="Lower priority"
                        disabled={index === providers.length - 1}
                        onClick={() => void handleMove(index, 1)}
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
                        title="Edit provider"
                        onClick={() => openEditModal(item)}
                      >
                        <Pencil className="size-4" />
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
                  </Reorder.Item>
                );
              })}
            </Reorder.Group>
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
                <Label htmlFor="llm-smart">Model Identifier (Smart) *</Label>
                <Input
                  id="llm-smart"
                  required
                  placeholder="e.g. qwen or gpt-4o"
                  value={modelSmart}
                  onChange={(e) => setModelSmart(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="llm-fast">Fast Model (optional)</Label>
                <Input
                  id="llm-fast"
                  placeholder="Defaults to Smart model"
                  value={modelFast}
                  onChange={(e) => setModelFast(e.target.value)}
                />
              </div>
            </div>

            {(providerType === "colab_vllm" || providerType === "custom") && (
              <p className="rounded-lg border border-border/70 bg-surface/50 px-3 py-2 text-xs text-muted-foreground dark:border-[#223D27] dark:bg-[#0A140C]/60">
                Uses non-streaming OpenAI-compatible Chat Completions (<code className="font-mono">stream: false</code>).
                Temporary Cloudflare Quick Tunnel URLs expire when a Colab session restarts — use Edit on the provider card
                to paste the new URL.
              </p>
            )}

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

      {editingItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setEditingItem(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border border-border bg-card p-5 shadow-2xl dark:border-[#223D27] dark:bg-[#112014]"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Edit Provider: {editingItem.name}</h3>
              <Button type="button" size="icon-sm" variant="ghost" onClick={() => setEditingItem(null)}>
                <X className="size-4" />
              </Button>
            </div>
            <form onSubmit={handleSaveEdit} className="space-y-3">
              <div className="grid gap-1.5">
                <Label htmlFor="edit-llm-name">Display Name *</Label>
                <Input
                  id="edit-llm-name"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="edit-llm-url">Base URL *</Label>
                <Input
                  id="edit-llm-url"
                  required
                  value={editBaseUrl}
                  onChange={(e) => setEditBaseUrl(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="edit-llm-key">New API Key (leave blank to keep existing)</Label>
                <Input
                  id="edit-llm-key"
                  type="password"
                  placeholder={editingItem.api_key_masked}
                  value={editApiKey}
                  onChange={(e) => setEditApiKey(e.target.value)}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="edit-llm-smart">Model Identifier (Smart) *</Label>
                  <Input
                    id="edit-llm-smart"
                    required
                    value={editModelSmart}
                    onChange={(e) => setEditModelSmart(e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="edit-llm-fast">Fast Model</Label>
                  <Input
                    id="edit-llm-fast"
                    value={editModelFast}
                    onChange={(e) => setEditModelFast(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setEditingItem(null)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={editSaving}>
                  {editSaving ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
