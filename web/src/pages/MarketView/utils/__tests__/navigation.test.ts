import { describe, expect, it } from 'vitest';

import { buildDashboardEventUrl } from '../navigation';

describe('buildDashboardEventUrl', () => {
  it('builds dashboard deep-link with event id', () => {
    expect(buildDashboardEventUrl('evt-1')).toBe('/dashboard?event=evt-1');
  });

  it('includes optional symbol', () => {
    expect(buildDashboardEventUrl('evt-1', 'AAPL')).toBe('/dashboard?event=evt-1&symbol=AAPL');
  });
});

