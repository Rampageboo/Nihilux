/**
 * Base URL for API calls. The app is always served by the backend it talks to
 * (the desktop shell's window loads http://127.0.0.1:<port>/), so requests are
 * same-origin and relative.
 */
export function apiBase(): string {
  return ''
}
