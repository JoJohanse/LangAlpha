import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@/test/utils';
import HotEventsCard from '../HotEventsCard';

describe('HotEventsCard', () => {
  it('renders empty state', () => {
    renderWithProviders(<HotEventsCard events={[]} loading={false} />);
    expect(screen.getByText('No hot events')).toBeInTheDocument();
  });

  it('renders events and handles click', async () => {
    const user = userEvent.setup();
    const onEventClick = vi.fn();

    renderWithProviders(
      <HotEventsCard
        loading={false}
        onEventClick={onEventClick}
        events={[
          {
            event_id: 'evt-1',
            title: 'Apple AI event',
            start_time: '2026-04-23T08:00:00Z',
            importance_score: 88,
            symbols: ['AAPL', 'NVDA'],
          },
        ]}
      />
    );

    await user.click(screen.getByRole('button', { name: /Apple AI event/i }));
    expect(onEventClick).toHaveBeenCalledWith('evt-1');
  });
});

