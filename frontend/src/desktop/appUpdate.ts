import { createContext, useContext } from 'react'
import type { Update } from '@tauri-apps/plugin-updater'
import type { ShellInfo } from './shell'

export interface AppUpdateState {
  /** Null outside the desktop shell: the update UI is hidden. */
  info: ShellInfo | null
  update: Update | null
  checking: boolean
  /** Bytes downloaded / total while installing; null when idle. */
  progress: { done: number; total: number | null } | null
  error: string
  lastChecked: Date | null
  /** The user closed the start-up notice for this version. */
  noticeDismissed: boolean
  dismissNotice: () => void
  check: () => Promise<void>
  install: () => Promise<void>
}

const idle: AppUpdateState = {
  info: null,
  update: null,
  checking: false,
  progress: null,
  error: '',
  lastChecked: null,
  noticeDismissed: true,
  dismissNotice: () => {},
  check: async () => {},
  install: async () => {},
}

export const AppUpdateContext = createContext<AppUpdateState>(idle)

export function useAppUpdate(): AppUpdateState {
  return useContext(AppUpdateContext)
}
