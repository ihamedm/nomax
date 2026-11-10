import { Link, useParams } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import CreateBusinessPage from "@/features/business/CreateBusinessPage";
import type { WizardData } from "@/features/business/create/types";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import type { BusinessImage, Category, Subcategory } from "@/types";

interface EditableBusiness {
  id: string;
  name: string;
  short_description: string;
  description?: string | null;
  phone_business?: string | null;
  address: string;
  geo: { lat: number; lng: number } | null;
  instagram?: string | null;
  is_24h: boolean;
  profile_image_url?: string | null;
  images?: BusinessImage[];
  category: { id: number; slug: string; name: string; icon: string } | null;
  subcategory:
    | {
        id: number;
        slug: string;
        name: string;
        icon: string;
        standard_tags?: string[];
      }
    | null;
  tags: string[];
}

export default function MeBusinessEditPage() {
  const { id } = useParams<{ id: string }>();
  const { data: business, isLoading, error } = useApi<EditableBusiness>(
    ["me", "business", id],
    `/me/businesses/${id}`,
    { enabled: Boolean(id) },
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (error || !business) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-6">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          <p>{error ? errorMessage(error) : "کسب‌وکار پیدا نشد."}</p>
          <Link to="/me/businesses" className="mt-4 inline-block text-brand-600">
            بازگشت به فهرست
          </Link>
        </div>
      </div>
    );
  }

  const category: Category | null = business.category
    ? {
        ...business.category,
        sort_order: 0,
        subcategory_count: business.subcategory ? 1 : 0,
      }
    : null;

  const subcategory: Subcategory | null =
    business.category && business.subcategory
      ? {
          ...business.subcategory,
          category_id: business.category.id,
          sort_order: 0,
          standard_tags: business.subcategory.standard_tags ?? [],
        }
      : null;

  const standard = new Set(subcategory?.standard_tags ?? []);
  const tags = business.tags ?? [];
  const photos = (business.images?.length
    ? [...business.images].sort((a, b) => a.sort_order - b.sort_order)
    : business.profile_image_url
      ? [{ url: business.profile_image_url, is_main: true, sort_order: 0 }]
      : []
  ).map((image) => ({ url: image.url, isMain: image.is_main }));
  if (photos.length > 0 && !photos.some((photo) => photo.isMain)) {
    photos[0] = { ...photos[0], isMain: true };
  }
  const initial: WizardData = {
    title: business.name,
    description: business.description ?? "",
    category,
    subcategory,
    address: business.address,
    is24h: business.is_24h,
    geo: business.geo,
    photos,
    intro: business.short_description ?? "",
    shopPhone: business.phone_business ?? "",
    instagram: business.instagram ?? "",
    licenseEnabled: false,
    standardTags: tags.filter((tag) => standard.has(tag)),
    customTags: tags.filter((tag) => !standard.has(tag)),
  };

  return (
    <CreateBusinessPage
      key={business.id}
      mode="edit"
      businessId={business.id}
      initialData={initial}
    />
  );
}
