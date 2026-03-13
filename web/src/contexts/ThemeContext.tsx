import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';

type ThemePreference = 'light' | 'dark' | 'auto';
type ResolvedTheme = 'light' | 'dark';

export interface ThemeContextValue {
  theme: ResolvedTheme;
  preference: ThemePreference;
  setTheme: (value: ThemePreference) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function getInitialPreference(): ThemePreference {
  const stored = localStorage.getItem('theme');
  if (stored === 'light' || stored === 'dark' || stored === 'auto') return stored;
  return 'auto';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(getInitialPreference);
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(getSystemTheme);

  // Listen to OS theme changes
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: light)');
    const handler = (e: MediaQueryListEvent) => setSystemTheme(e.matches ? 'light' : 'dark');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Resolved theme: what actually gets applied
  const theme: ResolvedTheme = preference === 'auto' ? systemTheme : preference;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', preference);
    const favicon = document.querySelector('link[rel="icon"]') as HTMLLinkElement | null;
    if (favicon) favicon.href = theme === 'light' ? '/logo-favicon.svg' : '/logo-favicon-dark.svg';
  }, [theme, preference]);

  const setTheme = (value: ThemePreference) => setPreference(value);

  const toggleTheme = () =>
    setPreference((prev) => {
      if (prev === 'dark') return 'light';
      if (prev === 'light') return 'auto';
      return 'dark';
    });

  const value = useMemo(
    () => ({ theme, preference, setTheme, toggleTheme }),
    [theme, preference],
  );

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
