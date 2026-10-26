export type Role = "customer" | "owner" | "admin" | "superadmin";

export interface User {
  id: string;
  phone: string;
  national_id?: string | null;
  full_name?: string | null;
  role: Role;
  permissions: string[];
  is_phone_verified: boolean;
  is_national_id_verified: boolean;
  last_login_at?: string | null;
  created_at?: string | null;
}

export interface AdminUser {
  id: string;
  phone: string;
  full_name?: string | null;
  role: Role;
  permissions: string[];
  is_phone_verified: boolean;
  created_at?: string | null;
}

export interface PermissionItem {
  code: string;
  label: string;
  group: string;
}

export interface DevOtp {
  phone: string;
  otp: string;
  ttl_seconds: number;
  expires_at?: string | null;
}

export interface Category {
  id: number;
  slug: string;
  name: string;
  icon: string;
  sort_order: number;
  subcategory_count: number;
}

export interface Subcategory {
  id: number;
  category_id: number;
  slug: string;
  name: string;
  icon: string;
  sort_order: number;
  standard_tags: string[];
}

export interface LoginResult {
  access: string;
  refresh: string;
  user: User;
}

export interface BusinessCategory {
  id: number;
  slug: string;
  name: string;
  icon: string;
}

export interface BusinessGeo {
  lat: number;
  lng: number;
}

export type BusinessSort = "nearest" | "top" | "newest" | "urgent";

export interface BusinessListItem {
  id: string;
  slug: string;
  name: string;
  short_description: string;
  address: string;
  phone_business?: string | null;
  category: BusinessCategory | null;
  subcategory: BusinessCategory | null;
  geo: BusinessGeo | null;
  distance_m: number | null;
  rating_avg: number;
  rating_count: number;
  is_24h: boolean;
  is_verified: boolean;
  profile_image_url?: string | null;
  created_at?: string | null;
}

export interface BusinessDetail extends BusinessListItem {
  description?: string | null;
  instagram?: string | null;
  reviews: unknown[];
}

export interface SearchMeta {
  has_more: boolean;
  next_cursor: string | null;
}

export interface Coordinates {
  lat: number;
  lng: number;
}
