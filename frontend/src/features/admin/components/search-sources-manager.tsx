"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Reorder } from "motion/react";
import { ArrowDown, ArrowUp, CheckCircle2, Globe, GripVertical, KeyRound, Plus, Star, Trash2, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError, api } from "@/lib/api";

type SearchSourceType =
  | "openstreetmap"
  | "google_places"
  | "google_search"
  | "linkedin"
  | "facebook"
  | "instagram"
  | "x_twitter"
  | "reddit"
  | "custom";

interface SearchSourceItem {
  id: string;
  name: string;
  source_type: SearchSourceType;
  base_url: string;
  api_key_masked: string;
  has_api_key: boolean;
  extra_config: string;
  priority: number;
  is_active: boolean;
  is_primary: boolean;
}

interface SearchSourceListOut {
  items: SearchSourceItem[];
  total: number;
}

interface SearchSourceTestOut {
  ok: boolean;
  status_code: number | null;
  latency_ms: number;
  sample_count: number;
  error: string | null;
}

const SOURCE_PRESETS: Record<SearchSourceType, { name: string; baseUrl: string }> = {
  openstreetmap: {
    name: "OpenStreetMap (Free Live Places)",
    baseUrl: "https://nominatim.openstreetmap.org/search",
  },
  google_places: {
    name: "Google Places (Maps)",
    baseUrl: "https://places.googleapis.com/v1/places:searchText",
  },
  google_search: {
    name: "Google Search (Serper / CSE)",
    baseUrl: "https://google.serper.dev/search",
  },
  linkedin: {
    name: "LinkedIn",
    baseUrl: "https://google.serper.dev/search",
  },
  facebook: {
    name: "Facebook",
    baseUrl: "https://google.serper.dev/search",
  },
  instagram: {
    name: "Instagram",
    baseUrl: "https://google.serper.dev/search",
  },
  x_twitter: {
    name: "X (Twitter)",
    baseUrl: "https://google.serper.dev/search",
  },
  reddit: {
    name: "Reddit",
    baseUrl: "https://www.reddit.com/search.json",
  },
  custom: {
    name: "Custom Search Source",
    baseUrl: "https://",
  },
};

export function SearchSourcesManager() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "super_admin";

  const [sources, setSources] = useState<SearchSourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [editingKeyId, setEditingKeyId] = useState<string | null>(null);
  const [keyDraft, setKeyDraft] = useState("");
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const latestSourcesRef = useRef<SearchSourceItem[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [sourceType, setSourceType] = useState<SearchSourceType>("google_places");
  const [name, setName] = useState(SOURCE_PRESETS.google_places.name);
  const [baseUrl, setBaseUrl] = useState(SOURCE_PRESETS.google_places.baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [extraConfig, setExtraConfig] = useState("");
  const [priority, setPriority] = useState(2);

  const adminHeaders = { "X-Admin-Role": user?.role ?? "" };

  const loadSources = useCallback(async () => {
    if (!isSuperAdmin) {
      setLoading(false);
      return;
    }
    try {
      const res = await api.get<SearchSourceListOut>("/admin/search-sources", {
        headers: adminHeaders,
        suppressUnauthorizedRedirect: true,
      });
      setSources(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load search sources.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin, user?.role]);

  useEffect(() => {
    void Promise.resolve().then(() => loadSources());
  }, [loadSources]);

  async function handleSaveKey(id: string) {
    setError(null);
    setMessage(null);
    try {
      await api.put(
        `/admin/search-sources/${id}`,
        { api_key: keyDraft.trim() },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setEditingKeyId(null);
      setKeyDraft("");
      setMessage("API key updated and encrypted.");
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update API key.");
    }
  }

  async function handleToggleActive(item: SearchSourceItem) {
    setError(null);
    try {
      await api.put(
        `/admin/search-sources/${item.id}`,
        { is_active: !item.is_active },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not toggle search source.");
    }
  }

  async function handleSetPrimary(id: string) {
    setError(null);
    setMessage(null);
    try {
      const updated = await api.post<SearchSourceItem>(
        `/admin/search-sources/${id}/set-primary`,
        undefined,
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setMessage(`"${updated.name}" is now Primary search source (#1).`);
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not set primary source.");
    }
  }

  async function persistOrder(nextList: SearchSourceItem[]) {
    const reindexed = nextList.map((item, idx) => ({
      ...item,
      priority: idx + 1,
      is_primary: idx === 0,
    }));
    setSources(reindexed);
    try {
      const res = await api.post<SearchSourceListOut>(
        "/admin/search-sources/reorder",
        { ordered_ids: reindexed.map((item) => item.id) },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setSources(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save new priority order.");
      await loadSources();
    }
  }

  async function handleMove(index: number, delta: number) {
    const targetIndex = index + delta;
    if (targetIndex < 0 || targetIndex >= sources.length) return;
    const next = [...sources];
    const [moved] = next.splice(index, 1);
    next.splice(targetIndex, 0, moved);
    await persistOrder(next);
  }

  function handleReorder(nextList: SearchSourceItem[]) {
    const reindexed = nextList.map((item, idx) => ({
      ...item,
      priority: idx + 1,
      is_primary: idx === 0,
    }));
    latestSourcesRef.current = reindexed;
    setSources(reindexed);
  }

  async function handleDragEnd() {
    setDraggedId(null);
    if (latestSourcesRef.current.length > 0) {
      await persistOrder(latestSourcesRef.current);
    }
  }

  async function handleTest(item: SearchSourceItem) {
    setError(null);
    setMessage(null);
    setTestingId(item.id);
    try {
      const res = await api.post<SearchSourceTestOut>(
        `/admin/search-sources/${item.id}/test`,
        undefined,
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      if (res.ok) {
        setMessage(
          `Connection to "${item.name}" succeeded in ${res.latency_ms} ms (${res.sample_count} sample results).`,
        );
      } else {
        setError(`Test failed for "${item.name}": ${res.error ?? `HTTP ${res.status_code}`}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Test failed.");
    } finally {
      setTestingId(null);
    }
  }

  async function handleAdd(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setSaving(true);
    try {
      await api.post(
        "/admin/search-sources",
        {
          name: name.trim(),
          source_type: sourceType,
          base_url: baseUrl.trim(),
          api_key: apiKey.trim(),
          extra_config: extraConfig.trim(),
          priority: Number(priority),
          is_active: true,
          is_primary: false,
        },
        { headers: adminHeaders, suppressUnauthorizedRedirect: true },
      );
      setApiKey("");
      setExtraConfig("");
      setMessage(`Added search source "${name.trim()}".`);
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add search source.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/admin/search-sources/${id}`, {
        headers: adminHeaders,
        suppressUnauthorizedRedirect: true,
      });
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete source.");
    }
  }

  if (!isSuperAdmin) {
    return (
      <Card className="border-border/80 bg-card">
        <CardContent className="p-6 text-sm text-muted-foreground">
          Only Super Admin accounts can manage platform search sources.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">Search Sources & Priority</h1>
        <p className="text-sm text-muted-foreground">
          Enable or disable live lead discovery channels (Google Places, Google Search, LinkedIn, Facebook, Instagram, X, Reddit, OpenStreetMap), manage API keys, and control priority order.
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
            <Globe className="size-4 text-primary dark:text-lime-400" />
            Configured Search Sources
          </CardTitle>
          <CardDescription>
            Live Search runs active sources in priority order and merges discovered leads.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-xs text-muted-foreground">Loading search sources...</p>
          ) : (
            <Reorder.Group
              axis="y"
              values={sources}
              onReorder={handleReorder}
              className="space-y-3"
            >
              {sources.map((item, index) => {
                const isDragging = draggedId === item.id;
                return (
                  <Reorder.Item
                    key={item.id}
                    value={item}
                    layout
                    transition={{ type: "spring", stiffness: 420, damping: 32 }}
                    onDragStart={() => {
                      latestSourcesRef.current = sources;
                      setDraggedId(item.id);
                    }}
                    onDragEnd={() => {
                      void handleDragEnd();
                    }}
                    whileDrag={{
                      scale: 1.015,
                      zIndex: 50,
                    }}
                    className={`relative cursor-grab space-y-3 rounded-xl p-4 select-none active:cursor-grabbing ${
                      isDragging
                        ? "z-50 border-2 border-emerald-500 bg-card opacity-100 ring-2 ring-emerald-500/30 shadow-[0_12px_30px_rgba(16,185,129,0.28)] dark:border-lime-400 dark:bg-[#112014] dark:ring-lime-400/30 dark:shadow-[0_12px_30px_rgba(132,204,22,0.24)]"
                        : "border border-border/80 bg-surface/50 dark:border-[#223D27] dark:bg-[#0A140C]/60"
                    }`}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
                              {item.is_active ? "Enabled" : "Disabled"}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Type: <span className="font-mono">{item.source_type}</span> · Key:{" "}
                            <span className="font-mono">{item.api_key_masked}</span>
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
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingKeyId(editingKeyId === item.id ? null : item.id);
                            setKeyDraft("");
                          }}
                        >
                          <KeyRound className="mr-1 size-3.5" />
                          API Key
                        </Button>
                        {!item.is_primary && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleSetPrimary(item.id)}
                          >
                            <CheckCircle2 className="mr-1 size-3.5" />
                            Primary
                          </Button>
                        )}
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          disabled={index === 0}
                          onClick={() => void handleMove(index, -1)}
                        >
                          <ArrowUp className="size-4" />
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          disabled={index === sources.length - 1}
                          onClick={() => void handleMove(index, 1)}
                        >
                          <ArrowDown className="size-4" />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={item.is_active ? "secondary" : "default"}
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

                    {editingKeyId === item.id && (
                      <div
                        className="flex flex-wrap items-center gap-2 border-t border-border/70 pt-3"
                        onPointerDown={(e) => e.stopPropagation()}
                      >
                        <Input
                          type="password"
                          placeholder="Paste API Key (leave empty to clear)"
                          value={keyDraft}
                          onChange={(e) => setKeyDraft(e.target.value)}
                          className="max-w-md"
                        />
                        <Button type="button" size="sm" onClick={() => void handleSaveKey(item.id)}>
                          Save Key
                        </Button>
                      </div>
                    )}
                  </Reorder.Item>
                );
              })}
            </Reorder.Group>
          )}
        </CardContent>
      </Card>

      <Card className="border-border/80 bg-card">
        <CardHeader>
          <CardTitle className="text-base">Add Custom Search Source</CardTitle>
          <CardDescription>
            Add another search provider (Google Places, Serper/Google CSE, LinkedIn, Instagram, Facebook, X, Reddit).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="ss-type">Source Type</Label>
                <select
                  id="ss-type"
                  value={sourceType}
                  onChange={(e) => {
                    const t = e.target.value as SearchSourceType;
                    setSourceType(t);
                    setName(SOURCE_PRESETS[t].name);
                    setBaseUrl(SOURCE_PRESETS[t].baseUrl);
                  }}
                  className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                >
                  {(Object.keys(SOURCE_PRESETS) as SearchSourceType[]).map((k) => (
                    <option key={k} value={k}>
                      {SOURCE_PRESETS[k].name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ss-name">Display Name *</Label>
                <Input id="ss-name" required value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ss-priority">Priority</Label>
                <Input
                  id="ss-priority"
                  type="number"
                  min={1}
                  max={100}
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-1.5">
                <Label htmlFor="ss-url">Base URL</Label>
                <Input id="ss-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ss-key">API Key (if required)</Label>
                <Input
                  id="ss-key"
                  type="password"
                  placeholder="Optional for OpenStreetMap / Reddit"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="ss-extra">Extra Config (e.g. Google CSE cx)</Label>
                <Input
                  id="ss-extra"
                  value={extraConfig}
                  onChange={(e) => setExtraConfig(e.target.value)}
                />
              </div>
            </div>

            <Button type="submit" disabled={saving}>
              <Plus className="mr-1.5 size-4" />
              {saving ? "Adding..." : "Add Search Source"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
