import { useUser } from './useUser';
import { parseServerDate } from '@/lib/dateTime';

interface FormatTimeOptions extends Intl.DateTimeFormatOptions {}

/**
 * Returns a formatTime function bound to the current user's timezone and locale.
 * Falls back to browser timezone / browser locale when the user hasn't set preferences.
 */
export function useFormatTime() {
  const { user } = useUser();
  const timezone = user?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC';
  const locale = user?.locale ?? navigator.language ?? 'zh-CN';

  return (
    dateStr: string | null | undefined,
    options?: FormatTimeOptions,
  ): string => {
    if (!dateStr) return '';
    try {
      const parsed = parseServerDate(dateStr);
      if (!parsed) return dateStr;
      return parsed.toLocaleString(locale, {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        ...options,
      });
    } catch {
      return dateStr;
    }
  };
}
