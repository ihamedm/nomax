const GRANT_KEY = "nomax.locationPrompt";
const SHOWS_KEY = "nomax.locationPromptShows";

export const LOCATION_PROMPT_LIMIT = 3;
export const LOCATION_PROMPT_COOLDOWN_MS = 24 * 60 * 60 * 1000;

interface PromptHistory {
  shown: number;
  lastShownAt: number;
}

function readHistory(): PromptHistory {
  try {
    const raw = localStorage.getItem(SHOWS_KEY);
    if (!raw) return { shown: 0, lastShownAt: 0 };
    const parsed = JSON.parse(raw) as Partial<PromptHistory>;
    return {
      shown: Number(parsed.shown) || 0,
      lastShownAt: Number(parsed.lastShownAt) || 0,
    };
  } catch {
    return { shown: 0, lastShownAt: 0 };
  }
}

export function isLocationGranted(): boolean {
  try {
    return localStorage.getItem(GRANT_KEY) === "granted";
  } catch {
    return false;
  }
}

export function markLocationGranted(): void {
  try {
    localStorage.setItem(GRANT_KEY, "granted");
  } catch {
    // Private mode: the prompt may reappear next visit, which is acceptable.
  }
}

/**
 * Automatic prompts are capped at three, one per day. Manual "locate me"
 * actions bypass this check.
 */
export function shouldAutoPrompt(now = Date.now()): boolean {
  if (isLocationGranted()) return false;
  const history = readHistory();
  return (
    history.shown < LOCATION_PROMPT_LIMIT &&
    now - history.lastShownAt >= LOCATION_PROMPT_COOLDOWN_MS
  );
}

/** Counts automatic prompts only; manual asks must not use up the quota. */
export function recordAutoPrompt(now = Date.now()): void {
  const history = readHistory();
  try {
    localStorage.setItem(
      SHOWS_KEY,
      JSON.stringify({ shown: history.shown + 1, lastShownAt: now }),
    );
  } catch {
    // Private mode: the prompt may reappear next visit, which is acceptable.
  }
}
