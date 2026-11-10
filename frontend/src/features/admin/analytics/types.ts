export interface AnalyticsWidgets {
  businesses_total: number;
  businesses_approved: number;
  reviews_total: number;
  quotes_total: number;
  searches_total: number;
  users_total: number;
}

export interface PendingActions {
  businesses: number;
  reviews: number;
  quotes: number;
  total: number;
}

export interface DailyPoint {
  date: string;
  searches: number;
  quote_requests: number;
  quote_responses: number;
  registrations: number;
}

export interface HourlyPoint {
  hour: number;
  searches: number;
  quote_requests: number;
}

export interface RolePoint {
  role: "customer" | "owner" | "admin" | "superadmin";
  label: string;
  count: number;
}

export interface FunnelCounts {
  requests: number;
  sent: number;
  seen: number;
  responded: number;
  chosen: number;
}

export interface FunnelRange {
  range: "today" | "week" | "month" | "all";
  counts: FunnelCounts;
}

export interface AnalyticsOverview {
  widgets: AnalyticsWidgets;
  pending: PendingActions;
  daily: DailyPoint[];
  hourly: HourlyPoint[];
  roles: RolePoint[];
  quote_funnel: FunnelRange[];
}

export interface QuoteWidgets {
  total: number;
  active: number;
  accepted: number;
  cancelled: number;
  expired: number;
  offers_total: number;
  accepted_offers: number;
  pending_offers: number;
  seen_requests: number;
  responded_requests: number;
  chosen_quotes: number;
  seen_rate: number;
  response_rate: number;
  choice_rate: number;
  avg_offer_seconds: number | null;
  avg_choice_seconds: number | null;
}

export interface QuoteStatusPoint {
  status: "active" | "accepted" | "cancelled" | "expired";
  count: number;
}

export interface QuoteTiming {
  key: "sent" | "seen" | "offer" | "choice";
  avg_seconds: number | null;
  count: number;
}

export interface QuoteAnalytics {
  widgets: QuoteWidgets;
  statuses: QuoteStatusPoint[];
  timings: QuoteTiming[];
}

export type MarketStatus =
  | "empty"
  | "no_supply"
  | "no_demand"
  | "urgent"
  | "shortage"
  | "surplus"
  | "balanced";

export interface CategoryDemandRow {
  id: number;
  name: string;
  icon: string;
  slug: string;
  businesses: number;
  searches: number;
  no_results: number;
  quotes: number;
  unanswered_quotes: number;
  demand: number;
  status: MarketStatus;
  status_label: string;
}

export interface SubcategoryDemandRow {
  id: number;
  name: string;
  category_name: string;
  searches: number;
  quotes: number;
  businesses: number;
  demand: number;
}

export interface KeywordRow {
  keyword: string;
  searches: number;
  avg_results: number;
  no_results: number;
}

export interface NoResultKeywordRow {
  keyword: string;
  searches: number;
  category_id: number | null;
  category_name: string;
}

export interface MarketAnalytics {
  categories: CategoryDemandRow[];
  subcategories: SubcategoryDemandRow[];
  keywords: KeywordRow[];
  no_result_keywords: NoResultKeywordRow[];
}

export interface BusinessPerformanceRow {
  id: string;
  slug: string;
  name: string;
  category: { id: number; slug: string; name: string; icon: string } | null;
  subcategory: { id: number; slug: string; name: string; icon: string } | null;
  view_count: number;
  quotes_suggested: number;
  quotes_accepted: number;
  response_rate: number;
  rating_avg: number;
  rating_count: number;
  negative_rate: number;
  status: "critical" | "watch" | "low_response" | "top" | "normal";
  status_label: string;
}

export interface BusinessPerformance {
  items: BusinessPerformanceRow[];
}

export interface MapBusiness {
  id: string;
  name: string;
  slug: string;
  lat: number;
  lng: number;
  category_name: string;
  category_icon: string;
}

export interface MapQuote {
  id: string;
  title: string;
  lat: number;
  lng: number;
  is_urgent: boolean;
  created_at: string | null;
  expires_at: string | null;
  category_name: string;
}

export interface AnalyticsMapData {
  businesses: MapBusiness[];
  quotes: MapQuote[];
  urgent_quotes: MapQuote[];
}

export type ActivityType =
  | "search"
  | "user_registered"
  | "business_created"
  | "review_created"
  | "quote_requested"
  | "quote_offer"
  | "quote_seen"
  | "quote_chosen";

export interface ActivityLog {
  id: string;
  type: ActivityType;
  occurred_at: string | null;
  user_id: string | null;
  user_name: string;
  title: string;
  detail: string | null;
  entity_type: "search" | "user" | "business" | "quote";
  entity_id: string;
}

export interface ActivityLogList {
  items: ActivityLog[];
}

export interface ActivityLogSummary {
  by_type: Array<{ type: ActivityType; count: number }>;
  daily: Array<{ date: string; total: number }>;
  total: number;
}
