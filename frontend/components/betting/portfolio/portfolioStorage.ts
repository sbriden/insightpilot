import type { BettingPortfolioPosition } from "@/services/api";

const STORAGE_KEY = "ip-betting-portfolio:v1";

export type StoredBettingPortfolio = {
  positions: BettingPortfolioPosition[];
  savedAt: string | null;
};

export function loadBettingPortfolio(): StoredBettingPortfolio {
  if (typeof window === "undefined") {
    return { positions: [], savedAt: null };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { positions: [], savedAt: null };
    }
    const parsed = JSON.parse(raw) as StoredBettingPortfolio;
    return {
      positions: Array.isArray(parsed.positions)
        ? parsed.positions
        : [],
      savedAt: parsed.savedAt || null,
    };
  } catch {
    return { positions: [], savedAt: null };
  }
}

export function saveBettingPortfolio(
  positions: BettingPortfolioPosition[]
): string {
  const savedAt = new Date().toISOString();
  const payload: StoredBettingPortfolio = { positions, savedAt };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  return savedAt;
}

export function exportBettingPortfolio(
  positions: BettingPortfolioPosition[]
): void {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          positions,
          exportedAt: new Date().toISOString(),
        },
        null,
        2
      ),
    ],
    { type: "application/json" }
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `insightpilot-betting-portfolio.json`;
  link.click();
  URL.revokeObjectURL(url);
}
