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
  showRightBorder = true,
}: BlogCardProps) {
  const isMarketBrief = filterKey === "market-briefs";
  return (
    <Link
      href={url}
      className={cn(
        "group block relative before:absolute before:-left-0.5 before:top-0 before:z-10 before:h-screen before:w-px before:bg-border before:content-[''] after:absolute after:-top-0.5 after:left-0 after:z-0 after:h-px after:w-screen after:bg-border after:content-['']",
        showRightBorder && "md:border-r border-border border-b-0"
      )}
    >
      <div className={cn("flex h-full flex-col", isMarketBrief ? "bg-card/30" : "bg-background")}>
        {thumbnail && (
          <div className={cn("relative w-full overflow-hidden", isMarketBrief ? "h-44" : "h-52")}>
            <Image
              src={thumbnail}
              alt={title}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            />
          </div>
        )}

        <div className={cn("flex flex-1 flex-col gap-3 p-6", isMarketBrief ? "border-t border-border/60" : "")}>
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
            {filterLabel ? (
              <span className={cn(
                "rounded-full border px-2.5 py-1",
                isMarketBrief
                  ? "border-sky-400/30 bg-sky-500/10 text-sky-200"
                  : "border-emerald-400/25 bg-emerald-500/10 text-emerald-200"
              )}>
                {filterLabel}
              </span>
            ) : null}
            {assetClass ? (
              <span className="text-muted-foreground">{assetClass}</span>
            ) : null}
          </div>
          <h3 className={cn(
            "font-semibold text-card-foreground group-hover:underline underline-offset-4",
            isMarketBrief ? "text-2xl tracking-tight" : "text-xl"
          )}>
            {title}
          </h3>
          <p className={cn(
            "text-muted-foreground",
            isMarketBrief ? "text-[15px] leading-6" : "text-sm leading-6"
          )}>
            {description}
          </p>
          <div className="mt-auto flex items-center justify-between pt-2">
            <time className="block text-sm font-medium text-muted-foreground">
              {date}
            </time>
            <span className={cn(
              "text-xs uppercase tracking-[0.18em]",
              isMarketBrief ? "text-sky-300" : "text-emerald-300"
            )}>
              {isMarketBrief ? "Session Note" : "Research Note"}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}
