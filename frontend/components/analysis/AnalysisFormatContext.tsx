"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type CSSProperties,
  type ReactNode,
} from "react";

import {
  analysisTokenCssVars,
  PRODUCT_ANALYSIS_TOKENS,
  setActiveAnalysisTokens,
  tokensForFormat,
  type AnalysisFormat,
  type AnalysisTokens,
} from "@/components/analysis/analysisTokens";

interface AnalysisFormatContextValue {
  format: AnalysisFormat;
  tokens: AnalysisTokens;
}

const AnalysisFormatContext =
  createContext<AnalysisFormatContextValue>({
    format: "product",
    tokens: PRODUCT_ANALYSIS_TOKENS,
  });

export function AnalysisFormatProvider({
  format,
  children,
}: {
  format: AnalysisFormat;
  children: ReactNode;
}) {
  const tokens = useMemo(
    () => tokensForFormat(format),
    [format]
  );

  // Synchronous so children reading snapshotTokens in the same render see app tokens.
  setActiveAnalysisTokens(tokens);

  useEffect(() => {
    setActiveAnalysisTokens(tokens);
    return () => {
      setActiveAnalysisTokens(PRODUCT_ANALYSIS_TOKENS);
    };
  }, [tokens]);

  const cssVars = useMemo(
    () => analysisTokenCssVars(tokens) as CSSProperties,
    [tokens]
  );

  const value = useMemo(
    () => ({ format, tokens }),
    [format, tokens]
  );

  return (
    <AnalysisFormatContext.Provider value={value}>
      <div
        data-analysis-format={format}
        className="ip-analysis-format min-w-0"
        style={cssVars}
      >
        {children}
      </div>
    </AnalysisFormatContext.Provider>
  );
}

export function useAnalysisFormat(): AnalysisFormat {
  return useContext(AnalysisFormatContext).format;
}

export function useAnalysisTokens(): AnalysisTokens {
  return useContext(AnalysisFormatContext).tokens;
}
