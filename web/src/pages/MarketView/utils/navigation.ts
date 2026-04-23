export function buildDashboardEventUrl(eventId: string, symbol?: string): string {
  const params = new URLSearchParams({ event: eventId });
  if (symbol) {
    params.set('symbol', symbol);
  }
  return `/dashboard?${params.toString()}`;
}

