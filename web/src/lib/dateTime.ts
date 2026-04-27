function normalizeDateInput(value: string): string {
  const trimmed = value.trim().replace(' ', 'T');
  if (!trimmed) return trimmed;

  // Treat naive timestamps from the backend/database as UTC.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(trimmed)) {
    return `${trimmed}Z`;
  }

  return trimmed;
}

export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const normalized = normalizeDateInput(value);
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}
