"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type DragEvent } from "react";
import { createPortal } from "react-dom";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileText,
  Loader2,
  Pencil,
  Save,
  Trash2,
  UploadCloud,
  Wand2,
  X,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ApiError, api } from "@/lib/api";
import type { KnowledgeFileListOut, KnowledgeFileOut } from "@/lib/settings-types";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = ".pdf,.md,.txt,.docx";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

type KnowledgeDocType = "catalog" | "pricing" | "faq" | "case_studies";

const RECOMMENDED_DOCS: Array<{
  type: KnowledgeDocType;
  title: string;
  hint: string;
  matchKeywords: string[];
}> = [
  {
    type: "catalog",
    title: "Product / Service Catalog",
    hint: "Offerings, specs, features, or service deliverables",
    matchKeywords: ["catalog", "catalogue", "product", "service", "brochure", "offer"],
  },
  {
    type: "pricing",
    title: "Price List & Packages",
    hint: "Pricing tiers, MOQs, retainers, or payment terms",
    matchKeywords: ["price", "pricing", "package", "rate", "quote"],
  },
  {
    type: "faq",
    title: "FAQs & Objection Handling",
    hint: "Common buyer questions, delivery, SLA, and policies",
    matchKeywords: ["faq", "question", "objection", "policy", "support"],
  },
  {
    type: "case_studies",
    title: "Case Studies / Portfolio",
    hint: "Client results, testimonials, or past projects",
    matchKeywords: ["case", "portfolio", "client", "testimonial", "study"],
  },
];

export interface KnowledgeAiContext {
  companyName: string;
  website: string;
  description: string;
  idealCustomerText: string;
}

interface KnowledgeFileDetailOut extends KnowledgeFileOut {
  content: string;
  editable: boolean;
}

export function KnowledgeUploader({
  onCountChange,
  aiContext,
  aiQuota,
  onQuotaRefresh,
}: {
  onCountChange?: (count: number) => void;
  aiContext?: KnowledgeAiContext;
  aiQuota?: Record<string, number>;
  onQuotaRefresh?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<KnowledgeFileOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [generatingDoc, setGeneratingDoc] = useState<KnowledgeDocType | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [modalFile, setModalFile] = useState<KnowledgeFileDetailOut | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalSaving, setModalSaving] = useState(false);
  const [modalDraft, setModalDraft] = useState("");
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalSaved, setModalSaved] = useState(false);
  const [pageSize, setPageSize] = useState<number>(10);
  const [page, setPage] = useState<number>(1);
  const isClient = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  useEffect(() => {
    let active = true;
    api
      .get<KnowledgeFileListOut>("/knowledge", {
        suppressUnauthorizedRedirect: true,
      })
      .then((res) => {
        if (!active) return;
        setFiles(res.items);
        onCountChange?.(res.total);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && err.status !== 401) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [onCountChange]);

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      for (const file of Array.from(fileList)) {
        const formData = new FormData();
        formData.append("file", file);
        const uploaded = await api.upload<KnowledgeFileOut>("/knowledge", formData, {
          suppressUnauthorizedRedirect: true,
        });
        setFiles((prev) => {
          const next = [uploaded, ...prev];
          onCountChange?.(next.length);
          return next;
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to upload knowledge file.");
    } finally {
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  async function handleDelete(fileId: string) {
    setError(null);
    try {
      await api.delete(`/knowledge/${fileId}`, { suppressUnauthorizedRedirect: true });
      setFiles((prev) => {
        const next = prev.filter((item) => item.id !== fileId);
        onCountChange?.(next.length);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete file.");
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    void handleFiles(e.dataTransfer.files);
  }

  async function handleGenerateDoc(docType: KnowledgeDocType) {
    if (!aiContext?.website.trim()) {
      setError("Add your website URL in Step 1 first so AI can generate this document.");
      return;
    }
    setError(null);
    setGeneratingDoc(docType);
    try {
      const created = await api.post<KnowledgeFileOut>(
        "/knowledge/ai-generate",
        {
          doc_type: docType,
          company_name: aiContext.companyName.trim(),
          website: aiContext.website.trim(),
          description: aiContext.description.trim(),
          ideal_customer_text: aiContext.idealCustomerText.trim(),
        },
        { suppressUnauthorizedRedirect: true },
      );
      setFiles((prev) => {
        const next = [created, ...prev];
        onCountChange?.(next.length);
        return next;
      });
      onQuotaRefresh?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate knowledge document.");
    } finally {
      setGeneratingDoc(null);
    }
  }

  async function openFileModal(file: KnowledgeFileOut) {
    setModalError(null);
    setModalSaved(false);
    setModalLoading(true);
    setModalFile({
      ...file,
      content: "",
      editable: /\.(md|txt)$/i.test(file.filename),
    });
    try {
      const detail = await api.get<KnowledgeFileDetailOut>(`/knowledge/${file.id}`, {
        suppressUnauthorizedRedirect: true,
      });
      setModalFile(detail);
      setModalDraft(detail.content);
    } catch (err) {
      setModalError(err instanceof ApiError ? err.message : "Could not load file content.");
    } finally {
      setModalLoading(false);
    }
  }

  async function saveModalContent() {
    if (!modalFile || !modalFile.editable) return;
    setModalError(null);
    setModalSaved(false);
    setModalSaving(true);
    try {
      const updated = await api.put<KnowledgeFileDetailOut>(
        `/knowledge/${modalFile.id}`,
        { content: modalDraft },
        { suppressUnauthorizedRedirect: true },
      );
      setModalFile(updated);
      setModalDraft(updated.content);
      setModalSaved(true);
      setFiles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setModalError(err instanceof ApiError ? err.message : "Could not save file changes.");
    } finally {
      setModalSaving(false);
    }
  }

  useEffect(() => {
    if (!modalFile) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalFile(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [modalFile]);

  const hasWebsite = Boolean(aiContext?.website.trim());

  return (
    <div className="space-y-4">
      {aiContext && (
        <div className="space-y-2 rounded-xl border border-border/80 bg-surface/40 p-3.5 dark:border-[#223D27] dark:bg-[#0A140C]/50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-foreground">Recommended Knowledge Checklist</p>
            <span className="text-[11px] text-muted-foreground">
              {hasWebsite
                ? "Upload your files or generate drafts from your website"
                : "Recommended files to upload (add a website in Step 1 to auto-generate)"}
            </span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {RECOMMENDED_DOCS.map((item) => {
              const covered = files.some((file) =>
                item.matchKeywords.some((kw) => file.filename.toLowerCase().includes(kw)),
              );
              const isBusy = generatingDoc === item.type;
              return (
                <div
                  key={item.type}
                  className={cn(
                    "flex items-center justify-between gap-2.5 rounded-lg border px-3 py-2 transition-colors",
                    covered
                      ? "border-emerald-500/40 bg-emerald-500/10 dark:border-lime-400/35 dark:bg-lime-500/10"
                      : "border-border/70 bg-card/70 dark:border-[#223D27] dark:bg-[#112014]/70",
                  )}
                >
                  <div className="flex min-w-0 items-start gap-2">
                    <span
                      className={cn(
                        "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border text-[10px]",
                        covered
                          ? "border-emerald-500 bg-emerald-500 text-white dark:border-lime-400 dark:bg-lime-400 dark:text-[#0A140C]"
                          : "border-border text-transparent dark:border-[#2d4d33]",
                      )}
                    >
                      <Check className="size-2.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-foreground">{item.title}</p>
                      <p className="truncate text-[11px] text-muted-foreground">{item.hint}</p>
                    </div>
                  </div>

                  <TooltipProvider delay={150}>
                    {(() => {
                      const remaining = aiQuota?.[`knowledge_${item.type}`] ?? 3;
                      const exhausted = remaining <= 0;
                      return (
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span
                            className={cn(
                              "text-[10px] font-semibold tabular-nums",
                              exhausted ? "text-red-500 dark:text-red-400" : "text-muted-foreground",
                            )}
                          >
                            {remaining}/3
                          </span>
                          <Tooltip>
                            <TooltipTrigger
                              render={
                                <button
                                  type="button"
                                  disabled={generatingDoc !== null || exhausted}
                                  onClick={() => void handleGenerateDoc(item.type)}
                                  aria-label={`Generate ${item.title} from website`}
                                  className={cn(
                                    "inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-border/80 bg-surface/85 shadow-xs transition-colors disabled:cursor-not-allowed disabled:opacity-45 dark:border-[#223D27] dark:bg-[#0A140C]/85",
                                    hasWebsite
                                      ? "text-muted-foreground hover:border-primary/50 hover:bg-primary/10 hover:text-primary dark:hover:border-lime-400/50 dark:hover:text-lime-300"
                                      : "text-muted-foreground/45 hover:text-muted-foreground/70",
                                  )}
                                />
                              }
                            >
                              {isBusy ? <Loader2 className="size-3 animate-spin" /> : <Wand2 className="size-3" />}
                            </TooltipTrigger>
                            <TooltipContent side="top">
                              {exhausted
                                ? "All 3 AI attempts used for this document"
                                : hasWebsite
                                  ? `Generate ${item.title} from your website (${remaining}/3 left)`
                                  : "Add your website URL in Step 1 to generate with AI"}
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      );
                    })()}
                  </TooltipProvider>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-6 text-center transition-colors",
          dragOver
            ? "border-primary bg-primary/10 dark:border-lime-400 dark:bg-lime-500/10"
            : "border-border/80 bg-surface/50 hover:border-primary/50 dark:border-[#223D27] dark:bg-[#0A140C]/60 dark:hover:border-lime-400/50",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS}
          className="hidden"
          onChange={(e) => void handleFiles(e.target.files)}
        />
        <UploadCloud className="size-8 text-primary dark:text-lime-400" />
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">
            {uploading ? "Uploading and extracting text..." : "Drop knowledge files here, or click to browse"}
          </p>
          <p className="text-xs text-muted-foreground">
            Supports PDF, TXT, MD, DOCX (up to 10 MB each, max 20 files)
          </p>
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-xs text-muted-foreground">Loading knowledge files...</p>
      ) : files.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No knowledge files uploaded yet. Upload product catalogs, FAQs, or price lists to ground your AI agent.
        </p>
      ) : (
        <div className="space-y-3">
          {/* Table Controls Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {files.length} {files.length === 1 ? "file" : "files"}
            </span>
            <div className="flex items-center gap-1.5">
              <span>Show</span>
              <select
                aria-label="Files per page"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="h-8 rounded-lg border border-input bg-surface/70 px-2 text-xs text-foreground dark:border-[#223D27] dark:bg-[#0A140C]"
              >
                {[5, 10, 20, 50].map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
              <span>per page</span>
            </div>
          </div>

          {/* Files Table */}
          <div className="overflow-x-auto rounded-xl border border-border/80 bg-surface/40 dark:border-[#223D27] dark:bg-[#0A140C]/55">
            <table className="w-full min-w-[640px] border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-border/80 bg-card/70 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase dark:border-[#223D27] dark:bg-[#112014]/70">
                  <th className="px-3.5 py-2.5">File</th>
                  <th className="px-3.5 py-2.5">Access</th>
                  <th className="px-3.5 py-2.5">Size</th>
                  <th className="px-3.5 py-2.5">Status</th>
                  <th className="px-3.5 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 dark:divide-[#223D27]/70">
                {(() => {
                  const totalPages = Math.max(1, Math.ceil(files.length / pageSize));
                  const safePage = Math.min(page, totalPages);
                  const start = (safePage - 1) * pageSize;
                  return files.slice(start, start + pageSize).map((item) => {
                    const isScanned = item.error === "no_text_extracted_maybe_scanned";
                    const isEditable = /\.(md|txt)$/i.test(item.filename);
                    return (
                      <tr
                        key={item.id}
                        onClick={() => void openFileModal(item)}
                        className="cursor-pointer transition-colors hover:bg-card/60 dark:hover:bg-[#112014]/60"
                      >
                        <td className="max-w-[240px] px-3.5 py-2.5">
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 shrink-0 text-primary dark:text-lime-400" />
                            <div className="min-w-0">
                              <AutoDirText as="span" className="block truncate font-medium text-foreground">
                                {item.filename}
                              </AutoDirText>
                              {isScanned && (
                                <span className="inline-flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-300">
                                  <AlertTriangle className="size-3" />
                                  May be scanned PDF
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3.5 py-2.5 whitespace-nowrap">
                          {isEditable ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:border-lime-400/35 dark:bg-lime-500/15 dark:text-lime-300">
                              <Pencil className="size-3" />
                              Editable
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground dark:border-[#223D27]">
                              <Eye className="size-3" />
                              Read-only
                            </span>
                          )}
                        </td>
                        <td className="px-3.5 py-2.5 whitespace-nowrap text-muted-foreground">
                          {formatBytes(item.size_bytes)} · {item.char_count.toLocaleString()} chars
                        </td>
                        <td className="px-3.5 py-2.5 whitespace-nowrap">
                          <Badge
                            variant={item.status === "ready" ? "default" : "secondary"}
                            className="capitalize"
                          >
                            {item.status}
                          </Badge>
                        </td>
                        <td
                          className="px-3.5 py-2.5 text-right whitespace-nowrap"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="inline-flex items-center justify-end gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              aria-label={isEditable ? `Edit ${item.filename}` : `View ${item.filename}`}
                              onClick={() => void openFileModal(item)}
                              className="size-7 text-muted-foreground hover:text-foreground"
                            >
                              {isEditable ? <Pencil className="size-3.5" /> : <Eye className="size-3.5" />}
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Delete ${item.filename}`}
                              onClick={() => void handleDelete(item.id)}
                              className="size-7 text-muted-foreground hover:text-red-600"
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  });
                })()}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          {(() => {
            const totalPages = Math.max(1, Math.ceil(files.length / pageSize));
            const safePage = Math.min(page, totalPages);
            return (
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  Showing {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, files.length)} of{" "}
                  {files.length}
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={safePage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="h-7 px-2 text-xs"
                  >
                    <ChevronLeft className="mr-1 size-3.5" />
                    Prev
                  </Button>
                  <span className="px-2 font-medium text-foreground">
                    Page {safePage} of {totalPages}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={safePage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="h-7 px-2 text-xs"
                  >
                    Next
                    <ChevronRight className="ml-1 size-3.5" />
                  </Button>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {isClient &&
        modalFile &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => setModalFile(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="knowledge-modal-title"
              onClick={(e) => e.stopPropagation()}
              className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl dark:border-[#223D27] dark:bg-[#112014]"
            >
              <div className="flex items-center justify-between gap-3 border-b border-border/80 px-5 py-4 dark:border-[#223D27]">
                <div className="flex min-w-0 items-center gap-2.5">
                  <FileText className="size-4 shrink-0 text-primary dark:text-lime-400" />
                  <div className="min-w-0">
                    <h3 id="knowledge-modal-title" className="truncate text-sm font-semibold text-foreground">
                      {modalFile.filename}
                    </h3>
                    <p className="text-[11px] text-muted-foreground">
                      {formatBytes(modalFile.size_bytes)} · {modalFile.char_count.toLocaleString()} chars ·{" "}
                      {modalFile.editable ? "Editable (.md / .txt)" : "Read-only preview"}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Close modal"
                  onClick={() => setModalFile(null)}
                >
                  <X className="size-4" />
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                {modalLoading ? (
                  <div className="flex min-h-[220px] items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin text-primary" />
                    Loading document content...
                  </div>
                ) : modalFile.editable ? (
                  <textarea
                    dir="auto"
                    rows={16}
                    value={modalDraft}
                    onChange={(e) => {
                      setModalDraft(e.target.value);
                      setModalSaved(false);
                    }}
                    className="min-h-[340px] w-full resize-y rounded-xl border border-input bg-surface/70 p-3.5 font-mono text-xs leading-relaxed text-foreground focus:outline-none focus:ring-2 focus:ring-ring dark:border-[#223D27] dark:bg-[#0A140C]"
                  />
                ) : (
                  <pre
                    dir="auto"
                    className="min-h-[220px] whitespace-pre-wrap break-words rounded-xl border border-border/70 bg-surface/50 p-4 font-sans text-xs leading-relaxed text-foreground dark:border-[#223D27] dark:bg-[#0A140C]"
                  >
                    {modalFile.content || "No readable text was extracted from this file."}
                  </pre>
                )}

                {modalError && (
                  <p className="mt-3 rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                    {modalError}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-between gap-3 border-t border-border/80 px-5 py-3.5 dark:border-[#223D27]">
                <span className="text-xs text-emerald-600 dark:text-lime-300">
                  {modalSaved ? "Saved changes." : ""}
                </span>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setModalFile(null)}>
                    Close
                  </Button>
                  {modalFile.editable && (
                    <Button
                      type="button"
                      size="sm"
                      disabled={modalLoading || modalSaving}
                      onClick={() => void saveModalContent()}
                      className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                    >
                      {modalSaving ? (
                        <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                      ) : (
                        <Save className="mr-1.5 size-3.5" />
                      )}
                      Save Changes
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
