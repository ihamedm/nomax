import { useEffect, useRef, useState } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { getCurrentPosition } from "@/lib/geolocation";
import {
  isLocationGranted,
  markLocationGranted,
  recordAutoPrompt,
  shouldAutoPrompt,
} from "@/lib/location-prompt";
import { useUi } from "@/stores/ui";

/**
 * Geolocation explainer sheet.
 *
 * Automatically asks at most three times, one per day, until permission is
 * granted. Location actions (search "my location", map picker) open it directly
 * because that is when the user actually needs the service.
 */
export function LocationPermissionSheet() {
  const toast = useToast();
  const setLocation = useUi((state) => state.setLocation);
  const locationSource = useUi((state) => state.locationSource);
  const open = useUi((state) => state.locationPromptOpen);
  const openPrompt = useUi((state) => state.openLocationPrompt);
  const closePrompt = useUi((state) => state.closeLocationPrompt);
  const [locating, setLocating] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => {
    if (locationSource === "gps") {
      markLocationGranted();
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

    if (isLocationGranted()) {
      // Permission was granted on an earlier visit and the in-memory store was
      // reset by the reload: restore the position silently, no prompt.
      locateSilently();
      return () => {
        cancelled = true;
      };
    }

    if (!shouldAutoPrompt()) return;

    const timer = window.setTimeout(async () => {
      if (cancelled) return;
      try {
        const status = await navigator.permissions?.query({
          name: "geolocation" as PermissionName,
        });
        if (cancelled) return;
        if (status?.state === "granted") {
          markLocationGranted();
          locateSilently();
          return;
        }
        if (status?.state === "denied") return;
      } catch {
        // Safari and older browsers have no Permissions API for geolocation.
      }
      if (cancelled) return;
      recordAutoPrompt();
      openPrompt();
    }, 800);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [locationSource, setLocation, openPrompt]);

  async function allow() {
    if (busyRef.current) return;
    busyRef.current = true;
    setLocating(true);
    try {
      const coords = await getCurrentPosition();
      setLocation(coords, "gps");
      markLocationGranted();
      closePrompt();
      toast("موقعیت شما ثبت شد و نتایج نزدیک‌تر نمایش داده می‌شود.");
    } catch {
      toast("دسترسی به موقعیت ممکن نشد. از تنظیمات مرورگر می‌توانید اجازه دهید.");
    } finally {
      busyRef.current = false;
      setLocating(false);
    }
  }

  return (
    <BottomSheet open={open} onClose={closePrompt} title="کسب‌وکارهای نزدیک شما">
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
          <Button variant="outline" className="flex-1" disabled={locating} onClick={closePrompt}>
            بعداً
          </Button>
        </div>
      </div>
    </BottomSheet>
  );
}
