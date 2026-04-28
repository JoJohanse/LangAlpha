import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '@/test/utils';
import AskAIDialog from '../AskAIDialog';

describe('AskAIDialog', () => {
  it('renders title and subject label', () => {
    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI About This News"
        subjectLabel="Fed signals rate cut"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByText('Ask AI About This News')).toBeInTheDocument();
    expect(screen.getByText('Fed signals rate cut')).toBeInTheDocument();
  });

  it('does not render subject label when null', () => {
    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI"
        subjectLabel={null}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: 'Ask AI' })).toBeInTheDocument();
  });

  it('calls onSubmit with the question text', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI"
        subjectLabel="Test article"
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />
    );

    const textarea = screen.getByPlaceholderText(/Enter your question/);
    await user.type(textarea, 'What is the market impact?');

    const askButton = screen.getByRole('button', { name: 'Ask AI' });
    await user.click(askButton);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('What is the market impact?');
    });
  });

  it('disables Ask AI button when input is empty', () => {
    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI"
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    const askButton = screen.getByRole('button', { name: 'Ask AI' });
    expect(askButton).toBeDisabled();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI"
        onClose={onClose}
        onSubmit={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows loading text on Ask AI button when loading', () => {
    renderWithProviders(
      <AskAIDialog
        open={true}
        title="Ask AI"
        subjectLabel="Test"
        loading={true}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Opening...' })).toBeInTheDocument();
  });
});
