export function isAvailable(value) {
  return value != null && value !== '' && Number.isFinite(Number(value));
}

export function chartMaximum(rows, keys) {
  return Math.max(
    1,
    ...rows.flatMap((row) =>
      keys.filter((key) => isAvailable(row[key])).map((key) => Number(row[key])),
    ),
  );
}

export function linePath(rows, key, x, y) {
  let connected = false;
  return rows
    .map((row, index) => {
      if (!isAvailable(row[key])) {
        connected = false;
        return '';
      }
      const command = connected ? 'L' : 'M';
      connected = true;
      return `${command} ${x(index).toFixed(1)} ${y(row[key]).toFixed(1)}`;
    })
    .filter(Boolean)
    .join(' ');
}
