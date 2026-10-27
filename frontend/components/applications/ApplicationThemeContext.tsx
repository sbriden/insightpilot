"use client";

import {
  createContext,
  useContext,
  useMemo,
  type CSSProperties,
  type ReactNode,
} from "react";

import {
  appThemeCssVars,
  DEFAULT_APP_THEME_ID,
  getAppThemeDefinition,
  getAppThemeTokens,
  type AppThemeChrome,
  type AppThemeDefinition,
  type AppThemeId,
  type AppThemeTokens,
  normalizeAppThemeId,
} from "@/components/applications/appTheme";

interface ApplicationThemeContextValue {
  themeId: AppThemeId;
  definition: AppThemeDefinition;
  tokens: AppThemeTokens;
  chrome: AppThemeChrome;
}

const defaultDefinition = getAppThemeDefinition(DEFAULT_APP_THEME_ID);

const ApplicationThemeContext =
  createContext<ApplicationThemeContextValue>({
    themeId: DEFAULT_APP_THEME_ID,
    definition: defaultDefinition,
    tokens: defaultDefinition.tokens,
    chrome: defaultDefinition.chrome,
  });

export function ApplicationThemeProvider({
  themeId,
  children,
}: {
  themeId?: string | null;
  children: ReactNode;
}) {
  const id = normalizeAppThemeId(themeId);
  const definition = useMemo(() => getAppThemeDefinition(id), [id]);
  const tokens = definition.tokens;
  const chrome = definition.chrome;
  const cssVars = useMemo(
    () => appThemeCssVars(tokens, id) as CSSProperties,
    [tokens, id]
  );
  const value = useMemo(
    () => ({ themeId: id, definition, tokens, chrome }),
    [id, definition, tokens, chrome]
  );

  return (
    <ApplicationThemeContext.Provider value={value}>
      <div
        className="min-h-screen"
        data-app-theme={id}
        data-app-scheme={definition.scheme}
        style={cssVars}
      >
        {children}
      </div>
    </ApplicationThemeContext.Provider>
  );
}

export function useAppTheme(): AppThemeTokens {
  return useContext(ApplicationThemeContext).tokens;
}

export function useAppThemeChrome(): AppThemeChrome {
  return useContext(ApplicationThemeContext).chrome;
}

export function useAppThemeId(): AppThemeId {
  return useContext(ApplicationThemeContext).themeId;
}

export function useAppThemeDefinition(): AppThemeDefinition {
  return useContext(ApplicationThemeContext).definition;
}
