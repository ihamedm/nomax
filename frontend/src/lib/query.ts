import { useQuery } from "@tanstack/react-query";

import { api, apiWithMeta } from "@/lib/api";

interface QueryOptions {
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number;
}

/** Thin wrapper so pages keep using the existing `api` client with Query caching. */
export function useApi<T>(key: readonly unknown[], path: string, options: QueryOptions = {}) {
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
  options: QueryOptions = {},
) {
  return useQuery<{ data: T; meta: M | undefined }>({
    queryKey: [...key],
    queryFn: () => apiWithMeta<T, M>(path),
    ...options,
  });
}
