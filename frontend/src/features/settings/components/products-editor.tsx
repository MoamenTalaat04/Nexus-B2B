"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import {
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Package,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ProductIn } from "@/lib/settings-types";
import { cn } from "@/lib/utils";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

const EMPTY_DRAFT: ProductIn = {
  kind: "product",
  name: "",
  description: "",
  price_range: "",
  min_order: "",
};

export function ProductsEditor({
  products,
  onChange,
}: {
  products: ProductIn[];
  onChange: (next: ProductIn[]) => void;
}) {
  const [pageSize, setPageSize] = useState<number>(10);
  const [page, setPage] = useState<number>(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<ProductIn>(EMPTY_DRAFT);
  const [draftError, setDraftError] = useState<string | null>(null);

  const isClient = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  // Filter out initial blank placeholder rows so the table stays clean
  const nonEmptyEntries = useMemo(
    () =>
      products
        .map((item, rawIndex) => ({ item, rawIndex }))
        .filter(({ item }) => item.name.trim().length > 0),
    [products],
  );

  const totalItems = nonEmptyEntries.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const safePage = Math.min(page, totalPages);

  const pageEntries = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return nonEmptyEntries.slice(start, start + pageSize);
  }, [nonEmptyEntries, safePage, pageSize]);

  function openAddModal() {
    setEditingIndex(null);
    setDraft({ ...EMPTY_DRAFT });
    setDraftError(null);
    setModalOpen(true);
  }

  function openEditModal(rawIndex: number, item: ProductIn) {
    setEditingIndex(rawIndex);
    setDraft({
      kind: item.kind ?? "product",
      name: item.name,
      description: item.description ?? "",
      price_range: item.price_range ?? "",
      min_order: item.min_order ?? "",
    });
    setDraftError(null);
    setModalOpen(true);
  }

  function handleSaveDraft() {
    if (!draft.name.trim()) {
      setDraftError(draft.kind === "service" ? "Service name is required." : "Product name is required.");
      return;
    }
    const cleaned: ProductIn = {
      kind: draft.kind ?? "product",
      name: draft.name.trim(),
      description: draft.description.trim(),
      price_range: draft.price_range?.trim() || null,
      min_order: draft.min_order?.trim() || null,
    };

    const existingValid = products.filter((p) => p.name.trim().length > 0);
    if (editingIndex !== null) {
      const next = products.map((item, idx) => (idx === editingIndex ? cleaned : item));
      onChange(next.filter((p) => p.name.trim().length > 0));
    } else {
      onChange([...existingValid, cleaned]);
      const nextTotalPages = Math.max(1, Math.ceil((existingValid.length + 1) / pageSize));
      setPage(nextTotalPages);
    }
    setModalOpen(false);
  }

  function removeItem(rawIndex: number) {
    const next = products.filter((_, idx) => idx !== rawIndex && _.name.trim().length > 0);
    onChange(next);
  }

  useEffect(() => {
    if (!modalOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [modalOpen]);

  const isServiceDraft = draft.kind === "service";

  return (
    <div className="space-y-3">
      {/* Table Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-muted-foreground">
            {totalItems} {totalItems === 1 ? "item" : "items"}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Show</span>
            <select
              aria-label="Items per page"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="h-8 rounded-lg border border-input bg-surface/70 px-2 text-xs text-foreground dark:border-[#223D27] dark:bg-[#0A140C]"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
            <span>per page</span>
          </div>
        </div>

        <Button
          type="button"
          size="sm"
          onClick={openAddModal}
          disabled={totalItems >= 30}
          className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
        >
          <Plus className="mr-1.5 size-4" />
          Add Product / Service
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-border/80 bg-surface/40 dark:border-[#223D27] dark:bg-[#0A140C]/55">
        <table className="w-full min-w-[680px] border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-border/80 bg-card/70 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase dark:border-[#223D27] dark:bg-[#112014]/70">
              <th className="px-3.5 py-2.5">Name</th>
              <th className="px-3.5 py-2.5">Type</th>
              <th className="px-3.5 py-2.5">Price range</th>
              <th className="px-3.5 py-2.5">MOQ / Scope</th>
              <th className="px-3.5 py-2.5">Description</th>
              <th className="px-3.5 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60 dark:divide-[#223D27]/70">
            {pageEntries.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-xs text-muted-foreground">
                  No products or services added yet. Click &ldquo;Add Product / Service&rdquo; or use AI extraction
                  above.
                </td>
              </tr>
            ) : (
              pageEntries.map(({ item, rawIndex }) => {
                const isService = item.kind === "service";
                return (
                  <tr
                    key={`${rawIndex}-${item.name}`}
                    className="transition-colors hover:bg-card/60 dark:hover:bg-[#112014]/60"
                  >
                    <td className="max-w-[180px] px-3.5 py-2.5 font-medium text-foreground">
                      <AutoDirText as="span" className="block truncate">
                        {item.name}
                      </AutoDirText>
                    </td>
                    <td className="px-3.5 py-2.5 whitespace-nowrap">
                      {isService ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/35 bg-sky-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-sky-700 dark:border-sky-400/35 dark:bg-sky-500/15 dark:text-sky-300">
                          <Briefcase className="size-3" />
                          Service
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:border-lime-400/35 dark:bg-lime-500/15 dark:text-lime-300">
                          <Package className="size-3" />
                          Product
                        </span>
                      )}
                    </td>
                    <td className="max-w-[130px] px-3.5 py-2.5 text-muted-foreground">
                      <AutoDirText as="span" className="block truncate">
                        {item.price_range || "—"}
                      </AutoDirText>
                    </td>
                    <td className="max-w-[130px] px-3.5 py-2.5 text-muted-foreground">
                      <AutoDirText as="span" className="block truncate">
                        {item.min_order || "—"}
                      </AutoDirText>
                    </td>
                    <td className="max-w-[220px] px-3.5 py-2.5 text-muted-foreground">
                      <AutoDirText as="span" className="block truncate">
                        {item.description || "—"}
                      </AutoDirText>
                    </td>
                    <td className="px-3.5 py-2.5 text-right whitespace-nowrap">
                      <div className="inline-flex items-center justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Edit ${item.name}`}
                          onClick={() => openEditModal(rawIndex, item)}
                          className="size-7 text-muted-foreground hover:text-foreground"
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Delete ${item.name}`}
                          onClick={() => removeItem(rawIndex)}
                          className="size-7 text-muted-foreground hover:text-red-600"
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalItems > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            Showing {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, totalItems)} of {totalItems}
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
      )}

      {/* Add / Edit Popup Modal */}
      {isClient &&
        modalOpen &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
            onClick={() => setModalOpen(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="offering-modal-title"
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-card shadow-2xl dark:border-[#223D27] dark:bg-[#112014]"
            >
              <div className="flex items-center justify-between border-b border-border/80 px-5 py-4 dark:border-[#223D27]">
                <div>
                  <h3 id="offering-modal-title" className="text-sm font-semibold text-foreground">
                    {editingIndex !== null ? "Edit Product / Service" : "Add Product / Service"}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Specify whether this is a product or service and fill in the details.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Close modal"
                  onClick={() => setModalOpen(false)}
                >
                  <X className="size-4" />
                </Button>
              </div>

              <div className="space-y-4 p-5">
                {/* Product vs Service Selection Cards */}
                <div className="space-y-1.5">
                  <Label className="text-xs">Offering type</Label>
                  <div className="grid grid-cols-2 gap-2.5">
                    {[
                      {
                        kind: "product" as const,
                        title: "Product",
                        desc: "Physical or digital goods you sell.",
                        icon: Package,
                      },
                      {
                        kind: "service" as const,
                        title: "Service",
                        desc: "Rentals, SaaS, consulting, or agency work.",
                        icon: Briefcase,
                      },
                    ].map((opt) => {
                      const Icon = opt.icon;
                      const active = (draft.kind ?? "product") === opt.kind;
                      return (
                        <button
                          key={opt.kind}
                          type="button"
                          onClick={() => setDraft((prev) => ({ ...prev, kind: opt.kind }))}
                          className={cn(
                            "flex items-start gap-2.5 rounded-xl border p-3 text-left transition-all",
                            active
                              ? "border-primary bg-primary/10 dark:border-lime-400 dark:bg-lime-500/15"
                              : "border-border/80 bg-surface/50 hover:border-primary/45 dark:border-[#223D27] dark:bg-[#0A140C]/60",
                          )}
                        >
                          <span
                            className={cn(
                              "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg border",
                              active
                                ? "border-primary/40 bg-primary text-primary-foreground dark:border-lime-400/50 dark:bg-lime-400 dark:text-[#0A140C]"
                                : "border-border/80 bg-card text-muted-foreground dark:border-[#223D27] dark:bg-[#112014]",
                            )}
                          >
                            <Icon className="size-3.5" />
                          </span>
                          <span className="min-w-0">
                            <span className="block text-xs font-semibold text-foreground">{opt.title}</span>
                            <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                              {opt.desc}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label htmlFor="modal-prod-name">
                      {isServiceDraft ? "Service name *" : "Product name *"}
                    </Label>
                    <Input
                      id="modal-prod-name"
                      dir="auto"
                      placeholder={
                        isServiceDraft ? "e.g. Monthly SEO Retainer / Equipment Rental" : "e.g. Kids Summer Sets"
                      }
                      value={draft.name}
                      onChange={(e) => {
                        setDraft((prev) => ({ ...prev, name: e.target.value }));
                        setDraftError(null);
                      }}
                    />
                  </div>

                  <div className="grid gap-1.5">
                    <Label htmlFor="modal-prod-price">Price range</Label>
                    <Input
                      id="modal-prod-price"
                      dir="auto"
                      placeholder={isServiceDraft ? "e.g. 5,000-15,000 EGP / month" : "e.g. 120-250 EGP / piece"}
                      value={draft.price_range ?? ""}
                      onChange={(e) =>
                        setDraft((prev) => ({ ...prev, price_range: e.target.value || null }))
                      }
                    />
                  </div>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="modal-prod-moq">
                    {isServiceDraft ? "Min. commitment / Scope" : "Minimum order (MOQ)"}
                  </Label>
                  <Input
                    id="modal-prod-moq"
                    dir="auto"
                    placeholder={isServiceDraft ? "e.g. 3-month contract / 1 project" : "e.g. 1 dozen per model"}
                    value={draft.min_order ?? ""}
                    onChange={(e) =>
                      setDraft((prev) => ({ ...prev, min_order: e.target.value || null }))
                    }
                  />
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="modal-prod-desc">Short description</Label>
                  <textarea
                    id="modal-prod-desc"
                    dir="auto"
                    rows={3}
                    placeholder={
                      isServiceDraft ? "Deliverables, SLA, target clients..." : "Fabric, sizes, target buyers..."
                    }
                    value={draft.description}
                    onChange={(e) => setDraft((prev) => ({ ...prev, description: e.target.value }))}
                    className="w-full rounded-lg border border-input bg-surface/70 px-3 py-2 text-sm dark:border-[#223D27] dark:bg-[#0A140C]"
                  />
                </div>

                {draftError && (
                  <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                    {draftError}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-border/80 px-5 py-3.5 dark:border-[#223D27]">
                <Button type="button" variant="outline" size="sm" onClick={() => setModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSaveDraft}
                  className="bg-gradient-to-r from-[#10B981] to-[#84CC16] font-semibold text-[#0A140C]"
                >
                  {editingIndex !== null ? "Save Changes" : "Confirm & Add"}
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
