import { useCallback, useEffect, useRef, useState, type TouchEvent } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { fa } from "@/lib/format";
import type { BusinessImage } from "@/types";

function Chevron({ direction, className }: { direction: "left" | "right"; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-5 w-5", className)}
      aria-hidden
    >
      {direction === "left" ? <path d="m15 5-7 7 7 7" /> : <path d="m9 5 7 7-7 7" />}
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

interface BusinessGalleryProps {
  name: string;
  images: BusinessImage[];
  icon?: string | null;
}

export function BusinessGallery({ name, images, icon }: BusinessGalleryProps) {
  const [index, setIndex] = useState(0);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const touchStart = useRef<number | null>(null);
  const lightboxTouchStart = useRef<number | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const count = images.length;

  useEffect(() => {
    setIndex(0);
    setLightboxIndex(null);
  }, [name]);

  useEffect(() => {
    setIndex((current) => Math.min(current, Math.max(0, count - 1)));
    setLightboxIndex((current) => {
      if (current === null) return null;
      return count === 0 ? null : Math.min(current, count - 1);
    });
  }, [count]);

  useEffect(() => {
    if (lightboxIndex !== null) setIndex(lightboxIndex);
  }, [lightboxIndex]);

  const goTo = (next: number) => {
    if (count === 0) return;
    setIndex(((next % count) + count) % count);
  };

  const changeLightbox = useCallback(
    (delta: number) => {
      setLightboxIndex((current) => {
        if (current === null || count < 2) return current;
        return ((current + delta) % count + count) % count;
      });
    },
    [count],
  );

  useEffect(() => {
    if (lightboxIndex === null) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLightboxIndex(null);
      else if (event.key === "ArrowRight") {
        event.preventDefault();
        changeLightbox(1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        changeLightbox(-1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 30);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(focusTimer);
    };
  }, [changeLightbox, lightboxIndex]);

  function handleTouchStart(event: TouchEvent) {
    touchStart.current = event.touches[0]?.clientX ?? null;
  }

  function handleTouchEnd(event: TouchEvent) {
    if (touchStart.current === null) return;
    const delta = touchStart.current - (event.changedTouches[0]?.clientX ?? touchStart.current);
    touchStart.current = null;
    if (Math.abs(delta) < 45) return;
    goTo(index + (delta > 0 ? 1 : -1));
  }

  function handleLightboxTouchStart(event: TouchEvent) {
    lightboxTouchStart.current = event.touches[0]?.clientX ?? null;
  }

  function handleLightboxTouchEnd(event: TouchEvent) {
    if (lightboxTouchStart.current === null) return;
    const delta =
      lightboxTouchStart.current - (event.changedTouches[0]?.clientX ?? lightboxTouchStart.current);
    lightboxTouchStart.current = null;
    if (Math.abs(delta) < 45) return;
    changeLightbox(delta > 0 ? 1 : -1);
  }

  if (count === 0) {
    return (
      <div className="relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden bg-gradient-to-br from-brand-50 via-white to-slate-100 sm:aspect-[16/9]">
        <span
          aria-hidden
          className="absolute -left-10 -top-12 h-40 w-40 rounded-full border border-brand-100"
        />
        <span
          aria-hidden
          className="absolute -bottom-16 -right-8 h-48 w-48 rounded-full bg-brand-50/80"
        />
        <div className="relative text-center">
          <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-white bg-white text-3xl shadow-sm">
            {icon || "🏪"}
          </span>
          <p className="mt-3 text-xs text-slate-400">تصویری برای این کسب‌وکار ثبت نشده است.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        className="relative aspect-[4/3] w-full touch-pan-y overflow-hidden bg-slate-200 sm:aspect-[16/9]"
        role="region"
        aria-roledescription="گالری تصاویر"
        aria-label={`تصاویر ${name}`}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={() => {
          touchStart.current = null;
        }}
      >
        <div
          dir="ltr"
          className="flex h-full transition-transform duration-500 ease-out motion-reduce:transition-none"
          style={{ transform: `translateX(-${index * 100}%)` }}
        >
          {images.map((photo, photoIndex) => (
            <button
              key={`${photo.url}-${photoIndex}`}
              type="button"
              tabIndex={photoIndex === index ? 0 : -1}
              aria-hidden={photoIndex !== index}
              aria-label={`بزرگ‌نمایی تصویر ${fa(photoIndex + 1)} از ${fa(count)}`}
              onClick={() => setLightboxIndex(photoIndex)}
              className="relative h-full min-w-full cursor-zoom-in overflow-hidden bg-slate-200"
            >
              <img
                src={photo.url}
                alt={`${name}، تصویر ${fa(photoIndex + 1)} از ${fa(count)}`}
                draggable={false}
                className="h-full w-full select-none object-cover"
              />
            </button>
          ))}
        </div>

        {count > 1 && (
          <>
            <div
              dir="ltr"
              aria-live="polite"
              className="pointer-events-none absolute left-3 top-3 rounded-full bg-slate-950/55 px-2.5 py-1 text-[10px] font-bold text-white backdrop-blur-sm"
            >
              {fa(index + 1)} / {fa(count)}
            </div>
            <button
              type="button"
              aria-label="تصویر قبلی"
              onClick={() => goTo(index - 1)}
              className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-white/50 bg-white/90 text-slate-800 shadow-sm backdrop-blur transition hover:bg-white"
            >
              <Chevron direction="right" />
            </button>
            <button
              type="button"
              aria-label="تصویر بعدی"
              onClick={() => goTo(index + 1)}
              className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-white/50 bg-white/90 text-slate-800 shadow-sm backdrop-blur transition hover:bg-white"
            >
              <Chevron direction="left" />
            </button>
            <span
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-slate-950/35 to-transparent"
            />
            <div className="absolute inset-x-0 bottom-3 flex items-center justify-center gap-1.5">
              {images.map((_, photoIndex) => (
                <button
                  key={photoIndex}
                  type="button"
                  aria-label={`نمایش تصویر ${fa(photoIndex + 1)}`}
                  aria-current={photoIndex === index ? "true" : undefined}
                  onClick={() => goTo(photoIndex)}
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    photoIndex === index ? "w-5 bg-white" : "w-1.5 bg-white/55 hover:bg-white/80",
                  )}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {lightboxIndex !== null &&
        createPortal(
          <div
            dir="rtl"
            role="dialog"
            aria-modal="true"
            aria-label={`گالری تصاویر ${name}`}
            className="fixed inset-0 z-[70] flex flex-col bg-slate-950 text-white"
          >
            <div className="flex items-center justify-between px-4 pb-2 pt-4">
              <button
                ref={closeButtonRef}
                type="button"
                aria-label="بستن گالری"
                onClick={() => setLightboxIndex(null)}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
              >
                <CloseIcon />
              </button>
              <span dir="ltr" className="text-xs font-medium text-white/65">
                {fa(lightboxIndex + 1)} / {fa(count)}
              </span>
              <span className="h-10 w-10" aria-hidden />
            </div>

            <div
              className="relative flex min-h-0 flex-1 items-center justify-center px-4 py-3"
              onClick={() => setLightboxIndex(null)}
              onTouchStart={handleLightboxTouchStart}
              onTouchEnd={handleLightboxTouchEnd}
              onTouchCancel={() => {
                lightboxTouchStart.current = null;
              }}
            >
              <img
                src={images[lightboxIndex]?.url}
                alt={`${name}، تصویر ${fa(lightboxIndex + 1)} از ${fa(count)}`}
                onClick={(event) => event.stopPropagation()}
                className="max-h-full max-w-full select-none rounded-lg object-contain"
                draggable={false}
              />
              {count > 1 && (
                <>
                  <button
                    type="button"
                    aria-label="تصویر قبلی"
                    onClick={(event) => {
                      event.stopPropagation();
                      changeLightbox(-1);
                    }}
                    className="absolute right-2 flex h-11 w-11 items-center justify-center rounded-full bg-slate-900/55 text-white backdrop-blur transition hover:bg-slate-900/80"
                  >
                    <Chevron direction="right" />
                  </button>
                  <button
                    type="button"
                    aria-label="تصویر بعدی"
                    onClick={(event) => {
                      event.stopPropagation();
                      changeLightbox(1);
                    }}
                    className="absolute left-2 flex h-11 w-11 items-center justify-center rounded-full bg-slate-900/55 text-white backdrop-blur transition hover:bg-slate-900/80"
                  >
                    <Chevron direction="left" />
                  </button>
                </>
              )}
            </div>

            {count > 1 && (
              <div className="flex shrink-0 justify-center gap-2 overflow-x-auto px-4 pb-[calc(env(safe-area-inset-bottom,0px)+1.25rem)] pt-2">
                {images.map((photo, photoIndex) => (
                  <button
                    key={`${photo.url}-${photoIndex}`}
                    type="button"
                    aria-label={`نمایش تصویر ${fa(photoIndex + 1)}`}
                    aria-current={photoIndex === lightboxIndex ? "true" : undefined}
                    onClick={() => setLightboxIndex(photoIndex)}
                    className={cn(
                      "h-12 w-12 shrink-0 overflow-hidden rounded-lg border-2 transition",
                      photoIndex === lightboxIndex
                        ? "border-white opacity-100"
                        : "border-transparent opacity-45 hover:opacity-80",
                    )}
                  >
                    <img
                      src={photo.url}
                      alt=""
                      className="h-full w-full object-cover"
                      draggable={false}
                    />
                  </button>
                ))}
              </div>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
