export type QuoteStatus = "active" | "accepted" | "cancelled" | "expired";
export type OfferStatus = "pending" | "accepted" | "expired" | "declined";

export interface QuoteCategoryRef {
  id: number;
  slug: string;
  name: string;
  icon: string;
}

export interface QuoteBusiness {
  id: string;
  slug: string;
  name: string;
  address: string;
  rating_avg: number;
  rating_count: number;
  is_verified: boolean;
  profile_image_url?: string | null;
  category?: QuoteCategoryRef | null;
  phone_business?: string | null;
}

export interface QuoteCustomer {
  id: string;
  name: string;
  phone?: string | null;
}

export interface QuoteOffer {
  id: string;
  request_id: string;
  business_id: string;
  price: number | null;
  unit?: string | null;
  brand?: string | null;
  message?: string | null;
  status: OfferStatus;
  business?: QuoteBusiness | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Quote {
  id: string;
  title: string;
  description?: string | null;
  category?: QuoteCategoryRef | null;
  subcategory?: QuoteCategoryRef | null;
  address: string;
  neighborhood?: string | null;
  geo?: { lat: number; lng: number } | null;
  is_urgent: boolean;
  status: QuoteStatus;
  expires_at?: string | null;
  accepted_offer_id?: string | null;
  offers_count: number;
  dispatch?: QuoteDispatchSummary | null;
  accepted_offer?: QuoteOffer | null;
  customer?: QuoteCustomer | null;
  customer_phone?: string | null;
  created_at?: string | null;
  offers?: QuoteOffer[];
}

export interface QuoteListResponse {
  items: Quote[];
}

export interface MatchingBusiness {
  id: string;
  name: string;
}

export interface IncomingQuote extends Quote {
  customer: QuoteCustomer;
  matching_businesses: MatchingBusiness[];
  my_offer?: QuoteOffer | null;
}

export interface IncomingResponse {
  scope: "new" | "archive" | "customers";
  counts: { new: number; archive: number; customers: number };
  items: IncomingQuote[];
}

export interface QuoteStats {
  total: number;
  active: number;
  urgent_active: number;
  accepted: number;
  cancelled: number;
  expired: number;
  offers_total: number;
  pending_offers: number;
  acceptance_rate: number;
}

export type QuoteDispatchState =
  | "pending"
  | "scheduled"
  | "searching"
  | "waiting_seen"
  | "reviewing"
  | "offers"
  | "exhausted"
  | "disabled"
  | "closed";

export interface QuoteDispatchSummary {
  state: QuoteDispatchState;
  status: string;
  round: number;
  latest_round: number;
  max_rounds: number;
  delivered_count: number;
  seen_count: number;
  offers_count: number;
  min_target_deliveries: number;
  next_dispatch_at?: string | null;
  last_dispatched_at?: string | null;
  is_active: boolean;
}
