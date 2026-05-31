import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import PaperPage, { dynamic, generateMetadata } from "./page";
import { siteConfig } from "@/lib/site";
import type { LiveResearchReport } from "@/lib/types";

globalThis.React = React;

const subject: LiveResearchReport = {
  report_id: "report-1",
  agent_id: "research_agent",
  agent_role: "researcher",
  surface: "public",
  run_id: "run-1",
  title: "Backend Research Report",
  summary: "Research summary returned by the backend report detail endpoint.",
  findings: ["First backend finding.", "Second backend finding."],
  asset_universe: ["NVDA", "MSFT"],
  confidence: 0.82,
  created_at: "2026-05-29T15:30:00Z",
  published_at: "2026-05-29T15:30:00Z",
  status: "published",
  views: 12,
  provider_used: "github",
  model_used: "gpt-4.1-mini",
  ai_trace: {
    provider: "github",
    model: "gpt-4.1-mini",
    fallback_used: false,
  },
  provenance: {
    data_sources: ["research:source-1"],
    thesis_id: "thesis-1",
    decision_ids: ["decision-1"],
    policy_gates_applied: ["risk-1"],
  },
};

const related: LiveResearchReport = {
  ...subject,
  report_id: "report-2",
  run_id: "run-2",
  title: "Related Backend Report",
  summary: "Related report sharing an asset with the subject report.",
  asset_universe: ["NVDA"],
};

const originalFetch = globalThis.fetch;

function response(payload: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(payload), {
    status: init?.status || 200,
    headers: {
      "content-type": "application/json",
      ...(init?.headers || {}),
    },
  });
}

function installFetch({ missing = false } = {}) {
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes("/api/research/reports/")) {
      return missing ? response({ detail: "research_report_not_found" }, { status: 404 }) : response(subject);
    }

    if (url.includes("/api/research/reports?")) {
      return response({
        reports: [subject, related],
        total: 2,
        limit: 80,
        offset: 0,
      });
    }

    return response({ detail: "unexpected_url" }, { status: 500 });
  }) as typeof fetch;
}

async function renderPaper(slug = subject.report_id) {
  const element = await PaperPage({ params: { slug } });
  return renderToStaticMarkup(element);
}

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("paper detail route", () => {
  it("renders a valid backend report", async () => {
    installFetch();
    const html = await renderPaper();

    assert.match(html, /Backend Research Report/);
    assert.match(html, /Research index/);
    assert.match(html, /Abstract/);
    assert.match(html, /Research summary returned by the backend report detail endpoint/);
    assert.match(html, /Research Body/);
    assert.match(html, /First backend finding/);
    assert.match(html, /Algorithm Signal Trace/);
    assert.match(html, /Related Papers/);
    assert.match(html, /Paper Metadata/);
  });

  it("throws notFound for an invalid backend report id", async () => {
    installFetch({ missing: true });

    await assert.rejects(
      () => renderPaper("missing-report"),
      (error) =>
        error instanceof Error &&
        "digest" in error &&
        error.digest === "NEXT_NOT_FOUND",
    );
  });

  it("keeps backend report ids request-time dynamic", () => {
    assert.equal(dynamic, "force-dynamic");
  });

  it("generates metadata from the backend report detail", async () => {
    installFetch();
    const metadata = await generateMetadata({ params: { slug: subject.report_id } });

    assert.equal(metadata.title, subject.title);
    assert.equal(metadata.description, subject.summary);
    assert.deepEqual(metadata.authors, [{ name: subject.agent_id }]);
    assert.deepEqual(metadata.openGraph, {
      title: subject.title,
      description: subject.summary,
      type: "article",
      url: `${siteConfig.url}/paper/${encodeURIComponent(subject.report_id)}`,
      publishedTime: subject.published_at,
      modifiedTime: subject.created_at,
      authors: [subject.agent_id],
      tags: ["NVDA", "MSFT", "research:source-1", "risk-1", "decision-1"],
    });
  });

  it("generates not-found metadata for an unknown report", async () => {
    installFetch({ missing: true });
    assert.deepEqual(await generateMetadata({ params: { slug: "missing-report" } }), {
      title: "Paper not found",
    });
  });

  it("renders related reports from the backend report list", async () => {
    installFetch();
    const html = await renderPaper();

    assert.match(html, /href="\/paper\/report-2"/);
    assert.match(html, /Related Backend Report/);
  });

  it("renders signal trace, metadata, assets, and tags from backend fields", async () => {
    installFetch();
    const html = await renderPaper();

    assert.match(html, /provider/);
    assert.match(html, /gpt-4.1-mini/);
    assert.match(html, /data sources/);
    assert.match(html, /research:source-1/);
    assert.match(html, /Published/);
    assert.match(html, /May 29, 2026/);
    assert.match(html, /Provider/);
    assert.match(html, /github/);
    assert.match(html, /Model/);
    assert.match(html, /NVDA/);
    assert.match(html, /MSFT/);
    assert.match(html, /risk-1/);
    assert.match(html, /decision-1/);
  });
});
