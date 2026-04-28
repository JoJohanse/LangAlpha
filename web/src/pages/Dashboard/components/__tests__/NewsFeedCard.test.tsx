import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@/test/utils';
import NewsFeedCard from '../NewsFeedCard';

describe('NewsFeedCard', () => {
  const sampleItems = [
    {
      id: 'news-1',
      title: 'Fed signals rate cut',
      time: '10 min ago',
      publishedAt: '2026-04-28T08:00:00Z',
      isHot: true,
      source: 'Reuters',
      favicon: null,
      image: null,
      tickers: ['SPY', 'QQQ'],
      articleUrl: 'https://example.com/news-1',
      sector: 'macro',
      topic: 'rates',
      region: 'US',
      tags: ['fed', 'rates'],
      importanceScore: 85,
    },
    {
      id: 'news-2',
      title: 'Oil prices surge on supply concerns',
      time: '2 hrs ago',
      publishedAt: '2026-04-28T06:00:00Z',
      isHot: false,
      source: 'Bloomberg',
      favicon: null,
      image: null,
      tickers: ['USO', 'XLE'],
      articleUrl: 'https://example.com/news-2',
      sector: 'energy',
      topic: 'oil',
      region: 'US',
      tags: ['oil', 'energy'],
    },
  ];

  it('renders empty state when no items', () => {
    renderWithProviders(
      <NewsFeedCard quickItems={[]} quickLoading={false} />
    );
    // Switch to 7x24 tab to see news
    expect(screen.getByText('7x24')).toBeInTheDocument();
  });

  it('renders news items in 7x24 mode', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <NewsFeedCard quickItems={sampleItems} quickLoading={false} />
    );

    await user.click(screen.getByText('7x24'));

    await waitFor(() => {
      expect(screen.getByText('Fed signals rate cut')).toBeInTheDocument();
    });
    expect(screen.getByText('Oil prices surge on supply concerns')).toBeInTheDocument();
  });

  it('calls onNewsClick with id and articleUrl when clicking a news row', async () => {
    const user = userEvent.setup();
    const onNewsClick = vi.fn();

    renderWithProviders(
      <NewsFeedCard
        quickItems={sampleItems}
        quickLoading={false}
        onNewsClick={onNewsClick}
      />
    );

    await user.click(screen.getByText('7x24'));

    await waitFor(() => {
      expect(screen.getByText('Fed signals rate cut')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Fed signals rate cut'));
    expect(onNewsClick).toHaveBeenCalledWith('news-1', 'https://example.com/news-1');
  });

  it('calls onAskNews with full item when clicking Ask AI button', async () => {
    const user = userEvent.setup();
    const onAskNews = vi.fn();

    renderWithProviders(
      <NewsFeedCard
        quickItems={sampleItems}
        quickLoading={false}
        onAskNews={onAskNews}
      />
    );

    await user.click(screen.getByText('7x24'));

    await waitFor(() => {
      expect(screen.getByText('Fed signals rate cut')).toBeInTheDocument();
    });

    const askButtons = screen.getAllByText('Ask AI');
    expect(askButtons.length).toBeGreaterThanOrEqual(1);

    await user.click(askButtons[0]);

    expect(onAskNews).toHaveBeenCalledTimes(1);
    const passedItem = onAskNews.mock.calls[0][0];
    expect(passedItem.id).toBe('news-1');
    expect(passedItem.title).toBe('Fed signals rate cut');
    expect(passedItem.source).toBe('Reuters');
    expect(passedItem.tickers).toEqual(['SPY', 'QQQ']);
    expect(passedItem.sector).toBe('macro');
    expect(passedItem.topic).toBe('rates');
    expect(passedItem.region).toBe('US');
    expect(passedItem.tags).toEqual(['fed', 'rates']);
  });

  it('shows loading skeleton when loading', () => {
    renderWithProviders(
      <NewsFeedCard quickItems={[]} hotEventsLoading={true} />
    );

    // Loading state should show skeleton elements (animate-pulse divs)
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('filters by ticker', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <NewsFeedCard quickItems={sampleItems} quickLoading={false} />
    );

    await user.click(screen.getByText('7x24'));

    const tickerInput = screen.getByPlaceholderText('Ticker...');
    await user.type(tickerInput, 'SPY');

    await waitFor(() => {
      expect(screen.getByText('Fed signals rate cut')).toBeInTheDocument();
    });
    expect(screen.queryByText('Oil prices surge on supply concerns')).not.toBeInTheDocument();
  });

  it('shows empty filter message when no results match', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <NewsFeedCard quickItems={sampleItems} quickLoading={false} />
    );

    await user.click(screen.getByText('7x24'));

    const tickerInput = screen.getByPlaceholderText('Ticker...');
    await user.type(tickerInput, 'ZZZZ');

    await waitFor(() => {
      expect(screen.getByText('No news matching your filters')).toBeInTheDocument();
    });
  });
});
