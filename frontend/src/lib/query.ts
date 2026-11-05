import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import { api, apiWithMeta } from "@/lib/api";

/**
 * Query options accepted by the `useApi` helpers: everything TanStack accepts
 * except the key/fn, which the helper owns. Keeps `placeholderData`,
 * `refetchOnWindowFocus`, etc. available to callers.
 */
type QueryOptions<T> = Omit<UseQueryOptions<T>, "queryKey" | "queryFn">;

/** Thin wrapper so pages keep using the existing `api` client with Query caching. */
export function useApi<T>(
  key: readonly unknown[],
  path: string,
  options: QueryOptions<T> = {},
) {
  return useQuery<T>({
    queryKey: [...key],
    queryFn: () => api<T>(path),
    ...options,
  });
}

/** Same as `useApi`, but keeps the envelope `meta` (used by paginated admin tables). */
export function useApiWithMeta<T, M>(
  key: readonly unknown[],
  path: string,
  options: QueryOptions<{ data: T; meta: M | undefined }> = {},
) {
  return useQuery<{ data: T; meta: M | undefined }>({
    queryKey: [...key],
    queryFn: () => apiWithMeta<T, M>(path),
    ...options,
  });
}
