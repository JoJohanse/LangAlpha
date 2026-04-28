import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

import { renderWithProviders } from '@/test/utils';
import Dashboard from '../Dashboard';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('@/hooks/useIsMobile', () => ({
  useIsMobile: () => false,
}));

vi.mock('../hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    indices: [],
    indicesLoading: false,
    newsItems: [],
    newsLoading: false,
    eventItems: [],
    eventLoading: false,
    hotEvents: [],
    hotEventsLoading: false,
    quickNewsItems: [],
    quickNewsLoading: false,
    marketStatus: null,
    marketStatusRef: { current: null },
  }),
}));

vi.mock('../hooks/useOnboarding', () => ({
  useOnboarding: () => ({
    showPersonalizationBanner: false,
    setShowPersonalizationBanner: vi.fn(),
    isCreatingWorkspace: false,
    navigateToPersonalization: vi.fn(),
  }),
  snoozePersonalization: vi.fn(),
}));

vi.mock('../hooks/useWatchlistData', () => ({
  useWatchlistData: () => ({
    rows: [],
    loading: false,
    modalOpen: false,
    currentWatchlistId: null,
    setModalOpen: vi.fn(),
    handleDelete: vi.fn(),
    handleAdd: vi.fn(),
  }),
}));

vi.mock('../hooks/usePortfolioData', () => ({
  usePortfolioData: () => ({
    rows: [],
    loading: false,
    hasRealHoldings: false,
    modalOpen: false,
    setModalOpen: vi.fn(),
    handleDelete: vi.fn(() => ({ open: false, title: '', message: '', onConfirm: null })),
    handleAdd: vi.fn(),
    editRow: null,
    openEdit: vi.fn(),
    editForm: {},
    setEditForm: vi.fn(),
    handleUpdate: vi.fn(),
  }),
}));

vi.mock('../hooks/useTickerNews', () => ({
  useTickerNews: () => ({
    items: [],
    loading: false,
  }),
}));

vi.mock('../components/DashboardHeader', () => ({ default: () => <div /> }));
vi.mock('../components/ConfirmDialog', () => ({ default: () => <div /> }));
vi.mock('../components/IndexMovementCard', () => ({ default: () => <div /> }));
vi.mock('../components/AIDailyBriefCard', () => ({ default: () => <div /> }));
vi.mock('../components/NewsFeedCard', () => ({ default: () => <div /> }));
vi.mock('../components/ChatInputCard', () => ({ default: () => <div /> }));
vi.mock('../components/EarningsCalendarCard', () => ({ default: () => <div /> }));
vi.mock('../components/PortfolioWatchlistCard', () => ({ default: () => <div /> }));
vi.mock('../components/NewsDetailModal', () => ({ default: () => <div /> }));
vi.mock('../components/InsightDetailModal', () => ({ default: () => <div /> }));
vi.mock('../components/HotEventsCard', () => ({ default: () => <div /> }));
vi.mock('../components/AddWatchlistItemDialog', () => ({ default: () => <div /> }));
vi.mock('../components/AddPortfolioHoldingDialog', () => ({ default: () => <div /> }));

vi.mock('../components/EventDetailModal', () => ({
  default: ({ eventId }: { eventId: string | null }) => (
    <div data-testid="event-detail-modal">{eventId || ''}</div>
  ),
}));

describe('Dashboard event deep link', () => {
  it('opens event detail modal from ?event query param', async () => {
    renderWithProviders(<Dashboard />, { route: '/dashboard?event=evt-123' });

    await waitFor(() => {
      expect(screen.getByTestId('event-detail-modal')).toHaveTextContent('evt-123');
    });
  });
});
