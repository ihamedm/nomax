import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { RatingStars } from "@/components/ui/stars";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { DEFAULT_DESCRIPTION, absoluteUrl, useSeo } from "@/lib/seo";
import { fa, formatPhone, formatRating } from "@/lib/format";
import { formatJalali, formatJalaliDateTime, formatRelative } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { returnPath } from "@/lib/auth-redirect";
import { useAuth } from "@/stores/auth";
import { NAVIGATION_APPS, navigationHref, useNavigationApp } from "@/stores/navigation";
import { LoginRequiredSheet } from "@/features/auth/LoginRequiredSheet";
import { NeshanMap, type MapMarker } from "@/features/map/NeshanMap";
import { ReviewSheet } from "@/features/reviews/ReviewSheet";
import type { BusinessDetail, BusinessListItem } from "@/types";
import { BusinessGallery } from "./detail/BusinessGallery";
import { OwnerClaimSheet } from "./detail/OwnerClaimSheet";

function PhoneIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />
    </Icon>
  );
}

function NavigationIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="m3 11 18-8-8 18-2-8-8-2Z" />
    </Icon>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="m5 13 4 4L19 7" />
    </Icon>
  );
}

function PinIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </Icon>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Icon>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M12 3 4.5 6v5c0 4.5 3.2 8.2 7.5 10 4.3-1.8 7.5-5.5 7.5-10V6L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  );
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </Icon>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <path d="M17.5 6.5h.01" />
    </Icon>
  );
}

function BookmarkIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4z" />
    </svg>
  );
}

function LicenseTick() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5 shrink-0 text-sky-500"
      role="img"
      aria-label="مجوز تأیید شده"
    >
      <path
        fill="currentColor"
        d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.1 14.3-3.6-3.6 1.4-1.4 2.2 2.2 4.8-4.8 1.4 1.4-6.2 6.2Z"
      />
    </svg>
  );
}

function HeartIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
      aria-hidden
    >
      <path d="M12 20.5S3.5 15 3.5 9.3A4.8 4.8 0 0 1 12 5.7a4.8 4.8 0 0 1 8.5 3.6C20.5 15 12 20.5 12 20.5Z" />
    </svg>
  );
}

function myReviewBadge(review: NonNullable<BusinessDetail["my_review"]>) {
  if (review.is_private) return { label: "نظر خصوصی", tone: "sky" as const };
  if (review.status === "approved") return { label: "نظر شما منتشر شد", tone: "brand" as const };
  if (review.status === "declined") return { label: "مالک نظر را نپذیرفت", tone: "rose" as const };
  if (review.status === "rejected") return { label: "نظر رد شد", tone: "rose" as const };
  if (review.status === "awaiting_owner") {
    return { label: "در انتظار تأیید مالک", tone: "amber" as const };
  }
  return { label: "در انتظار تأیید", tone: "amber" as const };
}

function telHref(phone: string | null | undefined) {
  if (!phone) return null;
  return `tel:${phone.startsWith("0") ? phone : `0${phone}`}`;
}

function maskPhone(phone: string) {
  return phone.length > 4 ? `${phone.slice(0, -4)}****` : "****";
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function instagramUrl(value: string) {
  return value.startsWith("http") ? value : `https://instagram.com/${value.replace(/^@/, "")}`;
}

/** schema.org graph for the public business page: LocalBusiness + breadcrumbs. */
function businessSchema(business: BusinessDetail) {
  const url = absoluteUrl(`/businesses/${encodeURIComponent(business.slug)}`);
  const images = [
    business.profile_image_url,
    business.avatar_url,
    ...(business.images ?? []).map((image) => image.url),
  ]
    .filter((src, index, all): src is string => Boolean(src) && all.indexOf(src) === index)
    .map((src) => (src.startsWith("http") ? src : absoluteUrl(src)));

  const reviews = business.reviews
    .filter((review) => review.rating > 0)
    .slice(0, 5)
    .map((review) => ({
      "@type": "Review",
      author: { "@type": "Person", name: review.author_name || "کاربر نومکس" },
      reviewRating: { "@type": "Rating", ratingValue: review.rating, bestRating: 5 },
      reviewBody: review.text || undefined,
      datePublished: review.created_at || undefined,
    }));

  const localBusiness = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    "@id": `${url}#business`,
    name: business.name,
    url,
    description: business.description || business.short_description || undefined,
    telephone: business.phone_business || undefined,
    image: images.length ? images : undefined,
    address: {
      "@type": "PostalAddress",
      streetAddress: business.address || undefined,
      addressLocality: "بهبهان",
      addressRegion: "خوزستان",
      addressCountry: "IR",
    },
    areaServed: { "@type": "City", name: "بهبهان" },
    geo: business.geo
      ? { "@type": "GeoCoordinates", latitude: business.geo.lat, longitude: business.geo.lng }
      : undefined,
    sameAs: business.instagram ? [instagramUrl(business.instagram)] : undefined,
    openingHoursSpecification: business.is_24h
      ? [
          {
            "@type": "OpeningHoursSpecification",
            dayOfWeek: WEEKDAYS,
            opens: "00:00",
            closes: "23:59",
          },
        ]
      : undefined,
    aggregateRating:
      business.rating_count > 0
        ? {
            "@type": "AggregateRating",
            ratingValue: business.rating_avg,
            reviewCount: business.rating_count,
            bestRating: 5,
            worstRating: 1,
          }
        : undefined,
    review: reviews.length ? reviews : undefined,
  };

  const crumbs: Record<string, unknown>[] = [
    { "@type": "ListItem", position: 1, name: "نومکس", item: absoluteUrl("/") },
  ];
  if (business.category) {
    crumbs.push({
      "@type": "ListItem",
      position: crumbs.length + 1,
      name: business.category.name,
      item: absoluteUrl(`/search?cat=${encodeURIComponent(business.category.slug)}`),
    });
  }
  crumbs.push({
    "@type": "ListItem",
    position: crumbs.length + 1,
    name: business.name,
    item: url,
  });

  return [
    localBusiness,
    { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: crumbs },
  ];
}

type LoginPrompt = "review" | "save" | "like" | "phone" | "instagram" | "claim";

const LOGIN_PROMPTS: Record<LoginPrompt, { title: string; description: string }> = {
  save: {
    title: "ورود برای ذخیره کسب‌وکار",
    description: "برای ذخیره کسب‌وکار در حساب خود، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
  like: {
    title: "ورود برای لایک کردن",
    description: "برای پسندیدن این کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
  claim: {
    title: "ورود برای ثبت مالکیت",
    description:
      "برای مشاهده شماره مالک و ثبت مالکیت این کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
  review: {
    title: "ورود برای ثبت نظر",
    description: "برای ثبت امتیاز و نظر برای این کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
  phone: {
    title: "ورود برای مشاهده شماره تماس",
    description:
      "برای مشاهده کامل شماره تماس مالک کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
  instagram: {
    title: "ورود برای مشاهده اینستاگرام",
    description: "برای مشاهده صفحه اینستاگرام این کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید.",
  },
};

export function BusinessDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const setSession = useAuth((state) => state.setSession);
  const detailQuery = useApi<BusinessDetail>(
    ["business", slug],
    `/businesses/${encodeURIComponent(slug ?? "")}`,
    { enabled: Boolean(slug) },
  );
  const business = detailQuery.data ?? null;
  const loading = detailQuery.isLoading;
  const error = detailQuery.error ? errorMessage(detailQuery.error) : null;
  const saved = Boolean(business?.is_saved);
  const liked = Boolean(business?.is_liked);
  // A user can own only one business, so the claim button is pointless (and
  // misleading) for anyone who already has one.
  const myBusinesses = useApi<{ items: BusinessListItem[] }>(["me", "businesses"], "/me/businesses", {
    enabled: Boolean(user),
  });
  const ownsBusiness =
    Boolean(business?.is_owner) || (myBusinesses.data?.items.length ?? 0) > 0;
  const [reviewOpen, setReviewOpen] = useState(false);
  const [claimOpen, setClaimOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [reviewHint, setReviewHint] = useState<string | null>(null);
  const [navMenuOpen, setNavMenuOpen] = useState(false);
  const navigationApp = useNavigationApp((state) => state.app);
  const setNavigationApp = useNavigationApp((state) => state.setApp);
  const reviewsRef = useRef<HTMLElement | null>(null);
  const [loginPrompt, setLoginPrompt] = useState<LoginPrompt | null>(null);
  const reviewIntentHandled = useRef(false);

  const saveMutation = useMutation({
    mutationFn: (note: string) => {
      if (!business) return Promise.resolve();
      return api(`/me/bookmarks/${business.id}`, {
        method: "POST",
        body: JSON.stringify({ note: note.trim() || null }),
      });
    },
    onSuccess: (_result, note) => {
      const trimmed = note.trim() || null;
      queryClient.setQueryData<BusinessDetail>(["business", slug], (current) =>
        current ? { ...current, is_saved: true, bookmark_note: trimmed } : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["me", "bookmarks"] });
      setNoteOpen(false);
      toast("کسب‌وکار ذخیره شد.");
    },
    onError: (saveError) => toast(errorMessage(saveError)),
  });

  const removeBookmark = useMutation({
    mutationFn: () => {
      if (!business) return Promise.resolve();
      return api(`/me/bookmarks/${business.id}`, { method: "DELETE" });
    },
    onSuccess: () => {
      queryClient.setQueryData<BusinessDetail>(["business", slug], (current) =>
        current ? { ...current, is_saved: false, bookmark_note: null } : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["me", "bookmarks"] });
      setNoteOpen(false);
      toast("از ذخیره‌شده‌ها حذف شد.");
    },
    onError: (saveError) => toast(errorMessage(saveError)),
  });

  const likeMutation = useMutation({
    mutationFn: () => {
      if (!business) return Promise.resolve({ liked, like_count: 0 });
      return api<{ liked: boolean; like_count: number }>(
        `/me/likes/${business.id}`,
        { method: liked ? "DELETE" : "POST" },
      );
    },
    onSuccess: (result) => {
      queryClient.setQueryData<BusinessDetail>(["business", slug], (current) =>
        current ? { ...current, is_liked: result.liked, like_count: result.like_count } : current,
      );
      toast(result.liked ? "کسب‌وکار لایک شد." : "لایک برداشته شد.");
    },
    onError: (likeError) => toast(errorMessage(likeError)),
  });

  const reviewParams = new URLSearchParams(location.search);  reviewParams.set("review", "1");
  const reviewNext = `${location.pathname}?${reviewParams.toString()}`;
  const currentPath = returnPath(location);

  // Navigating between business pages keeps this component mounted, so reset
  // the one-shot intent flag when the slug changes.
  useEffect(() => {
    reviewIntentHandled.current = false;
  }, [slug]);

  // The login sheet hands the review intent back through router state. Open
  // the review sheet only after hydration and only when the user can review,
  // then clear the one-shot state without changing the URL.
  const openReviewIntent = Boolean(
    (location.state as { openReview?: boolean } | null)?.openReview,
  );
  useEffect(() => {
    if (!openReviewIntent || reviewIntentHandled.current) return;
    if (!ready || detailQuery.isLoading) return;

    reviewIntentHandled.current = true;
    if (!user) {
      setLoginPrompt("review");
    } else if (business && !business.is_owner && !business.my_review) {
      setReviewOpen(true);
    }
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [
    business,
    detailQuery.isLoading,
    location.pathname,
    location.search,
    navigate,
    openReviewIntent,
    ready,
    user,
  ]);

  function requestReview() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("review");
      return;
    }
    setReviewOpen(true);
  }

  // Tapping the rating scrolls to the reviews list. With no reviews yet there
  // is nothing to read, so the review sheet opens with a first-review hint.
  function openReviews() {
    if (!business) return;
    const canReview = !business.is_owner && !business.my_review;
    const opensSheet = canReview && business.reviews.length === 0;
    // Jump instantly when the sheet opens so the list is already in place once
    // it closes; a smooth scroll would be interrupted by the sheet.
    reviewsRef.current?.scrollIntoView({
      behavior: opensSheet ? "auto" : "smooth",
      block: "start",
    });
    setReviewHint(
      opensSheet
        ? "هنوز هیچ نظری برای این کسب‌وکار ثبت نشده است؛ شما اولین نفر باشید و تجربه‌تان را با دیگران به اشتراک بگذارید."
        : null,
    );
    if (opensSheet) requestReview();
  }

  function requestSave() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("save");
      return;
    }
    setNoteDraft(business?.bookmark_note ?? "");
    setNoteOpen(true);
  }

  function requestLike() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("like");
      return;
    }
    likeMutation.mutate();
  }

  function requestClaim() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("claim");
      return;
    }
    setClaimOpen(true);
  }

  const mapMarkers = useMemo<MapMarker[]>(() => {
    if (!business?.geo) return [];
    return [
      {
        id: business.id,
        lat: business.geo.lat,
        lng: business.geo.lng,
        title: business.name,
        subtitle: business.address,
      },
    ];
  }, [business]);

  const photos = useMemo(() => {
    if (!business) return [];
    if (business.images?.length) {
      return [...business.images].sort((a, b) => a.sort_order - b.sort_order);
    }
    return business.profile_image_url
      ? [{ url: business.profile_image_url, is_main: true, sort_order: 0 }]
      : [];
  }, [business]);

  useSeo({
    title: business
      ? `${business.name} | ${business.category?.name ?? "کسب‌وکار"} در بهبهان | نومکس`
      : "کسب‌وکار | نومکس",
    description: business
      ? (
          business.description?.trim() ||
          business.short_description?.trim() ||
          DEFAULT_DESCRIPTION
        ).slice(0, 160)
      : DEFAULT_DESCRIPTION,
    path: `/businesses/${encodeURIComponent(business?.slug ?? slug ?? "")}`,
    image: photos[0]?.url ?? business?.profile_image_url ?? null,
    // Pending/rejected pages are owner previews, not public content.
    noindex: !business || business.status !== "approved",
    jsonLd: business ? businessSchema(business) : [],
  });

  const instagramHandle = business?.instagram?.replace(/^@/, "").replace(/[^A-Za-z0-9._]/g, "");
  const owner = business?.owner ?? null;
  const ownerVerified = owner?.is_verified === true;
  const ownerName = owner?.name?.trim() || "مالک نومکس";
  const ownerPhone = owner?.phone?.trim() || null;
  const businessPhone = business?.phone_business?.trim() || null;
  // The API already masks anonymous responses; masking again is harmless and
  // keeps the page safe behind an older cached response.
  const visibleOwnerPhone = ownerPhone && !user ? maskPhone(ownerPhone) : ownerPhone;
  const displayPhone = businessPhone ?? visibleOwnerPhone;
  const callNumber = telHref(displayPhone);
  // The primary call button only reveals the owner's number when the business
  // has no public phone, so anonymous visitors must sign in first.
  const callNeedsLogin = !user && !businessPhone && Boolean(ownerPhone);
  const navigationLink = business?.geo
    ? navigationHref(navigationApp, business.geo.lat, business.geo.lng)
    : null;
  const navigationLabel =
    NAVIGATION_APPS.find((item) => item.value === navigationApp)?.label ?? "نشان";

  return (
    <main className="mx-auto min-h-[100dvh] w-full max-w-3xl pb-16">
      {loading && (
        <div className="flex justify-center py-24 text-brand-600">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="px-4 py-10 sm:px-6">
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700">
            <p>{error}</p>
            <Link to="/search" className="mt-4 inline-block">
              <Button size="sm" variant="outline">
                بازگشت به جستجو
              </Button>
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && business && (
        <div className="space-y-3 px-4 pb-2 pt-4 sm:px-6">
          {business.status === "rejected" && (
            <section
              role="alert"
              className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="rose">ردشده</Badge>
                <p className="text-sm font-bold">این کسب‌وکار توسط مدیر رد شده است.</p>
              </div>
              <p className="mt-3 rounded-xl bg-white/70 px-3 py-2 text-xs leading-6 text-rose-700">
                <span className="font-bold">دلیل رد: </span>
                {business.rejection_reason || "دلیلی ثبت نشده است."}
              </p>
              <p className="mt-3 text-[11px] leading-5 text-rose-600">
                {business.is_owner
                  ? "اطلاعات کسب‌وکار را اصلاح کنید تا دوباره برای بررسی مدیر ارسال شود."
                  : "این کسب‌وکار تا اصلاح اطلاعات برای کاربران نمایش داده نمی‌شود."}
              </p>
              {business.is_owner && (
                <Link to={`/businesses/${business.id}/edit`} className="mt-4 inline-block">
                  <Button size="sm">اصلاح و ارسال دوباره</Button>
                </Link>
              )}
            </section>
          )}

          {business.status === "pending" && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="amber">در انتظار تأیید</Badge>
                <p className="text-sm font-bold">این کسب‌وکار در صف بررسی مدیر است.</p>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-amber-700">
                {business.is_owner
                  ? "تا زمان تأیید، این صفحه فقط برای شما و مدیران قابل مشاهده است. با ویرایش، اطلاعات به‌روز شده و دوباره ارسال می‌شود."
                  : "این صفحه تا تأیید مدیر برای کاربران نمایش داده نمی‌شود."}
              </p>
              {business.is_owner && (
                <Link to={`/businesses/${business.id}/edit`} className="mt-3 inline-block">
                  <Button size="sm" variant="outline">
                    ویرایش اطلاعات
                  </Button>
                </Link>
              )}
            </section>
          )}

          <section className="overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
            <div className="relative">
              <BusinessGallery
                name={business.name}
                images={photos}
                icon={business.category?.icon}
              />
              <button
                type="button"
                aria-label={saved ? "حذف از ذخیره‌شده‌ها" : "ذخیره کسب‌وکار"}
                aria-pressed={saved}
                title={saved ? "ذخیره شده" : "ذخیره کسب‌وکار"}
                onClick={requestSave}
                className={cn(
                  "absolute right-3 top-3 z-10 flex h-10 w-10 items-center justify-center rounded-full border shadow-sm backdrop-blur transition disabled:opacity-60",
                  saved
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-white/60 bg-white/90 text-slate-700 hover:border-brand-200 hover:text-brand-700",
                )}
              >
                <BookmarkIcon filled={saved} />
              </button>
            </div>

            <div className="px-5 pb-5 pt-4">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 text-[11px] font-medium text-slate-400">
                  {business.category?.icon} {business.category?.name}
                  {(business.subcategories?.length
                    ? business.subcategories
                    : business.subcategory
                      ? [business.subcategory]
                      : []
                  ).map((item) => ` · ${item.name}`).join("")}
                </p>
                {business.is_owner && (
                  <Link
                    to={`/businesses/${business.id}/edit`}
                    className="shrink-0 text-[11px] font-bold text-brand-600 hover:text-brand-700"
                  >
                    ویرایش پروفایل
                  </Link>
                )}
              </div>

              <h1 className="mt-1.5 flex items-center gap-1.5 text-2xl font-black leading-9 tracking-tight text-slate-900 sm:text-3xl sm:leading-10">
                <span>{business.name}</span>
                {business.is_license_verified && <LicenseTick />}
              </h1>

              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <button
                  type="button"
                  onClick={openReviews}
                  aria-label="مشاهده نظرات کاربران"
                  className="inline-flex items-center gap-1.5 font-bold text-slate-800 transition-colors hover:text-brand-600"
                >
                  <span className="text-amber-500" aria-hidden>
                    ★
                  </span>
                  {business.rating_count > 0
                    ? formatRating(business.rating_avg)
                    : "بدون امتیاز"}
                  <span className="h-3 w-px bg-slate-200" aria-hidden />
                  <span className="font-normal text-slate-400">
                    {business.rating_count > 0
                      ? `${fa(business.rating_count)} نظر`
                      : "اولین نظر را ثبت کنید"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={requestLike}
                  disabled={likeMutation.isPending}
                  aria-pressed={liked}
                  aria-label={liked ? "برداشتن لایک" : "لایک کردن کسب‌وکار"}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold transition disabled:opacity-60",
                    liked
                      ? "border-rose-200 bg-rose-50 text-rose-600"
                      : "border-slate-200 text-slate-500 hover:border-rose-200 hover:text-rose-600",
                  )}
                >
                  <HeartIcon filled={liked} />
                  {fa(business.like_count ?? 0)}
                </button>
                {business.is_verified && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-700">
                    <ShieldIcon className="h-3 w-3" />
                    تایید هویت شده
                  </span>
                )}
                {business.is_24h && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                    <ClockIcon className="h-3 w-3" />
                    ۲۴ ساعته
                  </span>
                )}
              </div>

              {business.short_description && (
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  {business.short_description}
                </p>
              )}

              {business.updated_at && (
                <p className="mt-3 flex items-center gap-1.5 text-[10px] text-slate-400">
                  <ClockIcon className="h-3.5 w-3.5" />
                  <span>
                    آخرین به‌روزرسانی{" "}
                    <time
                      dateTime={business.updated_at}
                      title={formatJalaliDateTime(business.updated_at)}
                    >
                      {formatRelative(business.updated_at)}
                    </time>
                  </span>
                </p>
              )}
            </div>
          </section>

          <section className="grid grid-cols-2 gap-2.5" aria-label="اقدام‌های کسب‌وکار">
            {callNumber && !callNeedsLogin ? (
              <a
                href={callNumber}
                className="flex min-h-16 items-center gap-2.5 rounded-2xl bg-brand-600 px-3.5 text-white shadow-[0_12px_30px_-20px_rgba(11,138,92,0.9)] transition hover:bg-brand-700"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15">
                  <PhoneIcon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 leading-tight">
                  <span className="block text-[13px] font-bold">
                    {business.phone_business ? "تماس با کسب‌وکار" : "تماس با مالک"}
                  </span>
                  <span dir="ltr" className="mt-1 block text-[10px] text-white/70">
                    {formatPhone(displayPhone ?? "")}
                  </span>
                </span>
              </a>
            ) : callNeedsLogin ? (
              <button
                type="button"
                onClick={() => setLoginPrompt("phone")}
                className="flex min-h-16 items-center gap-2.5 rounded-2xl bg-brand-600 px-3.5 text-right text-white shadow-[0_12px_30px_-20px_rgba(11,138,92,0.9)] transition hover:bg-brand-700"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15">
                  <PhoneIcon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 leading-tight">
                  <span className="block text-[13px] font-bold">تماس با مالک</span>
                  <span dir="ltr" className="mt-1 block text-[10px] text-white/70">
                    {formatPhone(displayPhone ?? "")}
                  </span>
                </span>
              </button>
            ) : (
              <span className="flex min-h-16 items-center justify-center rounded-2xl bg-slate-100 px-3 text-center text-[11px] text-slate-400">
                شماره تماس ثبت نشده
              </span>
            )}

            {navigationLink ? (
              <div className="relative">
                <div className="flex min-h-16 items-stretch rounded-2xl border border-slate-200 bg-white transition hover:border-brand-200 hover:bg-brand-50/30">
                  <a
                    href={navigationLink}
                    className="flex min-w-0 flex-1 items-center gap-2.5 rounded-s-2xl px-3.5 text-slate-800"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                      <NavigationIcon className="h-[18px] w-[18px]" />
                    </span>
                    <span className="min-w-0 leading-tight">
                      <span className="block text-[13px] font-bold">مسیریابی</span>
                      <span className="mt-1 block text-[10px] text-slate-400">
                        در {navigationLabel}
                      </span>
                    </span>
                  </a>
                  <button
                    type="button"
                    onClick={() => setNavMenuOpen((open) => !open)}
                    aria-label="انتخاب اپلیکیشن مسیریابی"
                    aria-expanded={navMenuOpen}
                    aria-haspopup="menu"
                    className="flex w-9 shrink-0 items-center justify-center rounded-e-2xl border-s border-slate-100 text-slate-400 transition hover:bg-slate-50 hover:text-slate-700"
                  >
                    <ChevronDownIcon className="h-4 w-4" />
                  </button>
                </div>

                {navMenuOpen && (
                  <>
                    <button
                      type="button"
                      aria-label="بستن فهرست اپلیکیشن‌ها"
                      tabIndex={-1}
                      onClick={() => setNavMenuOpen(false)}
                      className="fixed inset-0 z-20 cursor-default"
                    />
                    <div
                      role="menu"
                      className="absolute inset-x-0 bottom-full z-30 mb-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
                    >
                      {NAVIGATION_APPS.map((app) => (
                        <button
                          key={app.value}
                          type="button"
                          role="menuitemradio"
                          aria-checked={navigationApp === app.value}
                          onClick={() => {
                            setNavigationApp(app.value);
                            setNavMenuOpen(false);
                          }}
                          className={cn(
                            "flex w-full items-center justify-between gap-2 px-3 py-2.5 text-right text-xs transition-colors hover:bg-slate-50",
                            navigationApp === app.value
                              ? "font-bold text-brand-700"
                              : "text-slate-600",
                          )}
                        >
                          {app.label}
                          {navigationApp === app.value && <CheckIcon className="h-4 w-4" />}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ) : (
              <span className="flex min-h-16 items-center justify-center rounded-2xl bg-slate-100 px-3 text-center text-[11px] text-slate-400">
                موقعیت ثبت نشده
              </span>
            )}

            {instagramHandle &&
              (user ? (
                <a
                  href={`https://instagram.com/${instagramHandle}`}
                  target="_blank"
                  rel="noreferrer"
                  className="col-span-2 flex min-h-16 items-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-3.5 text-slate-800 transition hover:border-brand-200 hover:bg-brand-50/30"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                    <InstagramIcon className="h-[18px] w-[18px]" />
                  </span>
                  <span className="min-w-0 leading-tight">
                    <span className="block text-[13px] font-bold">اینستاگرام</span>
                    <span dir="ltr" className="mt-1 block text-[10px] text-slate-400">
                      @{instagramHandle}
                    </span>
                  </span>
                </a>
              ) : (
                <button
                  type="button"
                  onClick={() => setLoginPrompt("instagram")}
                  className="col-span-2 flex min-h-16 items-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-3.5 text-right text-slate-800 transition hover:border-brand-200 hover:bg-brand-50/30"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                    <InstagramIcon className="h-[18px] w-[18px]" />
                  </span>
                  <span className="min-w-0 leading-tight">
                    <span className="block text-[13px] font-bold">اینستاگرام</span>
                    <span dir="ltr" className="mt-1 block text-[10px] text-slate-400">
                      مشاهده صفحه · @{instagramHandle}
                    </span>
                  </span>
                </button>
              ))}
          </section>

          {business.owner && (
            <section className="rounded-2xl border border-slate-200 bg-white p-3.5">
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-base font-black",
                    ownerVerified
                      ? "bg-brand-50 text-brand-700"
                      : "bg-amber-50 text-amber-600",
                  )}
                >
                  {ownerVerified ? (
                    Array.from(ownerName)[0] || "ن"
                  ) : (
                    <WarningIcon className="h-5 w-5" />
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] text-slate-400">مالک کسب‌وکار</p>
                  {ownerVerified ? (
                    <p className="mt-0.5 truncate text-sm font-bold text-slate-900">
                      {ownerName}
                    </p>
                  ) : (
                    <p
                      role="status"
                      className="mt-0.5 flex items-center gap-1 text-sm font-bold text-amber-700"
                    >
                      <WarningIcon className="h-4 w-4 shrink-0" />
                      <span className="truncate">مالک تایید هویت نشده</span>
                    </p>
                  )}
                </div>
                {ownerPhone && (
                  user ? (
                    <a
                      href={telHref(ownerPhone) ?? undefined}
                      aria-label={`تماس با ${ownerVerified ? ownerName : "مالک کسب‌وکار"}`}
                      className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-slate-50 px-3 text-[11px] font-bold text-slate-700 transition hover:bg-brand-50 hover:text-brand-700"
                    >
                      <PhoneIcon className="h-3.5 w-3.5" />
                      <span dir="ltr">{formatPhone(ownerPhone)}</span>
                    </a>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setLoginPrompt("phone")}
                      aria-label="برای مشاهده شماره مالک وارد شوید"
                      className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-slate-50 px-3 text-[11px] font-bold text-slate-700 transition hover:bg-brand-50 hover:text-brand-700"
                    >
                      <PhoneIcon className="h-3.5 w-3.5" />
                      <span dir="ltr">{formatPhone(visibleOwnerPhone ?? "")}</span>
                    </button>
                  )
                )}
              </div>

              {!ownerVerified && !ownsBusiness && (
                <button
                  type="button"
                  onClick={requestClaim}
                  className="mt-3 w-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs font-bold text-amber-800 transition hover:bg-amber-100"
                >
                  من مالک این کسب‌وکار هستم
                </button>
              )}
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-bold text-slate-900">درباره کسب‌وکار</h2>
            {business.description && (
              <p className="mt-2 whitespace-pre-line text-xs leading-7 text-slate-600">
                {business.description}
              </p>
            )}
            <div
              className={cn(
                "flex items-start gap-3",
                business.description ? "mt-4 border-t border-slate-100 pt-4" : "mt-4",
              )}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-500">
                <PinIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] text-slate-400">آدرس</p>
                <p className="mt-0.5 text-xs leading-6 text-slate-700">{business.address}</p>
              </div>
            </div>
          </section>

          {business.geo && (
            <section className="space-y-2">
              <h2 className="text-sm font-bold text-slate-900">موقعیت روی نقشه</h2>
              <NeshanMap
                center={business.geo}
                markers={mapMarkers}
                zoom={17}
                className="h-56"
              />
            </section>
          )}

          <section
            ref={reviewsRef}
            className="scroll-mt-20 rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900">نظرات کاربران</h2>
                <p className="mt-1 text-[11px] text-slate-500">
                  ★ {formatRating(business.rating_avg)} از {fa(business.rating_count)} نظر تأییدشده
                </p>
              </div>
              {!business.is_owner &&
                (business.my_review ? (
                  <Badge tone={myReviewBadge(business.my_review).tone}>
                    {myReviewBadge(business.my_review).label}
                  </Badge>
                ) : (
                  <Button size="sm" onClick={requestReview}>
                    ثبت نظر
                  </Button>
                ))}
            </div>

            {business.is_owner ? (
              <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
                شما مالک این کسب‌وکار هستید و نمی‌توانید برای آن نظر ثبت کنید.
              </p>
            ) : business.my_review ? (
              <p
                className={
                  business.my_review.is_private
                    ? "mt-4 rounded-xl bg-sky-50 px-3 py-2 text-[11px] leading-5 text-sky-700"
                    : "mt-4 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800"
                }
              >
                {business.my_review.is_private
                  ? "نظر خصوصی شما ثبت شده و فقط مالک کسب‌وکار آن را می‌بیند."
                  : business.my_review.status === "approved"
                    ? "نظر شما تأیید و منتشر شده است."
                    : business.my_review.status === "awaiting_owner"
                      ? "نظر شما توسط مدیر تأیید شد و در انتظار تأیید مالک است."
                      : business.my_review.status === "declined"
                        ? "مالک کسب‌وکار این نظر را نپذیرفت و منتشر نشد."
                        : business.my_review.status === "rejected"
                          ? "نظر شما توسط مدیر رد شد."
                          : "نظر شما ثبت شده و در انتظار تأیید مدیر است."}
              </p>
            ) : null}

            <div className="mt-4 space-y-3">
              {business.reviews.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-xs leading-6 text-slate-400">
                  هنوز نظری ثبت نشده است. اولین نفر باشید و تجربه‌تان را با دیگران به اشتراک
                  بگذارید.
                </p>
              ) : (
                business.reviews.map((review) => (
                  <article key={review.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-slate-800">
                          {review.author_name || "کاربر نومکس"}
                        </p>
                        <RatingStars rating={review.rating} className="mt-1" />
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-400">
                        {review.created_at ? formatJalali(review.created_at) : ""}
                      </span>
                    </div>
                    {review.text && (
                      <p className="mt-2 whitespace-pre-line text-xs leading-6 text-slate-600">
                        {review.text}
                      </p>
                    )}
                    {review.reply && (
                      <div className="mt-2 rounded-xl bg-white px-3 py-2">
                        <p className="text-[10px] font-bold text-brand-600">پاسخ مالک کسب‌وکار</p>
                        <p className="mt-1 text-[11px] leading-5 text-slate-600">{review.reply}</p>
                      </div>
                    )}
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      )}

      {business && (
        <>
          <ReviewSheet
            open={reviewOpen}
            businessName={business.name}
            businessSlug={business.slug}
            hint={reviewHint}
            onClose={() => {
              setReviewOpen(false);
              setReviewHint(null);
            }}
            onSubmitted={() => {
              setReviewHint(null);
              void queryClient.invalidateQueries({ queryKey: ["business", slug] });
            }}
          />
          <OwnerClaimSheet
            open={claimOpen}
            businessId={business.id}
            ownerName={owner?.name}
            ownerPhone={ownerPhone}
            onClose={() => setClaimOpen(false)}
            onClaimed={(result) => {
              setSession(result.access, result.refresh, result.user);
              setClaimOpen(false);
              toast("مالکیت ثبت شد. حالا می‌توانید اطلاعات کسب‌وکار را مدیریت کنید.");
              void queryClient.invalidateQueries({ queryKey: ["business", slug] });
            }}
          />
          <BottomSheet
            open={noteOpen}
            onClose={() => setNoteOpen(false)}
            title={saved ? "یادداشت ذخیره‌شده" : "ذخیره کسب‌وکار"}
          >
            <div className="space-y-4">
              <div>
                <label htmlFor="bookmark-note" className="text-xs font-bold text-slate-700">
                  یادداشت <span className="font-normal text-slate-400">(اختیاری)</span>
                </label>
                <textarea
                  id="bookmark-note"
                  value={noteDraft}
                  onChange={(event) => setNoteDraft(event.target.value)}
                  rows={3}
                  maxLength={300}
                  placeholder="مثلاً: شنبه‌ها تعطیل است..."
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-brand-400"
                />
                <p className="mt-1 text-left text-[10px] text-slate-400" dir="ltr">
                  {noteDraft.length}/300
                </p>
                <p className="mt-1 text-[10px] leading-5 text-slate-400">
                  این یادداشت خصوصی است و فقط در بخش ذخیره‌شده‌های شما نمایش داده می‌شود.
                </p>
              </div>
              <Button
                type="button"
                className="w-full"
                loading={saveMutation.isPending}
                onClick={() => saveMutation.mutate(noteDraft)}
              >
                {saved ? "ذخیره یادداشت" : "ذخیره کسب‌وکار"}
              </Button>
              {saved && (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full text-rose-600"
                  loading={removeBookmark.isPending}
                  onClick={() => removeBookmark.mutate()}
                >
                  حذف از ذخیره‌شده‌ها
                </Button>
              )}
            </div>
          </BottomSheet>
          <LoginRequiredSheet
            open={loginPrompt !== null}
            title={loginPrompt ? LOGIN_PROMPTS[loginPrompt].title : ""}
            description={loginPrompt ? LOGIN_PROMPTS[loginPrompt].description : ""}
            next={loginPrompt === "review" ? reviewNext : currentPath}
            onClose={() => setLoginPrompt(null)}
          />
        </>
      )}
    </main>
  );
}
