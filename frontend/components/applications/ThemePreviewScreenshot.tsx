"use client";

import {
  getAppThemeDefinition,
  type AppThemeChrome,
  type AppThemeId,
  type AppThemeTokens,
} from "@/components/applications/appTheme";

interface Props {
  themeId: AppThemeId | string;
  appName?: string;
  showLeftNav?: boolean;
  showTopTabs?: boolean;
  showBottomTabs?: boolean;
}

function PreviewChrome({
  tokens,
  chrome,
  appName,
  showLeftNav,
  showTopTabs,
  showBottomTabs,
}: {
  tokens: AppThemeTokens;
  chrome: AppThemeChrome;
  appName: string;
  showLeftNav: boolean;
  showTopTabs: boolean;
  showBottomTabs: boolean;
}) {
  const navItems = ["Daily", "Games", "Markets", "Portfolio"];
  const activeNav = 1;

  return (
    <div
      className="overflow-hidden"
      style={{
        background: tokens.obsidian,
        border: `1px solid ${tokens.border}`,
        borderRadius: chrome.radiusCard,
        boxShadow: chrome.shadowCard,
        fontFamily: chrome.fontSans,
        fontVariantNumeric: chrome.fontVariantNumeric,
      }}
    >
      <div
        className="flex items-center justify-between px-3"
        style={{
          background: tokens.midnight,
          height: "2.25rem",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="flex h-5 w-5 shrink-0 items-center justify-center text-[9px] font-bold"
            style={{
              background: tokens.gradient,
              color: tokens.ctaText,
              borderRadius: chrome.radiusControl,
            }}
          >
            IP
          </span>
          <span
            className="truncate text-[11px] font-semibold"
            style={{
              color: tokens.white,
              fontFamily: chrome.fontDisplay,
              letterSpacing: chrome.headingTracking,
            }}
          >
            {appName}
          </span>
        </div>
        <span
          className="px-2 py-0.5 text-[9px] font-semibold"
          style={{
            background: tokens.deepBlue,
            color: tokens.white,
            border: `1px solid ${tokens.border}`,
            borderRadius: chrome.radiusButton,
            minHeight: "1.5rem",
          }}
        >
          Settings
        </span>
      </div>
      <div
        className="h-px"
        style={{ background: tokens.beam, opacity: chrome.beamOpacity }}
      />

      <div className="flex min-h-[148px]">
        {showLeftNav ? (
          <aside
            className="w-[72px] shrink-0 px-1.5 py-2"
            style={{
              background: tokens.midnight,
              borderRight: `1px solid ${tokens.border}`,
            }}
          >
            <p
              className="mb-1.5 px-1 text-[7px] font-semibold uppercase"
              style={{
                color: tokens.slate,
                letterSpacing: chrome.labelTracking,
              }}
            >
              Betting
            </p>
            <div className="space-y-0.5">
              {navItems.map((label, index) => {
                const selected = index === activeNav;
                return (
                  <div
                    key={label}
                    className="relative px-1.5 py-1 text-[9px] font-medium"
                    style={
                      selected
                        ? {
                            background: chrome.selectionBg,
                            color: tokens.white,
                            borderRadius: chrome.radiusControl,
                            boxShadow: chrome.shadowCard,
                          }
                        : { color: tokens.silver }
                    }
                  >
                    {selected ? (
                      <span
                        className="absolute inset-y-1 left-0 w-[2px] rounded-r"
                        style={{ background: tokens.cyan }}
                      />
                    ) : null}
                    <span className="pl-1">{label}</span>
                  </div>
                );
              })}
            </div>
          </aside>
        ) : null}

        <main
          className="min-w-0 flex-1"
          style={{
            background: tokens.obsidian,
            padding: chrome.space3,
          }}
        >
          {showTopTabs ? (
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span
                className="text-[7px] font-semibold uppercase"
                style={{
                  color: tokens.cyan,
                  letterSpacing: chrome.labelTracking,
                }}
              >
                Sports Betting
              </span>
              <div className="flex gap-1">
                {["Games", "Markets"].map((tab, index) => (
                  <span
                    key={tab}
                    className="px-1.5 py-0.5 text-[9px] font-medium"
                    style={
                      index === 0
                        ? {
                            background: chrome.selectionBg,
                            color: tokens.cyan,
                            borderRadius: chrome.radiusControl,
                            border: `1px solid ${chrome.selectionBorder}`,
                          }
                        : { color: tokens.silver }
                    }
                  >
                    {tab}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          <div
            style={{
              background: tokens.midnight,
              border: `1px solid ${tokens.border}`,
              borderRadius: chrome.radiusCard,
              padding: chrome.cardPadding,
              boxShadow: chrome.shadowCard,
            }}
          >
            <p
              className="text-[7px] font-semibold uppercase"
              style={{
                color: tokens.slate,
                letterSpacing: chrome.labelTracking,
              }}
            >
              Sports Betting
            </p>
            <p
              className="mt-0.5 font-semibold tracking-tight"
              style={{
                color: tokens.white,
                fontSize: chrome.typeCard,
                fontFamily: chrome.fontDisplay,
                letterSpacing: chrome.headingTracking,
              }}
            >
              Games
            </p>
            <p
              className="mt-0.5 leading-snug"
              style={{
                color: tokens.silver,
                fontSize: chrome.typeMeta,
              }}
            >
              Model projections versus market lines.
            </p>

            <div
              className="mt-2 grid grid-cols-2"
              style={{ gap: chrome.space2 }}
            >
              {["KC @ BUF", "DAL @ PHI"].map((matchup, index) => (
                <div
                  key={matchup}
                  style={{
                    background:
                      index === 0 ? chrome.selectionBg : tokens.elevated,
                    border: `1px solid ${
                      index === 0 ? chrome.selectionBorder : tokens.border
                    }`,
                    borderRadius: chrome.radiusControl,
                    padding: chrome.space2,
                  }}
                >
                  <p
                    className="font-semibold"
                    style={{
                      color: tokens.white,
                      fontSize: chrome.typeMeta,
                      fontVariantNumeric: chrome.fontVariantNumeric,
                    }}
                  >
                    {matchup}
                  </p>
                  <p
                    className="mt-0.5"
                    style={{
                      color: index === 0 ? tokens.positive : tokens.cyan,
                      fontSize: "8px",
                      fontVariantNumeric: chrome.fontVariantNumeric,
                    }}
                  >
                    {index === 0 ? "+3.2% edge" : "Pick · -2.5"}
                  </p>
                </div>
              ))}
            </div>

            <button
              type="button"
              className="mt-2 w-full text-[9px] font-semibold"
              style={{
                background: tokens.gradient,
                color: tokens.ctaText,
                borderRadius: chrome.radiusButton,
                minHeight: "1.75rem",
                fontWeight: chrome.buttonWeight,
              }}
            >
              Generate Slate
            </button>
          </div>
        </main>
      </div>

      {showBottomTabs ? (
        <nav
          className="flex items-stretch justify-around gap-0.5 px-1 py-1.5"
          style={{
            background: tokens.midnight,
            borderTop: `1px solid ${tokens.border}`,
            minHeight: "2.75rem",
          }}
        >
          {navItems.map((label, index) => {
            const selected = index === activeNav;
            return (
              <div
                key={label}
                className="flex min-w-0 flex-1 flex-col items-center gap-0.5 px-1 py-1"
                style={
                  selected
                    ? {
                        color: tokens.cyan,
                        background: chrome.selectionBg,
                        borderRadius: chrome.radiusControl,
                      }
                    : { color: tokens.slate }
                }
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background: selected ? tokens.cyan : tokens.slate,
                  }}
                />
                <span className="truncate text-[7px] font-semibold">
                  {label}
                </span>
              </div>
            );
          })}
        </nav>
      ) : null}
    </div>
  );
}

export default function ThemePreviewScreenshot({
  themeId,
  appName = "Sports Betting App",
  showLeftNav = true,
  showTopTabs = true,
  showBottomTabs = false,
}: Props) {
  const definition = getAppThemeDefinition(themeId);
  const tokens = definition.tokens;
  const chrome = definition.chrome;

  return (
    <div
      className="overflow-hidden"
      style={{
        border: `1px solid ${tokens.border}`,
        borderRadius: chrome.radiusCard,
      }}
    >
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{
          background: tokens.panel,
          borderBottom: `1px solid ${tokens.border}`,
        }}
      >
        <p
          className="text-[10px] font-semibold uppercase"
          style={{
            color: tokens.slate,
            letterSpacing: chrome.labelTracking,
          }}
        >
          Preview · {definition.name}
        </p>
        <div className="flex gap-1">
          {definition.swatches.map((swatch) => (
            <span
              key={swatch}
              className="h-2.5 w-2.5 rounded-full"
              style={{
                background: swatch,
                border: `1px solid ${tokens.borderInput}`,
              }}
            />
          ))}
        </div>
      </div>
      <div className="p-3" style={{ background: tokens.deepBlue }}>
        <PreviewChrome
          tokens={tokens}
          chrome={chrome}
          appName={appName}
          showLeftNav={showLeftNav}
          showTopTabs={showTopTabs}
          showBottomTabs={showBottomTabs}
        />
      </div>
    </div>
  );
}
