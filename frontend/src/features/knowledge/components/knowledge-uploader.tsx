"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, FileText, Trash2, UploadCloud } from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import type { KnowledgeFileListOut, KnowledgeFileOut } from "@/lib/settings-types";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = ".pdf,.md,.txt,.docx";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function KnowledgeUploader({
  onCountChange,
}: {
  onCountChange?: (count: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<KnowledgeFileOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="space-y-4">
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
        <div className="space-y-2.5">
          {files.map((item) => {
            const isExpanded = expandedId === item.id;
            const isScanned = item.error === "no_text_extracted_maybe_scanned";
            return (
              <Card key={item.id} className="border-border/80 bg-card">
                <CardContent className="space-y-2.5 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <FileText className="size-4 shrink-0 text-primary dark:text-lime-400" />
                      <div className="min-w-0">
                        <AutoDirText as="p" className="truncate text-sm font-medium text-foreground">
                          {item.filename}
                        </AutoDirText>
                        <p className="text-[11px] text-muted-foreground">
                          {formatBytes(item.size_bytes)} · {item.char_count.toLocaleString()} chars
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge
                        variant={item.status === "ready" ? "default" : "secondary"}
                        className="capitalize"
                      >
                        {item.status}
                      </Badge>
                      {item.preview && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpandedId(isExpanded ? null : item.id)}
                        >
                          {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                          <span className="ml-1 text-xs">Preview</span>
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${item.filename}`}
                        onClick={() => void handleDelete(item.id)}
                        className="text-muted-foreground hover:text-red-600"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>

                  {isScanned && (
                    <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                      <AlertTriangle className="size-3.5 shrink-0" />
                      <span>No text extracted — this PDF may be scanned images.</span>
                    </div>
                  )}

                  {isExpanded && item.preview && (
                    <div className="rounded-lg border border-border/70 bg-surface/60 p-3 dark:border-[#223D27] dark:bg-[#0A140C]">
                      <AutoDirText as="p" className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
                        {item.preview}
                      </AutoDirText>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
