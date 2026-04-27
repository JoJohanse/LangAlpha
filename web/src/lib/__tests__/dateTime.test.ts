import { describe, expect, it } from 'vitest';

import { parseServerDate } from '../dateTime';

describe('parseServerDate', () => {
  it('treats naive timestamps as UTC', () => {
    const parsed = parseServerDate('2026-04-27T08:00:00');
    expect(parsed?.toISOString()).toBe('2026-04-27T08:00:00.000Z');
  });

  it('supports database-style timestamps with spaces', () => {
    const parsed = parseServerDate('2026-04-27 08:00:00');
    expect(parsed?.toISOString()).toBe('2026-04-27T08:00:00.000Z');
  });

  it('keeps explicit timezone offsets intact', () => {
    const parsed = parseServerDate('2026-04-27T08:00:00+08:00');
    expect(parsed?.toISOString()).toBe('2026-04-27T00:00:00.000Z');
  });
});

