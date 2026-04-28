import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';

interface AskAIDialogProps {
  open: boolean;
  title: string;
  subjectLabel?: string | null;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (question: string) => Promise<void> | void;
}

function AskAIDialog({
  open,
  title,
  subjectLabel,
  loading = false,
  onClose,
  onSubmit,
}: AskAIDialogProps) {
  const [question, setQuestion] = useState('');

  useEffect(() => {
    if (!open) {
      setQuestion('');
    }
  }, [open]);

  const handleSubmit = async () => {
    const nextQuestion = question.trim();
    if (!nextQuestion || loading) return;
    await onSubmit(nextQuestion);
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => { if (!nextOpen && !loading) onClose(); }}>
      <DialogContent
        variant="centered"
        className="sm:max-w-xl border"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          borderColor: 'var(--color-border-muted)',
          color: 'var(--color-text-primary)',
        }}
      >
        <DialogHeader>
          <DialogTitle className="title-font">{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {subjectLabel && (
            <div
              className="rounded-lg border px-3 py-2 text-xs"
              style={{
                backgroundColor: 'var(--color-bg-card)',
                borderColor: 'var(--color-border-muted)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {subjectLabel}
            </div>
          )}
          <Textarea
            autoFocus
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter your question. The current news or event context will be attached automatically."
            className="min-h-[140px] border"
            style={{
              backgroundColor: 'var(--color-bg-card)',
              borderColor: 'var(--color-border-muted)',
              color: 'var(--color-text-primary)',
            }}
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-3 py-1.5 rounded text-sm border"
              style={{
                borderColor: 'var(--color-border-muted)',
                color: 'var(--color-text-secondary)',
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading || !question.trim()}
              className="px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50"
              style={{
                backgroundColor: 'var(--color-accent-primary)',
                color: 'var(--color-text-on-accent)',
              }}
            >
              {loading ? 'Opening...' : 'Ask AI'}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default AskAIDialog;
