import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Briefcase,
  CalendarDays,
  CircleDot,
  ClipboardCheck,
  Columns2,
  GitCompare,
  LineChart,
  Newspaper,
  Shield,
  Sparkles,
  Table2,
  Target,
  TrendingUp,
  Trophy,
  Wand2,
  Wallet,
} from "lucide-react";

import { getRegistryAnalysis } from "@/lib/analysisRegistry";

const BY_KEY: Record<string, LucideIcon> = {
  "fantasy.player_table": Table2,
  "fantasy.player_scatter": Activity,
  "fantasy.player_compare": GitCompare,
  "fantasy.team_stats": Shield,
  "fantasy.player_stats": BarChart3,
  "fantasy.player_usage": TrendingUp,
  "fantasy.player_matchups": Target,
  "fantasy.player_news": Newspaper,
  "dfs.analyzer": Sparkles,
  "dfs.optimizer": Wand2,
  "dfs.portfolio": Briefcase,
  "betting.daily_slate": CalendarDays,
  "betting.games": Trophy,
  "betting.markets": LineChart,
  "betting.portfolio": Wallet,
  "betting.results": ClipboardCheck,
};

const BY_RUNTIME: Record<string, LucideIcon> = {
  player_overview: Columns2,
  player_snapshot: BarChart3,
  dfs_analyzer: Sparkles,
  sports_betting: Trophy,
};

export function getAnalysisNavIcon(
  analysisKey: string
): LucideIcon {
  if (BY_KEY[analysisKey]) {
    return BY_KEY[analysisKey];
  }
  const meta = getRegistryAnalysis(analysisKey);
  if (meta?.runtime && BY_RUNTIME[meta.runtime]) {
    return BY_RUNTIME[meta.runtime];
  }
  return CircleDot;
}

export function shortAnalysisLabel(name: string): string {
  const trimmed = name.trim();
  if (trimmed.length <= 12) return trimmed;
  const withoutPrefix = trimmed
    .replace(/^(DFS|NFL|CFB)\s+/i, "")
    .replace(/\s+&\s+/g, " ");
  if (withoutPrefix.length <= 12) return withoutPrefix;
  return `${withoutPrefix.slice(0, 11)}…`;
}
