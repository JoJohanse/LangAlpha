/**
 * Tests the ChatView error banner rendering logic (type guard for structured vs string errors).
 *
 * We extract the rendering logic into a minimal test component rather than mounting
 * the full ChatView (which has ~30 transitive dependencies). This verifies:
 * - Structured errors render message + link without going through parseErrorMessage
 * - String errors pass through parseErrorMessage as before
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { parseErrorMessage } from '../../utils/parseErrorMessage';
import type { StructuredError } from '@/utils/rateLimitError';

/**
 * Minimal reproduction of the ChatView error banner logic.
 * Mirrors the IIFE in ChatView.tsx lines ~1930-1955.
 */
function ErrorBanner({ messageError }: { messageError: string | StructuredError | null }) {
  if (!messageError) return null;

  // Structured error path (from buildRateLimitError)
  if (typeof messageError === 'object' && 'message' in messageError) {
    const err = messageError as StructuredError;
    return (
      <div data-testid="error-banner" role="alert">
        <span>
          {err.message}
          {err.link && (
            <>
              {' '}
              <a
                href={err.link.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {err.link.label}
              </a>
            </>
          )}
        </span>
      </div>
    );
  }

  // String error path (existing parseErrorMessage)
  const parsed = parseErrorMessage(messageError as string);
  return (
    <div data-testid="error-banner" role="alert">
      <span>{parsed.detail ? `${parsed.title}: ${parsed.detail}` : parsed.title}</span>
    </div>
  );
}

describe('ChatView error banner type guard', () => {
  it('renders structured error with message and link', () => {
    const error: StructuredError = {
      message: 'Daily credit limit reached (80/100 credits). Resets at midnight UTC.',
      link: { url: 'https://ginlix.ai/account/usage', label: 'View Usage' },
    };
    render(<ErrorBanner messageError={error} />);

    expect(screen.getByText(/Daily credit limit reached/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'View Usage' });
    expect(link).toHaveAttribute('href', 'https://ginlix.ai/account/usage');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders structured error without link', () => {
    const error: StructuredError = {
      message: 'Too many concurrent requests. Please wait a moment.',
    };
    render(<ErrorBanner messageError={error} />);

    expect(screen.getByText(/Too many concurrent requests/)).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('renders string error through parseErrorMessage', () => {
    render(<ErrorBanner messageError="Something went wrong on the server" />);
    // parseErrorMessage returns { title: raw, detail: null } for short plain strings
    expect(screen.getByText('Something went wrong on the server')).toBeInTheDocument();
  });

  it('renders string rate-limit error with descriptive passthrough', () => {
    render(<ErrorBanner messageError="Daily credit limit reached (50/50 credits). Resets at midnight UTC." />);
    // parseErrorMessage now passes through descriptive rate-limit messages as title-only
    expect(screen.getByText(/Daily credit limit reached/)).toBeInTheDocument();
    // Should NOT have redundant "Rate limit exceeded:" prefix
    expect(screen.queryByText(/Rate limit exceeded:/)).not.toBeInTheDocument();
  });

  it('renders null for no error', () => {
    const { container } = render(<ErrorBanner messageError={null} />);
    expect(container.firstChild).toBeNull();
  });
});
