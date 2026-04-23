import Link from "next/link";
import Image from "next/image";
import { cn } from "@/lib/utils";

interface BlogCardProps {
  url: string;
  title: string;
  description: string;
  date: string;
  thumbnail?: string;
  assetClass?: string;
  filterLabel?: string;
  filterKey?: string;
  showRightBorder?: boolean;
}

export function BlogCard({
  url,
  title,
  description,
  date,
  thumbnail,
  assetClass,
  filterLabel,
  filterKey,
}: BlogCardProps) {
  const isMarketBrief = filterKey === "market-briefs";

  return (
    <Link
      href={url}
      className={cn(
        "group flex h-full flex-col overflow-hidden rounded-[28px] border border-border bg-card/65 shadow-[0_20px_60px_rgba(0,0,0,0.14)] transition-all duration-300 hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_28px_80px_rgba(0,0,0,0.18)]",
        isMarketBrief && "bg-card/85"
      )}
    >
      {thumbnail ? (
        <div className={cn("relative w-full overflow-hidden", isMarketBrief ? "h-48" : "h-56")}>
          <Image
            src={thumbnail}
            alt={title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-[1.03]"
            sizes="(max-width: 768px) 100vw, (max-width: 1280px) 50vw, 33vw"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background/75 via-background/10 to-transparent" />
        </div>
      ) : null}

      <div className="flex flex-1 flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
          {filterLabel ? (
            <span
              className={cn(
                "rounded-full border px-3 py-1",
                isMarketBrief
                  ? "border-sky-400/25 bg-sky-500/10 text-sky-200"
                  : "border-primary/20 bg-primary/10 text-primary"
              )}
            >
              {filterLabel}
            </span>
          ) : null}
          {assetClass ? <span className="text-muted-foreground">{assetClass}</span> : null}
        </div>

        <div className="flex flex-1 flex-col gap-3">
          <h3
            className={cn(
              "text-balance font-semibold tracking-[-0.05em] text-card-foreground transition-colors group-hover:text-primary",
              isMarketBrief ? "text-2xl" : "text-xl"
            )}
          >
            {title}
          </h3>
          <p className="text-sm leading-7 text-muted-foreground md:text-[15px]">{description}</p>
        </div>

        <div className="mt-auto flex items-center justify-between gap-4 pt-2 text-sm text-muted-foreground">
          <time>{date}</time>
          <span className={cn("font-medium", isMarketBrief ? "text-sky-300" : "text-primary")}>Read note</span>
        </div>
      </div>
    </Link>
  );
}
