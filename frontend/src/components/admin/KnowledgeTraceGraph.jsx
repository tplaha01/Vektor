import React, { useMemo } from 'react';

const roleLabel = (value) =>
  String(value || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const shortId = (value) => {
  const text = String(value || '').trim();
  return text ? text.slice(0, 8) : 'n/a';
};

const statusTone = (value) => {
  const status = String(value || '').toLowerCase();
  if (['completed', 'filled', 'published', 'running', 'approved'].includes(status)) return 'ok';
  if (['blocked', 'failed', 'error', 'halted'].includes(status)) return 'bad';
  return 'wait';
};

const summarize = (value, max = 120) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return 'No summary available.';
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

export default function KnowledgeTraceGraph({
  reports = [],
  posts = [],
  lineageRows = [],
  onSelectReport = null,
  onSelectPost = null,
}) {
  const chains = useMemo(() => {
    const kbReports = [...reports]
      .filter((report) => String(report?.surface || 'kb').toLowerCase() === 'kb')
      .sort((a, b) => new Date(b?.published_at || b?.created_at || 0).getTime() - new Date(a?.published_at || a?.created_at || 0).getTime())
      .slice(0, 8);

    return kbReports.map((report) => {
      const lineage = lineageRows.find((row) => {
        const reportIds = Array.isArray(row?.report_ids) ? row.report_ids : [];
        return reportIds.includes(report.report_id) || (report.run_id && row?.run_id === report.run_id);
      }) || null;

      const relatedPosts = posts.filter((post) => {
        const sourceReportId = post?.sourceReportId || post?.metadata?.report_id;
        const lineageBlogIds = Array.isArray(lineage?.blog_post_ids) ? lineage.blog_post_ids : [];
        return sourceReportId === report.report_id || lineageBlogIds.includes(post?.id);
      });

      const consumers = [
        {
          kind: 'consumer',
          label: 'Fund Manager',
          meta: lineage?.run_id ? `run ${shortId(lineage.run_id)}` : 'waiting',
          status: lineage?.fund_manager_status || 'pending',
        },
      ];
      if (lineage?.trader_status && String(lineage.trader_status).toLowerCase() !== 'unknown') {
        consumers.push({
          kind: 'consumer',
          label: 'Trader',
          meta: lineage?.symbol || String(report?.asset_universe?.[0] || 'multi-asset').toUpperCase(),
          status: lineage.trader_status,
        });
      }
      if (relatedPosts.length) {
        consumers.push({
          kind: 'consumer',
          label: 'Blog Writer',
          meta: `${relatedPosts.length} post${relatedPosts.length === 1 ? '' : 's'}`,
          status: 'published',
        });
      }

      const outputs = [];
      if (lineage?.decision_id) {
        outputs.push({
          kind: 'decision',
          id: lineage.decision_id,
          label: `Decision ${shortId(lineage.decision_id)}`,
          meta: Array.isArray(lineage?.blocked_reasons) && lineage.blocked_reasons.length
            ? lineage.blocked_reasons.join(', ')
            : 'decision chain',
          status: lineage?.trader_status || lineage?.fund_manager_status || 'completed',
        });
      }
      if (lineage?.order_id) {
        outputs.push({
          kind: 'order',
          id: lineage.order_id,
          label: `Order ${shortId(lineage.order_id)}`,
          meta: lineage?.symbol || String(report?.asset_universe?.[0] || 'multi-asset').toUpperCase(),
          status: lineage?.trader_status || 'completed',
        });
      }
      relatedPosts.forEach((post) => {
        outputs.push({
          kind: 'blog',
          id: post.id,
          label: post.title,
          meta: `${post.category || 'Research'} | ${post.author_role || 'editorial'}`,
          status: 'published',
          action: () => onSelectPost?.({
            id: post.id,
            kind: 'blog',
            type: 'Blog',
            title: post.title,
            subtitle: `${post.category || 'Research'} | ${post.author_role || 'editorial'}`,
            detail: `${Number(post.views || 0)} views`,
            timestamp: post.published_at || post.created_at,
            href: `/blog?id=${encodeURIComponent(post.id)}`,
            preview: summarize(post.excerpt || post.summary || post.content, 180),
          }),
        });
      });

      return {
        report,
        lineage,
        consumers,
        outputs,
      };
    });
  }, [lineageRows, onSelectPost, posts, reports]);

  if (!chains.length) {
    return <div className="theater-empty">No KB trace chains available yet.</div>;
  }

  return (
    <div className="kb-trace-graph">
      {chains.map((chain) => {
        const report = chain.report;
        const primaryAsset = String(report?.asset_universe?.[0] || 'multi-asset').toUpperCase();
        const providerLine = [report?.provider_used, report?.model_used].filter(Boolean).join(' · ') || 'provider unresolved';
        return (
          <div key={report.report_id} className="kb-trace-chain">
            <div className="kb-trace-column">
              <span className="kb-trace-column-label">Agent finding</span>
              <button
                type="button"
                className="kb-trace-card kb-trace-card-agent"
                onClick={() => onSelectReport?.({
                  id: report.report_id,
                  kind: 'research',
                  type: 'KB Document',
                  title: report.title,
                  subtitle: `${report.agent_role || report.agent_id} | ${primaryAsset}`,
                  detail: providerLine,
                  timestamp: report.published_at || report.created_at,
                  href: report.surface === 'public' ? `/research?report=${encodeURIComponent(report.report_id)}` : '',
                  preview: summarize(report.summary, 180),
                })}
              >
                <strong>{roleLabel(report.agent_role || report.agent_id)}</strong>
                <span>{primaryAsset}</span>
                <small>{summarize(report.findings?.[0] || report.summary, 110)}</small>
              </button>
            </div>

            <div className="kb-trace-arrow" aria-hidden="true">→</div>

            <div className="kb-trace-column">
              <span className="kb-trace-column-label">KB document</span>
              <button
                type="button"
                className="kb-trace-card kb-trace-card-report"
                onClick={() => onSelectReport?.({
                  id: report.report_id,
                  kind: 'research',
                  type: 'KB Document',
                  title: report.title,
                  subtitle: `${report.agent_role || report.agent_id} | ${primaryAsset}`,
                  detail: `${Math.round(Number(report.confidence || 0) * 100)}% confidence`,
                  timestamp: report.published_at || report.created_at,
                  href: report.surface === 'public' ? `/research?report=${encodeURIComponent(report.report_id)}` : '',
                  preview: summarize(report.summary, 180),
                })}
              >
                <strong>{report.title}</strong>
                <span>{providerLine}</span>
                <small>{chain.lineage?.run_id ? `run ${shortId(chain.lineage.run_id)}` : 'unlinked run'}</small>
              </button>
            </div>

            <div className="kb-trace-arrow" aria-hidden="true">→</div>

            <div className="kb-trace-column">
              <span className="kb-trace-column-label">Consumers</span>
              <div className="kb-trace-stack">
                {chain.consumers.map((consumer) => (
                  <div key={`${report.report_id}-${consumer.label}`} className={`kb-trace-card kb-trace-card-consumer tone-${statusTone(consumer.status)}`}>
                    <strong>{consumer.label}</strong>
                    <span>{consumer.meta}</span>
                    <small>{consumer.status}</small>
                  </div>
                ))}
              </div>
            </div>

            <div className="kb-trace-arrow" aria-hidden="true">→</div>

            <div className="kb-trace-column">
              <span className="kb-trace-column-label">Outputs</span>
              <div className="kb-trace-stack">
                {chain.outputs.length ? chain.outputs.map((output) => {
                  const Tag = output.action ? 'button' : 'div';
                  return (
                    <Tag
                      key={`${report.report_id}-${output.kind}-${output.id}`}
                      type={output.action ? 'button' : undefined}
                      className={`kb-trace-card kb-trace-card-output tone-${statusTone(output.status)}`}
                      onClick={output.action || undefined}
                    >
                      <strong>{output.label}</strong>
                      <span>{output.meta}</span>
                      <small>{output.status}</small>
                    </Tag>
                  );
                }) : (
                  <div className="kb-trace-card kb-trace-card-output tone-wait">
                    <strong>No downstream artifact yet</strong>
                    <span>Awaiting decision, order, or blog output</span>
                    <small>{chain.lineage?.run_id ? `run ${shortId(chain.lineage.run_id)}` : 'not linked'}</small>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
