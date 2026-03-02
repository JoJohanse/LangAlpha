import React from 'react';

const trendStyles = {
  up: {
    backgroundColor: 'var(--color-profit-soft)',
    color: 'var(--color-profit)',
    borderColor: 'var(--color-profit-soft)',
  },
  down: {
    backgroundColor: 'var(--color-loss-soft)',
    color: 'var(--color-loss)',
    borderColor: 'var(--color-loss-soft)',
  },
  neutral: {
    backgroundColor: 'var(--color-bg-tag)',
    color: 'var(--color-text-secondary)',
    borderColor: 'var(--color-bg-tag)',
  },
};

function TopicBadge({ text, trend }) {
  return (
    <span
      className="px-3 py-1.5 rounded-lg border text-xs font-medium"
      style={trendStyles[trend] || trendStyles.neutral}
    >
      #{text}
    </span>
  );
}

export default TopicBadge;
