import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Sparkles, ExternalLink, BarChart3 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MobileBottomSheet } from '@/components/ui/mobile-bottom-sheet';
import { useIsMobile } from '@/hooks/useIsMobile';
import {
  getEventDetail,
  interpretEvent,
  type MarketEventDetail,
  type InterpretResult,
} from '../utils/eventsApi';

interface EventDetailModalProps {
  eventId: string | null;
  onClose: () => void;
}

function EventDetailModal({ eventId, onClose }: EventDetailModalProps) {
  const [loading, setLoading] = useState(false);
  const [eventData, setEventData] = useState<MarketEventDetail | null>(null);
  const [interpretLoading, setInterpretLoading] = useState(false);
  const [interpretResult, setInterpretResult] = useState<InterpretResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isMobile = useIsMobile();
  const navigate = useNavigate();

  useEffect(() => {
    if (!eventId) {
      setEventData(null);
      setInterpretResult(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getEventDetail(eventId)
      .then((data) => {
        if (cancelled) return;
        setEventData(data);
      })
      .catch((e) => {
        console.error('[EventDetailModal] failed', e);
        if (!cancelled) setError('Failed to load event details');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  const handleInterpret = async () => {
    if (!eventId || interpretLoading) return;
    setInterpretLoading(true);
    try {
      const result = await interpretEvent(eventId);
      setInterpretResult(result);
    } catch (e) {
      console.error('[EventDetailModal] interpret failed', e);
      setError('Interpretation failed');
    } finally {
      setInterpretLoading(false);
    }
  };

  const handleOpenMarket = () => {
    if (!eventData) return;
    const symbol = eventData.primary_symbol || eventData.symbols?.[0];
    if (!symbol) return;
    const qs = new URLSearchParams({
      symbol,
      event: eventData.event_id,
    });
    if (eventData.start_time) qs.set('event_time', eventData.start_time);
    navigate(`/market?${qs.toString()}`);
    onClose();
  };

  const body = (
    <div className={isMobile ? 'pt-2' : 'p-6'}>
      {loading ? (
        <div className="py-16 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          Loading event...
        </div>
      ) : error ? (
        <div className="py-16 text-center" style={{ color: 'var(--color-loss)' }}>
          {error}
        </div>
      ) : !eventData ? (
        <div className="py-16 text-center" style={{ color: 'var(--color-text-secondary)' }}>
          Event not found
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <div className="text-xs mb-1" style={{ color: 'var(--color-text-secondary)' }}>
              {eventData.start_time ? new Date(eventData.start_time).toLocaleString() : ''}
            </div>
            <h2 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
              {eventData.title}
            </h2>
            {eventData.short_summary && (
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {eventData.short_summary}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {(eventData.symbols || []).map((sym) => (
              <span
                key={sym}
                className="text-xs px-2 py-1 rounded"
                style={{ backgroundColor: 'var(--color-accent-soft)', color: 'var(--color-accent-light)' }}
              >
                {sym}
              </span>
            ))}
          </div>

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={handleOpenMarket}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded text-sm font-medium"
              style={{ backgroundColor: 'var(--color-accent-primary)', color: '#fff' }}
            >
              <BarChart3 size={14} />
              Open MarketView
            </button>
            <button
              onClick={handleInterpret}
              disabled={interpretLoading}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded text-sm font-medium border"
              style={{ borderColor: 'var(--color-border-muted)', color: 'var(--color-text-secondary)' }}
            >
              <Sparkles size={14} />
              {interpretLoading ? 'Interpreting...' : 'AI Interpret'}
            </button>
          </div>

          {(interpretResult?.interpretation || eventData.ai_takeaway) && (
            <div
              className="rounded-lg border p-3"
              style={{ borderColor: 'var(--color-border-muted)', backgroundColor: 'var(--color-bg-card)' }}
            >
              <div className="text-xs mb-1" style={{ color: 'var(--color-text-secondary)' }}>
                AI Interpretation
              </div>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
                {interpretResult?.interpretation || eventData.ai_takeaway}
              </p>
            </div>
          )}

          {!!eventData.related_articles?.length && (
            <div>
              <div className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Related News
              </div>
              <div className="space-y-2">
                {eventData.related_articles.slice(0, 10).map((a) => (
                  <a
                    key={a.article_id}
                    href={a.article_url || '#'}
                    target={a.article_url ? '_blank' : undefined}
                    rel={a.article_url ? 'noopener noreferrer' : undefined}
                    className="block p-2 rounded border transition-colors hover:bg-foreground/10"
                    style={{ borderColor: 'var(--color-border-muted)' }}
                  >
                    <div className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                      {a.title || a.article_id}
                    </div>
                    <div className="text-xs mt-1 flex items-center gap-2" style={{ color: 'var(--color-text-secondary)' }}>
                      <span>{a.source_name || 'Source'}</span>
                      {a.article_url && <ExternalLink size={12} />}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  if (isMobile) {
    return (
      <MobileBottomSheet
        open={!!eventId}
        onClose={onClose}
        sizing="fixed"
        height="92vh"
        style={{ paddingBottom: 'calc(var(--bottom-tab-height, 0px) + 16px)' }}
      >
        {body}
      </MobileBottomSheet>
    );
  }

  return (
    <AnimatePresence>
      {eventId && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center p-6"
          style={{ backgroundColor: 'var(--color-bg-overlay, rgba(0,0,0,0.6))', backdropFilter: 'blur(4px)' }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-3xl max-h-[88vh] overflow-y-auto rounded-2xl border relative"
            style={{ backgroundColor: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-muted)' }}
          >
            <button
              onClick={onClose}
              className="absolute top-3 right-3 p-2 rounded-full z-10"
              style={{ color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-bg-hover)' }}
            >
              <X size={16} />
            </button>
            {body}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default EventDetailModal;
