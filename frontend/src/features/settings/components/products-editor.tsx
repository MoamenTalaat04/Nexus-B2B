"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ProductIn } from "@/lib/settings-types";

export function ProductsEditor({
  products,
  onChange,
}: {
  products: ProductIn[];
  onChange: (next: ProductIn[]) => void;
}) {
  function updateItem(index: number, patch: Partial<ProductIn>) {
    onChange(products.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addItem() {
    onChange([
      ...products,
      { name: "", description: "", price_range: "", min_order: "" },
    ]);
  }

  function removeItem(index: number) {
    onChange(products.filter((_, idx) => idx !== index));
  }

  return (
    <div className="space-y-3">
      {products.map((product, index) => (
        <div
          key={index}
          className="space-y-3 rounded-xl border border-border/80 bg-surface/50 p-4 dark:border-[#223D27] dark:bg-[#0A140C]/60"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Product #{index + 1}
            </span>
            {products.length > 1 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeItem(index)}
                className="h-7 px-2 text-xs text-muted-foreground hover:text-red-600"
              >
                <Trash2 className="mr-1 size-3.5" />
                Remove
              </Button>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor={`prod-name-${index}`}>Product name *</Label>
              <Input
                id={`prod-name-${index}`}
                dir="auto"
                required
                placeholder="e.g. Kids Summer Sets"
                value={product.name}
                onChange={(e) => updateItem(index, { name: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`prod-price-${index}`}>Price range</Label>
              <Input
                id={`prod-price-${index}`}
                dir="auto"
                placeholder="e.g. 120-250 EGP / piece"
                value={product.price_range ?? ""}
                onChange={(e) => updateItem(index, { price_range: e.target.value || null })}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor={`prod-moq-${index}`}>Minimum order (MOQ)</Label>
              <Input
                id={`prod-moq-${index}`}
                dir="auto"
                placeholder="e.g. 1 dozen per model"
                value={product.min_order ?? ""}
                onChange={(e) => updateItem(index, { min_order: e.target.value || null })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`prod-desc-${index}`}>Short description</Label>
              <Input
                id={`prod-desc-${index}`}
                dir="auto"
                placeholder="Fabric, sizes, target buyers..."
                value={product.description}
                onChange={(e) => updateItem(index, { description: e.target.value })}
              />
            </div>
          </div>
        </div>
      ))}

      <Button type="button" variant="outline" size="sm" onClick={addItem} disabled={products.length >= 30}>
        <Plus className="mr-1.5 size-4" />
        Add product
      </Button>
    </div>
  );
}
