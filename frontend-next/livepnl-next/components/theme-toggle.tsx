"use client";

import { Monitor } from "lucide-react";

export function ThemeToggle() {
  return (
    <span className="inline-flex h-8 items-center gap-2 rounded-full border border-border bg-card/60 px-3 font-mono text-xs text-muted-foreground">
      <Monitor className="size-3.5" aria-hidden="true" />
      Dark
    </span>
  );
}
