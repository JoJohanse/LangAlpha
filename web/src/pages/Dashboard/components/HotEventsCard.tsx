import type { MarketEvent } from '../utils/eventsApi';

interface HotEventsCardProps {
  events: MarketEvent[];
  loading?: boolean;
  onEventClick?: (eventId: string) => void;
}

function HotEventsCard({ events, loading = false, onEventClick }: HotEventsCardProps) {
  return (
    <div className="dashboard-glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Hot Events
        </h3>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div
              key={idx}
              className="h-12 rounded animate-pulse"
              style={{ backgroundColor: 'var(--color-border-default)' }}
            />
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          No hot events
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((event) => (
            <button
              key={event.event_id}
              type="button"
              className="w-full text-left p-2.5 rounded-lg border transition-colors hover:bg-foreground/10"
              style={{ borderColor: 'var(--color-border-muted)' }}
              onClick={() => onEventClick?.(event.event_id)}
            >
              <div className="text-xs mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                {event.start_time ? new Date(event.start_time).toLocaleString() : ''}
              </div>
              <div className="text-sm font-medium line-clamp-2" style={{ color: 'var(--color-text-primary)' }}>
                {event.title}
              </div>
              <div className="mt-1 flex items-center gap-2 flex-wrap">
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded border"
                  style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border-muted)' }}
                >
                  score {Number(event.importance_score ?? 0).toFixed(0)}
                </span>
                {(event.symbols || []).slice(0, 3).map((symbol) => (
                  <span
                    key={symbol}
                    className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                    style={{ backgroundColor: 'var(--color-accent-soft)', color: 'var(--color-accent-light)' }}
                  >
                    {symbol}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default HotEventsCard;
