/**
 * The Nihilux desktop shell (desktop/src-tauri) when the app runs inside it.
 * In a browser or the pywebview development launcher these report "not in the
 * shell" and the update UI stays hidden.
 */

export interface ShellInfo {
  version: string
  /** True for an installed app; false for a development build from a checkout. */
  packaged: boolean
}

export function inDesktopShell(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

async function invoke<T>(command: string): Promise<T> {
  const { invoke: tauriInvoke } = await import('@tauri-apps/api/core')
  return tauriInvoke<T>(command)
}

export async function shellInfo(): Promise<ShellInfo | null> {
  if (!inDesktopShell()) return null
  try {
    return await invoke<ShellInfo>('app_info')
  } catch {
    return null
  }
}

/** Stop the backend (and anything else running from the install folder) before installing. */
export function prepareForUpdate(): Promise<void> {
  return invoke<void>('prepare_for_update')
}

/** Start the backend again, e.g. after an update that failed to install. */
export function retryBackend(): Promise<void> {
  return invoke<void>('retry_backend')
}
