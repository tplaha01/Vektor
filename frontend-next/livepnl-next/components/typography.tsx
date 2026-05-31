import type { PropsWithChildren } from "react";

export function Eyebrow({ children }: PropsWithChildren) {
  return (
    <p className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary">
      {children}
    </p>
  );
}

export function SectionTitle({ children }: PropsWithChildren) {
  return <h2 className="text-2xl font-semibold text-foreground">{children}</h2>;
}
