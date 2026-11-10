import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/cn";

interface AdminModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

export function AdminModal({ title, onClose, children, className }: AdminModalProps) {
  useEffect(() => {
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
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center sm:p-4" role="dialog" aria-modal>
      <button
        type="button"
        aria-label="بستن"
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        className={cn(
          "relative flex max-h-[92dvh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl",
          className,
        )}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-4 py-4 sm:px-5">
          <h2 className="min-w-0 truncate text-base font-bold text-slate-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-sm text-slate-500 hover:text-slate-800"
          >
            بستن
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5 sm:pb-4">
          {children}
        </div>
      </div>
    </div>
  );
}
