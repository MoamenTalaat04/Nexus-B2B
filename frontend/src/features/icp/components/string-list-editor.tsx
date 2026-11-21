"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { AutoDirText } from "@/components/shared/auto-dir-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function StringListEditor({
  id,
  label,
  values,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  values: string[];
  placeholder?: string;
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function addItem() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (!values.includes(trimmed)) {
      onChange([...values, trimmed]);
    }
    setDraft("");
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex gap-2">
        <Input
          id={id}
          dir="auto"
          placeholder={placeholder ?? "Type item and press Add"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addItem();
            }
          }}
        />
        <Button type="button" variant="outline" size="sm" onClick={addItem}>
          <Plus className="mr-1 size-4" />
          Add
        </Button>
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((item) => (
            <Badge key={item} variant="secondary" className="flex items-center gap-1.5 px-2.5 py-1 text-xs">
              <AutoDirText>{item}</AutoDirText>
              <button
                type="button"
                aria-label={`Remove ${item}`}
                onClick={() => onChange(values.filter((v) => v !== item))}
                className="hover:text-red-600"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
