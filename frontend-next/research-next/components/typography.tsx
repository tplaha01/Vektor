import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Eyebrow({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        "font-mono text-xs font-semibold uppercase tracking-[0.24em] text-primary",
        className,
      )}
      {...props}
    />
  );
}

export function DisplayHeading({
  className,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h1
      className={cn(
        "text-4xl font-semibold tracking-normal text-foreground md:text-6xl",
        className,
      )}
      {...props}
    />
  );
}

export function BodyCopy({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("font-mono text-sm leading-7 text-muted-foreground", className)}
      {...props}
    />
  );
}
