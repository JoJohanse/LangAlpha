import React, { useState, useMemo } from 'react';
import { Clock, Search, X, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useIsMobile } from '@/hooks/useIsMobile';
import { useFormatTime } from '@/hooks/useFormatTime';
import { parseServerDate } from '@/lib/dateTime';
import type { MarketEvent } from '../utils/eventsApi';

interface NewsItem {
  id?: string | number;
  title: string;
  source?: string;
  time?: string;
  publishedAt?: string | null;
  image?: string | null;
  favicon?: string | null;
  tickers?: string[];
  isHot?: boolean;
  articleUrl?: string | null;
  sector?: string | null;
  topic?: string | null;
  region?: string | null;
  tags?: string[];
  importanceScore?: number;
}

type DateRangeKey = 'all' | '1h' | '6h' | '24h' | '7d';
type FeedMode = 'events' | 'quick';
type EventViewKey = 'all' | 'hot';

interface DateRangeDef {
  key: DateRangeKey;
  label: string;
}

const DATE_RANGES: DateRangeDef[] = [
  { key: 'all', label: 'All' },
  { key: '1h', label: '1H' },
  { key: '6h', label: '6H' },
  { key: '24h', label: '24H' },
  { key: '7d', label: '7D' },
];

function parseRelativeTime(timeStr: string | undefined | null): number | null {
  if (!timeStr) return null;
  const now = Date.now();
  const m = timeStr.match(/^(\d+)\s*(min|hr|hrs|hour|hours|day|days)/i);
  if (!m) return now;
  const val = parseInt(m[1], 10);
  const unit = m[2].toLowerCase();
  if (unit === 'min') return now - val * 60 * 1000;
  if (unit.startsWith('hr') || unit.startsWith('hour')) return now - val * 3600 * 1000;
  if (unit.startsWith('day')) return now - val * 86400 * 1000;
  return now;
}

function getDateRangeCutoff(key: DateRangeKey): number {
  if (key === 'all') return 0;
  const now = Date.now();
  switch (key) {
    case '1h': return now - 3600 * 1000;
    case '6h': return now - 6 * 3600 * 1000;
    case '24h': return now - 24 * 3600 * 1000;
    case '7d': return now - 7 * 86400 * 1000;
    default: return 0;
  }
}

function parseDateTimeLocal(value: string): number | null {
  if (!value) return null;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? null : ts;
}

interface NewsRowProps {
  item: NewsItem;
  idx: number;
  onNewsClick?: (id: string | number, articleUrl?: string | null) => void;
  onAskNews?: (id: string | number) => void;
  skipAnimation?: boolean;
}

function NewsRow({ item, idx, onNewsClick, onAskNews, skipAnimation }: NewsRowProps) {
  const sentiment = item.isHot ? 'positive' : 'neutral';
  const sentimentColor =
    sentiment === 'positive'
      ? 'var(--color-profit)'
      : 'var(--color-text-secondary)';
  const tickers = (item.tickers?.length ?? 0) > 0 ? item.tickers! : null;

  const Wrapper = skipAnimation ? 'div' : motion.div;
  const motionProps = skipAnimation ? {} : {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { delay: Math.min(idx, 10) * 0.05 },
  };

  return (
    <Wrapper
      {...motionProps}
      onClick={() => item.id != null && onNewsClick?.(item.id, item.articleUrl)}
      className="group flex items-center gap-3 sm:gap-4 px-2 py-2.5 sm:p-3 rounded-lg sm:rounded-xl border border-transparent transition-all cursor-pointer"
      style={{ backgroundColor: 'transparent' }}
      onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
        e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
        e.currentTarget.style.borderColor = 'var(--color-border-muted)';
      }}
      onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
        e.currentTarget.style.backgroundColor = 'transparent';
        e.currentTarget.style.borderColor = 'transparent';
      }}
    >
      {/* Thumbnail — hidden on mobile */}
      {item.image && (
        <div className="relative h-16 w-24 flex-shrink-0 overflow-hidden rounded-lg hidden sm:block">
          <img
            src={item.image}
            alt=""
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: sentimentColor }}
          />
          {item.favicon && (
            <img
              src={item.favicon}
              alt=""
              className="w-4 h-4 rounded flex-shrink-0"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          )}
          {item.source && (
            <span
              className="text-[10px] font-medium uppercase tracking-wide"
              style={{ color: 'var(--color-accent-light)' }}
            >
              {item.source}
            </span>
          )}
          <span
            className="text-xs flex items-center gap-1"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <Clock size={10} /> {item.time}
          </span>
        </div>
        <h3
          className="text-sm font-medium truncate transition-colors"
          style={{ color: 'var(--color-text-primary)' }}
          title={item.title}
        >
          {item.title}
        </h3>
        {tickers && (
          <div className="flex items-center gap-1.5 mt-1">
            {tickers.slice(0, 4).map((t) => (
              <span
                key={t}
                className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor: 'var(--color-accent-soft)',
                  color: 'var(--color-accent-light)',
                }}
              >
                {t}
              </span>
            ))}
            {tickers.length > 4 && (
              <span className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                +{tickers.length - 4}
              </span>
            )}
          </div>
        )}
        {item.id != null && (
          <div className="mt-1.5">
            <button
              type="button"
              className="text-[11px] px-2 py-0.5 rounded border"
              style={{ color: 'var(--color-accent-light)', borderColor: 'var(--color-border-muted)' }}
              onClick={(e) => {
                e.stopPropagation();
                onAskNews?.(item.id as string | number);
              }}
            >
              Ask AI
            </button>
          </div>
        )}
      </div>
    </Wrapper>
  );
}

function SkeletonRows({ count = 6 }: { count?: number }) {
  return Array.from({ length: count }).map((_, idx) => (
    <div key={idx} className="flex items-center gap-4 p-3 animate-pulse">
      <div
        className="h-16 w-24 flex-shrink-0 rounded-lg hidden sm:block"
        style={{ backgroundColor: 'var(--color-border-default)' }}
      />
      <div className="flex-1 min-w-0">
        <div className="h-3 rounded mb-2" style={{ backgroundColor: 'var(--color-border-default)', width: '40%' }} />
        <div className="h-4 rounded" style={{ backgroundColor: 'var(--color-border-default)', width: `${60 + (idx % 3) * 15}%` }} />
      </div>
    </div>
  ));
}

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  if (hasFilters) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          No news matching your filters
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-16">
      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        No news available
      </p>
    </div>
  );
}

interface NewsFeedCardProps {
  eventItems?: MarketEvent[];
  eventLoading?: boolean;
  hotEvents?: MarketEvent[];
  hotEventsLoading?: boolean;
  quickItems?: NewsItem[];
  quickLoading?: boolean;
  onNewsClick?: (id: string | number, articleUrl?: string | null) => void;
  onAskNews?: (id: string | number) => void;
  onAskEvent?: (eventId: string) => void;
  onEventClick?: (eventId: string) => void;
}

function NewsFeedCard({
  eventItems = [],
  eventLoading = false,
  hotEvents = [],
  hotEventsLoading = false,
  quickItems = [],
  quickLoading = false,
  onNewsClick,
  onAskNews,
  onAskEvent,
  onEventClick,
}: NewsFeedCardProps) {
  const formatTime = useFormatTime();
  const [mode, setMode] = useState<FeedMode>('events');
  const [eventView, setEventView] = useState<EventViewKey>('hot');
  const [tickerFilter, setTickerFilter] = useState('');
  const [sectorFilter, setSectorFilter] = useState('');
  const [topicFilter, setTopicFilter] = useState('');
  const [dateRange, setDateRange] = useState<DateRangeKey>('all');
  const [startDateTime, setStartDateTime] = useState('');
  const [endDateTime, setEndDateTime] = useState('');
  const items = quickItems;
  const currentLoading = quickLoading;

  const hasFilters =
    tickerFilter.trim() !== '' ||
    sectorFilter.trim() !== '' ||
    topicFilter.trim() !== '' ||
    dateRange !== 'all' ||
    startDateTime !== '' ||
    endDateTime !== '';

  const filteredItems = useMemo(() => {
    let result = items;

    // Ticker filter
    const query = tickerFilter.trim().toUpperCase();
    if (query) {
      result = result.filter((item) =>
        item.tickers?.some((t) => t.toUpperCase().includes(query))
      );
    }
    const sector = sectorFilter.trim().toLowerCase();
    if (sector) {
      result = result.filter((item) => String(item.sector || '').toLowerCase().includes(sector));
    }
    const topic = topicFilter.trim().toLowerCase();
    if (topic) {
      result = result.filter((item) => String(item.topic || '').toLowerCase().includes(topic));
    }

    // Date range filter
    if (dateRange !== 'all') {
      const cutoff = getDateRangeCutoff(dateRange);
      result = result.filter((item) => {
        const ts = item.publishedAt ? parseServerDate(item.publishedAt)?.getTime() ?? null : parseRelativeTime(item.time);
        return ts !== null && ts >= cutoff;
      });
    }

    const startTs = parseDateTimeLocal(startDateTime);
    if (startTs !== null) {
      result = result.filter((item) => {
        const ts = item.publishedAt ? parseServerDate(item.publishedAt)?.getTime() ?? null : parseRelativeTime(item.time);
        return ts !== null && ts >= startTs;
      });
    }
    const endTs = parseDateTimeLocal(endDateTime);
    if (endTs !== null) {
      result = result.filter((item) => {
        const ts = item.publishedAt ? parseServerDate(item.publishedAt)?.getTime() ?? null : parseRelativeTime(item.time);
        return ts !== null && ts <= endTs;
      });
    }

    return result;
  }, [items, tickerFilter, sectorFilter, topicFilter, dateRange, startDateTime, endDateTime]);

  const isMobile = useIsMobile();

  const filteredEvents = useMemo(() => {
    let result = eventItems;
    const query = tickerFilter.trim().toUpperCase();
    if (query) {
      result = result.filter((item) =>
        (item.symbols || []).some((s) => s.toUpperCase().includes(query))
      );
    }
    if (dateRange !== 'all') {
      const cutoff = getDateRangeCutoff(dateRange);
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts >= cutoff;
      });
    }
    const startTs = parseDateTimeLocal(startDateTime);
    if (startTs !== null) {
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts >= startTs;
      });
    }
    const endTs = parseDateTimeLocal(endDateTime);
    if (endTs !== null) {
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts <= endTs;
      });
    }
    return result;
  }, [eventItems, tickerFilter, dateRange, startDateTime, endDateTime]);

  const filteredHotEvents = useMemo(() => {
    let result = hotEvents;
    const query = tickerFilter.trim().toUpperCase();
    if (query) {
      result = result.filter((item) =>
        (item.symbols || []).some((s) => s.toUpperCase().includes(query))
      );
    }
    if (dateRange !== 'all') {
      const cutoff = getDateRangeCutoff(dateRange);
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts >= cutoff;
      });
    }
    const startTs = parseDateTimeLocal(startDateTime);
    if (startTs !== null) {
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts >= startTs;
      });
    }
    const endTs = parseDateTimeLocal(endDateTime);
    if (endTs !== null) {
      result = result.filter((item) => {
        const ts = item.start_time ? parseServerDate(item.start_time)?.getTime() ?? null : null;
        return ts !== null && ts <= endTs;
      });
    }
    return result;
  }, [hotEvents, tickerFilter, dateRange, startDateTime, endDateTime]);

  const renderEventRow = (item: MarketEvent, idx: number) => {
    const score = Number(item.importance_score ?? 0);
    const sentiment = (item.sentiment || 'neutral').toLowerCase();
    const sentimentColor = sentiment === 'positive'
      ? 'var(--color-profit)'
      : sentiment === 'negative'
        ? 'var(--color-loss)'
        : 'var(--color-text-secondary)';
    return (
      <motion.div
        key={item.event_id}
        initial={isMobile ? false : { opacity: 0, y: 10 }}
        animate={isMobile ? undefined : { opacity: 1, y: 0 }}
        transition={{ delay: Math.min(idx, 10) * 0.05 }}
        className="group flex items-start gap-3 sm:gap-4 px-2 py-2.5 sm:p-3 rounded-lg sm:rounded-xl border border-transparent transition-all cursor-pointer"
        onClick={() => onEventClick?.(item.event_id)}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
          e.currentTarget.style.borderColor = 'var(--color-border-muted)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
          e.currentTarget.style.borderColor = 'transparent';
        }}
      >
        <div className="pt-0.5">
          <Zap size={14} style={{ color: sentimentColor }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span
              className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
              style={{ color: 'var(--color-accent-light)', backgroundColor: 'var(--color-accent-soft)' }}
            >
              Event
            </span>
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {item.start_time ? formatTime(item.start_time) : ''}
            </span>
            <span
              className="text-[10px] font-semibold px-1.5 py-0.5 rounded border"
              style={{ color: sentimentColor, borderColor: 'var(--color-border-muted)' }}
            >
              score {score.toFixed(0)}
            </span>
          </div>
          <h3 className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }} title={item.title}>
            {item.title}
          </h3>
          {item.short_summary && (
            <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>
              {item.short_summary}
            </p>
          )}
          {!!(item.symbols && item.symbols.length) && (
            <div className="flex items-center gap-1.5 mt-1">
              {item.symbols.slice(0, 5).map((t) => (
                <span
                  key={t}
                  className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                  style={{ backgroundColor: 'var(--color-accent-soft)', color: 'var(--color-accent-light)' }}
                >
                  {t}
                </span>
              ))}
              {(item.symbols?.length || 0) > 5 && (
                <span className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                  +{(item.symbols?.length || 0) - 5}
                </span>
              )}
            </div>
          )}
          <div className="mt-1.5">
            <button
              type="button"
              className="text-[11px] px-2 py-0.5 rounded border"
              style={{ color: 'var(--color-accent-light)', borderColor: 'var(--color-border-muted)' }}
              onClick={(e) => {
                e.stopPropagation();
                onAskEvent?.(item.event_id);
              }}
            >
              Ask AI
            </button>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div className={`dashboard-glass-card ${isMobile ? 'p-3' : 'p-6'}`}>
      {/* Header: tabs + filters on same row */}
      <div
        className={`flex items-center justify-between gap-3 ${isMobile ? 'pb-3 mb-3' : 'pb-4 mb-4'} border-b flex-wrap`}
        style={{ borderColor: 'var(--color-border-muted)' }}
      >
        {/* Modes + tabs */}
        <div className="flex items-center gap-2 min-w-0 overflow-x-auto">
          <div className="flex items-center gap-1 p-1 rounded-lg" style={{ backgroundColor: 'var(--color-bg-tag)' }}>
            <button
              onClick={() => { setMode('events'); setTickerFilter(''); setSectorFilter(''); setTopicFilter(''); setDateRange('all'); setStartDateTime(''); setEndDateTime(''); setEventView('hot'); }}
              className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
              style={{
                backgroundColor: mode === 'events' ? 'var(--color-bg-elevated)' : 'transparent',
                color: mode === 'events' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              }}
            >
              Events
            </button>
            <button
              onClick={() => { setMode('quick'); setTickerFilter(''); setSectorFilter(''); setTopicFilter(''); setDateRange('all'); setStartDateTime(''); setEndDateTime(''); }}
              className="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
              style={{
                backgroundColor: mode === 'quick' ? 'var(--color-bg-elevated)' : 'transparent',
                color: mode === 'quick' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              }}
            >
              7x24
            </button>
          </div>
          {mode === 'events' && (
            <>
              <div className="flex items-center gap-1 p-1 rounded-lg" style={{ backgroundColor: 'var(--color-bg-tag)' }}>
                <button
                  onClick={() => setEventView('hot')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all"
                  style={{
                    backgroundColor: eventView === 'hot' ? 'var(--color-bg-elevated)' : 'transparent',
                    color: eventView === 'hot' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  }}
                >
                  Hot
                </button>
                <button
                  onClick={() => setEventView('all')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all"
                  style={{
                    backgroundColor: eventView === 'all' ? 'var(--color-bg-elevated)' : 'transparent',
                    color: eventView === 'all' ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  }}
                >
                  All Events
                </button>
              </div>
            </>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          {/* Ticker search */}
          <div
            className="flex items-center gap-1.5 h-7 px-2 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-input, var(--color-bg-tag))',
              borderColor: 'var(--color-border-muted)',
              width: tickerFilter ? 160 : 130,
              transition: 'width 0.2s',
            }}
          >
            <Search size={12} style={{ color: 'var(--color-text-secondary)', flexShrink: 0 }} />
            <input
              type="text"
              placeholder="Ticker..."
              value={tickerFilter}
              onChange={(e) => setTickerFilter(e.target.value)}
              className="flex-1 text-[11px] bg-transparent border-none outline-none min-w-0"
              style={{ color: 'var(--color-text-primary)' }}
            />
            {tickerFilter && (
              <button
                onClick={() => setTickerFilter('')}
                className="flex-shrink-0"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <X size={11} />
              </button>
            )}
          </div>
          <div
            className="flex items-center gap-1.5 h-7 px-2 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-input, var(--color-bg-tag))',
              borderColor: 'var(--color-border-muted)',
              width: sectorFilter ? 150 : 110,
              transition: 'width 0.2s',
            }}
          >
            <input
              type="text"
              placeholder="Sector..."
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              className="flex-1 text-[11px] bg-transparent border-none outline-none min-w-0"
              style={{ color: 'var(--color-text-primary)' }}
            />
          </div>
          <div
            className="flex items-center gap-1.5 h-7 px-2 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-input, var(--color-bg-tag))',
              borderColor: 'var(--color-border-muted)',
              width: topicFilter ? 140 : 100,
              transition: 'width 0.2s',
            }}
          >
            <input
              type="text"
              placeholder="Topic..."
              value={topicFilter}
              onChange={(e) => setTopicFilter(e.target.value)}
              className="flex-1 text-[11px] bg-transparent border-none outline-none min-w-0"
              style={{ color: 'var(--color-text-primary)' }}
            />
          </div>
          <div
            className="flex items-center gap-1.5 h-7 px-2 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-input, var(--color-bg-tag))',
              borderColor: 'var(--color-border-muted)',
              width: 170,
            }}
            title="Start time (YYYY-MM-DD HH)"
          >
            <input
              type="datetime-local"
              step={3600}
              value={startDateTime}
              onChange={(e) => {
                setStartDateTime(e.target.value);
                setDateRange('all');
              }}
              className="flex-1 text-[11px] bg-transparent border-none outline-none min-w-0"
              style={{ color: 'var(--color-text-primary)' }}
            />
          </div>
          <div
            className="flex items-center gap-1.5 h-7 px-2 rounded-lg border"
            style={{
              backgroundColor: 'var(--color-bg-input, var(--color-bg-tag))',
              borderColor: 'var(--color-border-muted)',
              width: 170,
            }}
            title="End time (YYYY-MM-DD HH)"
          >
            <input
              type="datetime-local"
              step={3600}
              value={endDateTime}
              onChange={(e) => {
                setEndDateTime(e.target.value);
                setDateRange('all');
              }}
              className="flex-1 text-[11px] bg-transparent border-none outline-none min-w-0"
              style={{ color: 'var(--color-text-primary)' }}
            />
          </div>

          {/* Date range pills */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-lg" style={{ backgroundColor: 'var(--color-bg-tag)' }}>
            {DATE_RANGES.map((dr) => {
              const isActive = dateRange === dr.key;
              return (
                <button
                  key={dr.key}
                  onClick={() => setDateRange(dr.key)}
                  className="px-2 py-1 rounded-md text-[11px] font-medium transition-all"
                  style={{
                    backgroundColor: isActive ? 'var(--color-bg-elevated)' : 'transparent',
                    color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  }}
                >
                  {dr.label}
                </button>
              );
            })}
          </div>

          {/* Clear */}
          {hasFilters && (
            <button
              onClick={() => { setTickerFilter(''); setSectorFilter(''); setTopicFilter(''); setDateRange('all'); setStartDateTime(''); setEndDateTime(''); }}
              style={{ color: 'var(--color-text-secondary)' }}
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="flex flex-col gap-1"
        >
          {mode === 'events' ? (
            (eventView === 'all' ? eventLoading : hotEventsLoading) ? (
              <SkeletonRows />
            ) : (eventView === 'all' ? filteredEvents : filteredHotEvents).length === 0 ? (
              <div className="flex items-center justify-center py-16">
                <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                  {eventView === 'all' ? 'No events available' : 'No hot events available'}
                </p>
              </div>
            ) : (
              (eventView === 'all' ? filteredEvents : filteredHotEvents).map((item, idx) => renderEventRow(item, idx))
            )
          ) : currentLoading ? (
            <SkeletonRows />
          ) : filteredItems.length === 0 ? (
            <EmptyState hasFilters={hasFilters} />
          ) : (
            filteredItems.map((item, idx) => (
              <NewsRow key={item.id || idx} item={item} idx={idx} onNewsClick={onNewsClick} onAskNews={onAskNews} skipAnimation={isMobile} />
            ))
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export default NewsFeedCard;
