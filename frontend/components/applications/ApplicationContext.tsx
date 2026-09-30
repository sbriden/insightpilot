"use client";

import { createContext, useContext, useMemo, useState } from "react";

export interface ApplicationAnalysisContext {
  playerId: string | null;
  setPlayerId: (id: string | null) => void;
  season: number | null;
  setSeason: (season: number | null) => void;
  week: number | null;
  setWeek: (week: number | null) => void;
}

const Ctx = createContext<ApplicationAnalysisContext | null>(null);

export function ApplicationContextProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [season, setSeason] = useState<number | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const value = useMemo(
    () => ({
      playerId,
      setPlayerId,
      season,
      setSeason,
      week,
      setWeek,
    }),
    [playerId, season, week]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApplicationContext(): ApplicationAnalysisContext {
  const ctx = useContext(Ctx);
  if (!ctx) {
    return {
      playerId: null,
      setPlayerId: () => undefined,
      season: null,
      setSeason: () => undefined,
      week: null,
      setWeek: () => undefined,
    };
  }
  return ctx;
}
