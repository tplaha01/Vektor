"use client";

import React from "react";
import { Link2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface CopyHeaderProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level: number;
  children: React.ReactNode;
}

function extractText(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(extractText).join("");
  }

  if (React.isValidElement(node)) {
    return extractText((node as React.ReactElement<{ children?: React.ReactNode }>).props.children);
  }

  return "";
}

function generateSlug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function CopyHeader({ level, children, className, ...props }: CopyHeaderProps) {
  const text = extractText(children).trim();
  const id = generateSlug(text || `section-${level}`);
  const HeadingTag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";

  const copyToClipboard = async () => {
    const url = `${window.location.origin}${window.location.pathname}#${id}`;
    window.history.replaceState({}, "", `#${id}`);

    const element = document.getElementById(id);
    if (element) {
      const offset = 96;
      const top = element.getBoundingClientRect().top + window.pageYOffset - offset;
      window.scrollTo({ top, behavior: "smooth" });
    }

    try {
      await navigator.clipboard.writeText(url);
    } catch (error) {
      console.error(error);
      const textArea = document.createElement("textarea");
      textArea.value = url;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
    }
  };

  const showCopyAction = level <= 3;

  return (
    <HeadingTag
      id={id}
      className={cn(
        "group scroll-mt-28 text-foreground",
        showCopyAction && "flex items-center gap-3",
        className
      )}
      {...props}
    >
      <span>{children}</span>
      {showCopyAction ? (
        <button
          type="button"
          onClick={copyToClipboard}
          className="inline-flex size-8 items-center justify-center rounded-full border border-transparent bg-transparent text-muted-foreground opacity-0 transition hover:border-border hover:bg-muted hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
          aria-label={`Copy link to ${text}`}
          title="Copy link to this section"
        >
          <Link2 className="h-4 w-4" />
        </button>
      ) : null}
    </HeadingTag>
  );
}
