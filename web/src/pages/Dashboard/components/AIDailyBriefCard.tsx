import React, { useEffect, useState, useCallback } from 'react';
import { Sparkles, ArrowRight, Newspaper, Clock, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import TopicBadge from './TopicBadge';
import { getTodayInsights } from '../utils/api';

interface InsightTopic {
  text: string;
  trend: 'up' | 'down' | 'neutral';
}

interface Insight {
  market_insight_id: string;
  type: string;
  headline: string;
  summary: string;
  completed_at?: string;
  topics?: InsightTopic[];
  [key: string]: unknown;
}

interface AIDailyBriefCardProps {
  onReadFull?: (marketInsightId: string) => void;
}

interface TypeConfigEntry {
  label: string;
  accent: string;
}

// Module-level cache (survives navigation, clears on page refresh)
let insightsCache: Insight[] | null = null;

const TYPE_CONFIG: Record<string, TypeConfigEntry> = {
  pre_market: { label: 'Pre-Market', accent: 'var(--color-profit)' },
  market_update: { label: 'Market Update', accent: 'var(--color-accent-primary)' },
  post_market: { label: 'Post-Market', accent: '#a78bfa' },
};

function formatRelativeTime(timestamp: string | undefined): string {
  if (!timestamp) return '';
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function formatTime(timestamp: string | undefined): string {
  if (!timestamp) return '';
  try {
    const d = new Date(timestamp);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

function AIDailyBriefCard({ onReadFull }: AIDailyBriefCardProps) {
  const [insights, setInsights] = useState<Insight[]>(insightsCache || []);
  const [loading, setLoading] = useState(!insightsCache);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (insightsCache) return;
    let cancelled = false;
    getTodayInsights().then((data) => {
      if (cancelled) return;
      const typedData = data as unknown as Insight[];
      if (typedData?.length) {
        insightsCache = typedData;
        setInsights(typedData);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const latest: Insight | null = insights[0] || null;
  const older = insights.slice(1);

  const handleCardClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    // Don't expand if clicking the CTA button or a link
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('a')) return;
    if (older.length > 0) setExpanded((v) => !v);
  }, [older.length]);

  // Loading skeleton
  if (loading) {
    return (
      <div
        className="relative rounded-3xl overflow-hidden border p-8"
        style={{
          borderColor: 'var(--color-accent-overlay)',
          background: 'var(--color-bg-card)',
        }}
      >
        <div className="animate-pulse space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-40 rounded-full" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
            <div className="h-4 w-16 rounded" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
          </div>
          <div className="h-8 w-3/4 rounded" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
          <div className="h-4 w-full rounded" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
          <div className="h-4 w-2/3 rounded" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
          <div className="flex gap-3">
            <div className="h-8 w-28 rounded-lg" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
            <div className="h-8 w-24 rounded-lg" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
            <div className="h-8 w-20 rounded-lg" style={{ backgroundColor: 'var(--color-bg-hover)' }} />
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!latest) {
    return (
      <div
        className="relative rounded-3xl overflow-hidden border p-8 flex items-center justify-center"
        style={{
          borderColor: 'var(--color-accent-overlay)',
          background: 'var(--color-bg-card)',
          minHeight: 200,
        }}
      >
        <div className="text-center">
          <Newspaper size={40} className="mx-auto mb-3 opacity-30" style={{ color: 'var(--color-accent-primary)' }} />
          <p style={{ color: 'var(--color-text-secondary)' }}>Generating first insight...</p>
        </div>
      </div>
    );
  }

  const updatedAgo = formatRelativeTime(latest.completed_at);
  const topics = latest.topics || [];
  const latestType = TYPE_CONFIG[latest.type] || TYPE_CONFIG.market_update;

  return (
    <div className="relative">
      {/* Stacked card shadows (visible only when collapsed and there are older insights) */}
      {!expanded && older.length > 0 && (
        <>
          <div
            className="absolute left-3 right-3 bottom-0 h-full rounded-3xl border pointer-events-none"
            style={{
              borderColor: 'var(--color-border-muted)',
              background: 'var(--color-bg-card)',
              transform: 'translateY(8px) scale(0.98)',
              opacity: 0.6,
              zIndex: 0,
            }}
          />
          {older.length > 1 && (
            <div
              className="absolute left-6 right-6 bottom-0 h-full rounded-3xl border pointer-events-none"
              style={{
                borderColor: 'var(--color-border-muted)',
                background: 'var(--color-bg-card)',
                transform: 'translateY(16px) scale(0.96)',
                opacity: 0.35,
                zIndex: -1,
              }}
            />
          )}
        </>
      )}

      {/* Main card */}
      <motion.div
        layout
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="relative group rounded-3xl overflow-hidden border"
        style={{
          borderColor: 'var(--color-accent-overlay)',
          background: `linear-gradient(135deg, var(--color-bg-card) 0%, var(--color-bg-card) 60%, var(--color-accent-soft) 100%)`,
          cursor: older.length > 0 ? 'pointer' : 'default',
          zIndex: 1,
        }}
        onClick={handleCardClick}
      >
        {/* Decorative brain icon */}
        <div className="absolute top-0 right-0 p-6 opacity-20 group-hover:opacity-40 transition-opacity pointer-events-none">
          <Newspaper size={120} style={{ color: 'var(--color-accent-primary)' }} />
        </div>

        <div className="relative z-10 p-8 flex flex-col md:flex-row gap-8 items-start">
          <div className="flex-1">
            {/* Badge + updated */}
            <div className="flex items-center gap-2 mb-4">
              <div
                className="px-3 py-1 rounded-full border flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
                style={{
                  backgroundColor: 'var(--color-accent-soft)',
                  borderColor: 'var(--color-accent-overlay)',
                  color: 'var(--color-accent-light)',
                }}
              >
                <Sparkles size={12} />
                AI Generated Insight
              </div>
              {updatedAgo && (
                <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  Updated {updatedAgo}
                </span>
              )}
            </div>

            {/* Headline */}
            <h2
              className="text-3xl font-bold mb-4 leading-tight"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {latest.headline}
            </h2>

            {/* Summary */}
            <p
              className="mb-6 leading-relaxed max-w-2xl"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {latest.summary}
            </p>

            {/* Topic badges */}
            <div className="flex flex-wrap gap-3">
              {topics.map((topic) => (
                <TopicBadge key={topic.text} text={topic.text} trend={topic.trend} />
              ))}
            </div>
          </div>

          {/* CTA + stack indicator */}
          <div className="w-full md:w-auto flex flex-col items-end justify-end gap-3 self-stretch">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReadFull?.(latest.market_insight_id);
              }}
              className="group/btn flex items-center gap-2 px-6 py-3 rounded-xl font-semibold transition-colors shadow-lg"
              style={{
                backgroundColor: 'var(--color-btn-primary-bg, var(--color-accent-primary))',
                color: 'var(--color-btn-primary-text, #fff)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              Read Full Brief
              <ArrowRight size={16} className="group-hover/btn:translate-x-1 transition-transform" />
            </button>

            {/* Stack indicator */}
            {older.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setExpanded((v) => !v);
                }}
                className="flex items-center gap-1.5 text-xs transition-colors"
                style={{ color: 'var(--color-text-tertiary)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-tertiary)')}
              >
                <Clock size={12} />
                {older.length} earlier today
                <ChevronDown
                  size={14}
                  className="transition-transform"
                  style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
                />
              </button>
            )}
          </div>
        </div>

        {/* Expanded timeline — inside the main card */}
        <AnimatePresence>
          {expanded && older.length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
              className="overflow-hidden"
            >
              <div
                className="mx-8 mb-6 border-t pt-5"
                style={{ borderColor: 'var(--color-border-muted)' }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <span
                    className="text-[10px] font-semibold uppercase tracking-wider"
                    style={{ color: 'var(--color-text-tertiary)' }}
                  >
                    Earlier Insights
                  </span>
                </div>

                <div className="space-y-1">
                  {older.map((item) => {
                    const cfg = TYPE_CONFIG[item.type] || TYPE_CONFIG.market_update;
                    return (
                      <button
                        key={item.market_insight_id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onReadFull?.(item.market_insight_id);
                        }}
                        className="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-left transition-colors group/item"
                        style={{ color: 'var(--color-text-secondary)' }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        {/* Time */}
                        <span
                          className="text-xs font-medium shrink-0 w-16 text-right tabular-nums"
                          style={{ color: 'var(--color-text-tertiary)' }}
                        >
                          {formatTime(item.completed_at)}
                        </span>

                        {/* Timeline dot */}
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: cfg.accent }}
                        />

                        {/* Type badge */}
                        <span
                          className="text-[10px] font-semibold uppercase tracking-wider shrink-0 px-2 py-0.5 rounded"
                          style={{
                            color: cfg.accent,
                            backgroundColor: `color-mix(in srgb, ${cfg.accent} 15%, transparent)`,
                          }}
                        >
                          {cfg.label}
                        </span>

                        {/* Headline */}
                        <span
                          className="text-sm truncate flex-1 group-hover/item:text-[var(--color-text-primary)] transition-colors"
                        >
                          {item.headline}
                        </span>

                        <ArrowRight
                          size={14}
                          className="shrink-0 opacity-0 group-hover/item:opacity-60 transition-opacity"
                          style={{ color: 'var(--color-text-tertiary)' }}
                        />
                      </button>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Bottom padding for stacked shadow effect */}
      {!expanded && older.length > 0 && (
        <div style={{ height: older.length > 1 ? 16 : 8 }} />
      )}
    </div>
  );
}

export default AIDailyBriefCard;
