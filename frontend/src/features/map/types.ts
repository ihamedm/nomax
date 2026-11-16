import type { BusinessCategory } from "@/types";

export interface MapPoint {
  id: string;
  slug: string;
  name: string;
  lat: number;
  lng: number;
  address: string;
  rating_avg: number;
  rating_count: number;
  like_count?: number;
  is_24h: boolean;
  is_verified: boolean;
  is_license_verified?: boolean;
  profile_image_url?: string | null;
  avatar_url?: string | null;
  category?: BusinessCategory | null;
  subcategory?: BusinessCategory | null;
  subcategory_slugs?: string[];
}

export interface MapFeed {
  generated_at?: string | null;
  version?: number;
  items: MapPoint[];
}
