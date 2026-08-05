// Thin wrapper around Umami's global `window.umami.track(...)`. No-ops
// silently when the Umami script tag isn't present (dev, tests, and
// production until a real Website ID is added to index.html) -- callers
// never need to guard against Umami being absent.
declare global {
  interface Window {
    umami?: { track: (event: string, data?: Record<string, unknown>) => void };
  }
}

export function track(event: string, data?: Record<string, unknown>): void {
  window.umami?.track(event, data);
}
