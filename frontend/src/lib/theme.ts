import type { CSSProperties } from "react";

import type { DisplayData } from "./types";

export function tournamentTitle(display: DisplayData): string {
  return (
    display.longFormatTitle ||
    [display.titleLine1, display.titleLine2].filter(Boolean).join(" ") ||
    display.tournamentDisplayId ||
    "Tournament"
  );
}

export function themeStyle(display: DisplayData): CSSProperties {
  const left = display.backgroundLeftColor ?? "#1a1a2e";
  const right = display.backgroundRightColor ?? display.primaryColor ?? "#16213e";
  const text = display.titleColor ?? display.backgroundTextColor ?? "#ffffff";

  return {
    ["--t-primary" as string]: display.primaryColor ?? "#7c5cff",
    ["--t-secondary" as string]: display.secondaryColor ?? "#4cc9f0",
    ["--t-text" as string]: text,
    background: `linear-gradient(135deg, ${left}, ${right})`,
    color: text,
  };
}

export function themeAccentStyle(display: DisplayData): CSSProperties {
  return {
    borderColor: display.primaryColor ?? "#7c5cff",
    color: display.titleColor ?? "#fff",
  };
}
