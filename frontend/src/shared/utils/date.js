export function toLocalDateString(isoDateTime) {
  if (!isoDateTime) return '-';
  const date = new Date(isoDateTime);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function toPercent(value) {
  if (typeof value !== 'number') return '0.00';
  return value.toFixed(2);
}
