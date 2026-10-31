import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { BottomSheet } from "@/components/ui/bottom-sheet";

interface ConfirmSheetProps {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  loading?: boolean;
  tone?: "brand" | "rose";
  onClose: () => void;
  onConfirm: () => void;
}

export function ConfirmSheet({
  open,
  title,
  description,
  confirmLabel,
  loading = false,
  tone = "brand",
  onClose,
  onConfirm,
}: ConfirmSheetProps) {
  return (
    <BottomSheet open={open} onClose={onClose} title={title}>
      <div className="text-sm leading-7 text-slate-600">{description}</div>
      <div className="mt-6 flex gap-2">
        <Button
          type="button"
          variant={tone === "rose" ? "danger" : "primary"}
          className="flex-1"
          loading={loading}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
        <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
          انصراف
        </Button>
      </div>
    </BottomSheet>
  );
}
