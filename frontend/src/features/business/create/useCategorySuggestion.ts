import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { CategorySuggestionResult } from "@/types";

const DEBOUNCE_MS = 700;

interface Options {
  title: string;
  description: string;
  enabled: boolean;
}

/**
 * Debounced, abortable suggestion request for the business wizard.
 *
 * The endpoint is advisory: failures are intentionally swallowed so a missing
 * Laya sidecar never blocks manual category selection.
 */
export function useCategorySuggestion({ title, description, enabled }: Options) {
  const [result, setResult] = useState<CategorySuggestionResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const cleanTitle = title.trim();
    const cleanDescription = description.trim();
    if (!enabled || cleanTitle.length < 3 || cleanDescription.length < 10) {
      setResult(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    // Drop a stale card immediately while the next debounced request runs.
    setResult(null);
    const timer = window.setTimeout(() => {
      setLoading(true);
      void api<CategorySuggestionResult>("/categories/suggest", {
        method: "POST",
        body: JSON.stringify({
          title: cleanTitle,
          description: cleanDescription,
        }),
        signal: controller.signal,
      })
        .then((next) => {
          if (!controller.signal.aborted) setResult(next);
        })
        .catch(() => {
          if (!controller.signal.aborted) setResult(null);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [description, enabled, title]);

  return { result, loading };
}
