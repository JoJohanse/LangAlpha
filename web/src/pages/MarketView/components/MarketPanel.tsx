import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MessageList from '../../ChatAgent/components/MessageList';
import LogoLoading from '../../../components/ui/logo-loading';
import type { StructuredError } from '@/utils/rateLimitError';
import './MarketPanel.css';

// TODO: type properly once ChatAgent message types are exported
interface ChatMessage {
  id?: string;
  role?: string;
  content?: string;
  isStreaming?: boolean;
  [key: string]: unknown;
}

interface MarketPanelProps {
  messages?: ChatMessage[];
  isLoading?: boolean;
  error?: string | StructuredError | null;
}

/** Render error link — uses client-side navigation for internal paths. */
function ErrorLink({ url, label, navigate }: { url: string; label: string; navigate: (to: string) => void }) {
  return (
    <>
      {' '}
      <a
        href={url}
        {...(!url.startsWith('/') && { target: '_blank', rel: 'noopener noreferrer' })}
        onClick={(e) => {
          if (url.startsWith('/')) {
            e.preventDefault();
            navigate(url);
          }
        }}
        style={{ textDecoration: 'underline', fontWeight: 500 }}
      >
        {label}
      </a>
    </>
  );
}

/** Render error text, supporting both plain strings and StructuredError objects. */
function renderErrorContent(error: string | StructuredError, navigate: (to: string) => void): React.ReactNode {
  if (typeof error === 'object' && 'message' in error) {
    return (
      <>
        {error.message}
        {error.link && <ErrorLink url={error.link.url} label={error.link.label} navigate={navigate} />}
      </>
    );
  }
  return error;
}

const MarketPanel = ({ messages = [], isLoading: _isLoading = false, error = null }: MarketPanelProps) => {
  const navigate = useNavigate();
  const _messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or when streaming
  useEffect(() => {
    const scrollToBottom = () => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTo({
          top: messagesContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    };

    // Scroll when messages change
    if (messages.length > 0) {
      // Use setTimeout to ensure DOM has updated
      const timeoutId = setTimeout(scrollToBottom, 100);
      return () => clearTimeout(timeoutId);
    }
  }, [messages]);

  // Also scroll when a message is streaming (content updates)
  useEffect(() => {
    const hasStreamingMessage = messages.some((msg) => msg.isStreaming);
    if (hasStreamingMessage && messagesContainerRef.current) {
      const timeoutId = setTimeout(() => {
        if (messagesContainerRef.current) {
          messagesContainerRef.current.scrollTo({
            top: messagesContainerRef.current.scrollHeight,
            behavior: 'smooth',
          });
        }
      }, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [messages]);

  return (
    <div className="market-panel">
      <div 
        ref={messagesContainerRef}
        style={{ 
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {messages.length === 0 ? (
          <div className="market-chat-empty-state" style={{ height: '100%' }}>
            <LogoLoading size={60} color="var(--color-accent-overlay)" />
            <p className="market-chat-empty-text" style={{ marginTop: 16 }}>
              Start a conversation by typing a message below
            </p>
            {error && (
              <div style={{ color: 'var(--color-loss)', padding: '12px', fontSize: '14px' }}>
                {renderErrorContent(error, navigate)}
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '16px 24px', maxWidth: '100%' }}>
            <MessageList
              messages={messages}
              hideAvatar
              compactToolCalls
              onOpenSubagentTask={() => {}}
              onOpenFile={() => {}}
            />
            {error && (
              <div style={{
                margin: '8px 0',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'var(--color-loss-soft)',
                border: '1px solid var(--color-border-loss)',
                color: 'var(--color-loss)',
                fontSize: '13px',
                lineHeight: '1.5',
              }}>
                {renderErrorContent(error, navigate)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(MarketPanel);
