"use client";

import { useRouter, usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
} from "@/components/ui/drawer";

interface TagFilterProps {
  tags: string[];
  selectedTag: string;
  tagCounts?: Record<string, number>;
}

export function TagFilter({ tags, selectedTag, tagCounts }: TagFilterProps) {
  const router = useRouter();
  const pathname = usePathname();

  const handleTagClick = (tag: string) => {
    const params = new URLSearchParams();
    if (tag !== "All") {
      params.set("tag", tag);
    }
    router.push(`${pathname}?${params.toString()}`);
  };

  const DesktopTagFilter = () => (
    <div className="hidden md:flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card/50 p-2">
      {tags.map((tag) => (
        <button
          key={tag}
          onClick={() => handleTagClick(tag)}
          className={`h-9 flex items-center px-1 pl-3 rounded-xl cursor-pointer border text-sm transition-colors ${
            selectedTag === tag
              ? "border-primary bg-primary text-primary-foreground shadow-sm"
              : "border-transparent bg-transparent hover:border-border hover:bg-muted"
          }`}
        >
          <span>{tag}</span>
          {tagCounts?.[tag] && (
            <span
              className={`ml-2 text-xs border rounded-lg h-6 min-w-6 font-medium flex items-center justify-center px-1.5 ${
                selectedTag === tag
                  ? "border-border/40 dark:border-primary-foreground bg-background text-primary"
                  : "border-border bg-background/70 dark:border-border"
              }`}
            >
              {tagCounts[tag]}
            </span>
          )}
        </button>
      ))}
    </div>
  );

  const MobileTagFilter = () => (
    <Drawer>
      <DrawerTrigger className="md:hidden w-full flex items-center justify-between px-4 py-3 border border-border rounded-xl bg-card/50 hover:bg-muted transition-colors">
        <span className="capitalize text-sm font-medium">{selectedTag}</span>
        <ChevronDown className="h-4 w-4" />
      </DrawerTrigger>

      <DrawerContent className="md:hidden">
        <DrawerHeader>
          <h3 className="font-semibold text-sm">Select Category</h3>
        </DrawerHeader>

        <DrawerBody>
          <div className="space-y-2">
            {tags.map((tag) => (
              <button
                key={tag}
                onClick={() => handleTagClick(tag)}
                className={`w-full flex items-center justify-between rounded-xl border px-3 py-3 font-medium cursor-pointer text-sm transition-colors ${
                  selectedTag === tag
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card/40 text-foreground hover:bg-muted"
                }`}
              >
                <span className="w-full text-left">
                  {tag}
                </span>
                {tagCounts?.[tag] && (
                  <span className="flex-shrink-0 ml-2 border border-border rounded-lg h-6 min-w-6 flex items-center justify-center px-1.5">
                    {tagCounts[tag]}
                  </span>
                )}
              </button>
            ))}
          </div>
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  );

  return (
    <>
      <DesktopTagFilter />
      <MobileTagFilter />
    </>
  );
}
