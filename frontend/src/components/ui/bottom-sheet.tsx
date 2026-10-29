import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/cn";

interface BottomSheetProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

export function BottomSheet({ open, title, onClose, children, className }: BottomSheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" role="dialog" aria-modal>
      <button
        type="button"
        aria-label="بستن"
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        className={cn(
          "relative max-h-[88dvh] animate-sheet-in overflow-y-auto rounded-t-3xl bg-white shadow-sheet",
          "safe-bottom",
          className,
        )}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between bg-white/95 px-5 pb-3 pt-3 backdrop-blur">
          <span className="mx-auto absolute inset-x-0 top-2 h-1.5 w-10 rounded-full bg-slate-200" />
          <h2 className="pt-4 text-base font-bold text-slate-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="pt-4 text-sm text-slate-500 hover:text-slate-800"
          >
            بستن
          </button>
        </div>
        <div className="px-5 pb-6 pt-1">{children}</div>
      </div>
    </div>
  );
}
