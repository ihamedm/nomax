import { useEffect, useRef, useState } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getCurrentPosition } from "@/lib/geolocation";
import { useUi } from "@/stores/ui";

const STORAGE_KEY = "nomax.locationPrompt";
type PromptAnswer = "granted" | "dismissed";

function readAnswer(): PromptAnswer | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "granted" || value === "dismissed" ? value : null;
  } catch {
    return null;
  }
}

function storeAnswer(answer: PromptAnswer): void {
  try {
    localStorage.setItem(STORAGE_KEY, answer);
  } catch {
    // Private mode: the prompt may reappear next visit, which is acceptable.
  }
}

/**
 * First-visit geolocation ask.
 *
 * Browsers show their own permission dialog only when `getCurrentPosition`
 * runs, and an unexplained prompt gets denied. This sheet explains the value
 * first, then asks. The answer is remembered so it never nags twice, and it is
 * skipped entirely when the browser already holds a decision.
 */
export function LocationPermissionSheet() {
  const toast = useToast();
  const setLocation = useUi((state) => state.setLocation);
  const locationSource = useUi((state) => state.locationSource);
  const [open, setOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const answeredRef = useRef(false);

  useEffect(() => {
    if (locationSource === "gps") {
      storeAnswer("granted");
      return;
    }

    let cancelled = false;

    /** Apply the position without any UI, for already-granted permissions. */
    const locateSilently = () => {
      void getCurrentPosition()
        .then((coords) => {
          if (!cancelled) setLocation(coords, "gps");
        })
        .catch(() => {
          // Position unavailable right now; the user can retry manually.
        });
    };

    if (readAnswer() === "granted") {
      // Permission was granted on an earlier visit and the in-memory store was
      // reset by the reload: restore the position silently, no prompt.
      locateSilently();
      return () => {
        cancelled = true;
      };
    }
    if (readAnswer()) return;

    const timer = window.setTimeout(async () => {
      if (cancelled) return;
      try {
        const status = await navigator.permissions?.query({
          name: "geolocation" as PermissionName,
        });
        if (cancelled) return;
        if (status?.state === "granted") {
          storeAnswer("granted");
          locateSilently();
          return;
        }
        if (status?.state === "denied") {
          storeAnswer("dismissed");
          return;
        }
      } catch {
        // Safari and older browsers have no Permissions API for geolocation.
      }
      if (!cancelled) setOpen(true);
    }, 800);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [locationSource, setLocation]);

  async function allow() {
    if (answeredRef.current) return;
    answeredRef.current = true;
    setLocating(true);
    try {
      const coords = await getCurrentPosition();
      setLocation(coords, "gps");
      storeAnswer("granted");
      setOpen(false);
      toast("موقعیت شما ثبت شد و نتایج نزدیک‌تر نمایش داده می‌شود.");
    } catch {
      toast("دسترسی به موقعیت ممکن نشد. از تنظیمات مرورگر می‌توانید اجازه دهید.");
    } finally {
      answeredRef.current = false;
      setLocating(false);
    }
  }

  function dismiss() {
    storeAnswer("dismissed");
    setOpen(false);
  }

  return (
    <BottomSheet open={open} onClose={dismiss} title="کسب‌وکارهای نزدیک شما">
      <div className="space-y-4">
        <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 text-center">
          <span
            aria-hidden
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-2xl shadow-sm"
          >
            📍
          </span>
          <p className="mt-3 text-sm font-bold text-slate-900">موقعیت خود را به ما بدهید</p>
          <p className="mt-2 text-xs leading-6 text-slate-600">
            با اجازه دسترسی به موقعیت، فاصله هر کسب‌وکار تا شما محاسبه می‌شود و
            نزدیک‌ترین گزینه‌ها اول نمایش داده می‌شوند. موقعیت شما ذخیره یا منتشر نمی‌شود.
          </p>
        </div>

        <p className="rounded-xl bg-slate-50 px-3 py-2 text-center text-[11px] leading-5 text-slate-500">
          مرورگر از شما تأییدیه‌ای جداگانه می‌پرسد. اگر رد کنید، همچنان می‌توانید نتایج را
          ببینید و بعداً از دکمه «موقعیت من» استفاده کنید.
        </p>

        <div className="flex gap-2">
          <Button className="flex-1" loading={locating} onClick={() => void allow()}>
            اجازه می‌دهم
          </Button>
          <Button variant="outline" className="flex-1" disabled={locating} onClick={dismiss}>
            بعداً
          </Button>
        </div>
      </div>
    </BottomSheet>
  );
}
