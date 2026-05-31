import { siteConfig } from "@/lib/site";

export default function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="vektor-section flex flex-col gap-3 py-6 font-mono text-xs text-muted-foreground md:flex-row md:items-center md:justify-between">
        <p>{siteConfig.name} / paper portfolio transparency</p>
        <div className="flex flex-wrap gap-3">
          <a href={siteConfig.links.research} className="hover:text-primary">
            Research
          </a>
          <a href={siteConfig.links.blog} className="hover:text-primary">
            Blog
          </a>
          <a href={siteConfig.links.admin} className="hover:text-primary">
            Admin
          </a>
        </div>
      </div>
    </footer>
  );
}
