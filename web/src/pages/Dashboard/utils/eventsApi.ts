import { api } from '@/api/client';

export interface MarketEvent {
  event_id: string;
  title: string;
  short_summary?: string | null;
  importance_score?: number;
  sentiment?: string | null;
  start_time?: string | null;
  primary_symbol?: string | null;
  symbols?: string[];
  tags?: string[];
  article_count?: number;
  ai_takeaway?: string | null;
}

export interface EventArticle {
  article_id: string;
  relevance_score?: number | null;
  is_primary?: boolean;
  title?: string | null;
  article_url?: string | null;
  source_name?: string | null;
  published_at?: string | null;
}

export interface MarketEventDetail extends MarketEvent {
  related_articles: EventArticle[];
}

export interface InterpretResult {
  target_type: 'event' | 'article';
  target_id: string;
  interpretation: string;
  model?: string | null;
  cached?: boolean;
  generated_at: string;
}

export interface AskAIResult {
  thread_initial_message: string;
  fallback_message: string;
  additional_context: Record<string, unknown>[];
}

interface EventListResponse {
  results: MarketEvent[];
  count: number;
  limit: number;
  offset: number;
}

export async function getEvents(params: { limit?: number; offset?: number } = {}): Promise<EventListResponse> {
  const { data } = await api.get('/api/v1/events', { params });
  return data;
}

export async function getHotEvents(limit: number = 10): Promise<EventListResponse> {
  const { data } = await api.get('/api/v1/events/hot', { params: { limit } });
  return data;
}

export async function getEventDetail(eventId: string): Promise<MarketEventDetail> {
  const { data } = await api.get(`/api/v1/events/${encodeURIComponent(eventId)}`);
  return data;
}

export async function getEventsBySymbol(symbol: string, limit: number = 20): Promise<EventListResponse> {
  const { data } = await api.get(`/api/v1/events/by-symbol/${encodeURIComponent(symbol)}`, {
    params: { limit },
  });
  return data;
}

export async function interpretEvent(eventId: string, payload: { focus_symbol?: string; refresh?: boolean } = {}): Promise<InterpretResult> {
  const { data } = await api.post(`/api/v1/events/${encodeURIComponent(eventId)}/interpret`, payload);
  return data;
}

export async function askEvent(eventId: string, payload: { question?: string; focus_symbol?: string } = {}): Promise<AskAIResult> {
  const { data } = await api.post(`/api/v1/events/${encodeURIComponent(eventId)}/ask`, payload);
  return data;
}

export async function interpretNews(articleId: string, payload: { focus_symbol?: string; refresh?: boolean } = {}): Promise<InterpretResult> {
  const { data } = await api.post(`/api/v1/news/${encodeURIComponent(articleId)}/interpret`, payload);
  return data;
}
