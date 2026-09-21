const TENTHS_PER_HOUR = 36000;
const TENTHS_PER_MINUTE = 600;
const SECONDS_PER_HOUR = 3600;

function scaledSeconds(seconds: number, scale: number): number {
  if (!Number.isFinite(seconds)) {
    return 0;
  }
  return Math.max(0, seconds) * scale;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatTimestamp(seconds: number): string {
  const tenths = Math.round(scaledSeconds(seconds, 10));
  const hours = Math.floor(tenths / TENTHS_PER_HOUR);
  const minutes = Math.floor((tenths % TENTHS_PER_HOUR) / TENTHS_PER_MINUTE);
  const rest = (tenths % TENTHS_PER_MINUTE) / 10;
  const secondsText = rest.toFixed(1).padStart(4, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${secondsText}` : `${minutes}:${secondsText}`;
}

export function formatClock(seconds: number): string {
  const total = Math.floor(scaledSeconds(seconds, 1));
  const hours = Math.floor(total / SECONDS_PER_HOUR);
  const minutes = Math.floor((total % SECONDS_PER_HOUR) / 60);
  const rest = total % 60;
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
}
