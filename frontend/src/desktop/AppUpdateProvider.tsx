import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Update } from '@tauri-apps/plugin-updater'
import { AppUpdateContext, type AppUpdateState } from './appUpdate'
import { prepareForUpdate, retryBackend, shellInfo, type ShellInfo } from './shell'

const RECHECK_MS = 6 * 60 * 60 * 1000

function message(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason)
}

/**
 * GitHub Release updates for the installed app: checks at start and every six
 * hours. Install = download and verify the signed installer first, then stop the
 * backend, run the installer and restart; a failed download leaves the app
 * running as it was. A development build (`packaged: false`) only checks on demand.
 */
export function AppUpdateProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<ShellInfo | null>(null)
  const [update, setUpdate] = useState<Update | null>(null)
  const [checking, setChecking] = useState(false)
  const [progress, setProgress] = useState<AppUpdateState['progress']>(null)
  const [error, setError] = useState('')
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [dismissedVersion, setDismissedVersion] = useState('')
  const busy = useRef(false)

  const check = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setChecking(true)
    setError('')
    try {
      const { check: checkForUpdate } = await import('@tauri-apps/plugin-updater')
      setUpdate(await checkForUpdate())
      setLastChecked(new Date())
    } catch (reason) {
      setError(`Update check failed: ${message(reason)}`)
    } finally {
      busy.current = false
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    let timer = 0
    let cancelled = false
    void shellInfo().then((value) => {
      if (cancelled || !value) return
      setInfo(value)
      if (!value.packaged) return
      void check()
      timer = window.setInterval(() => void check(), RECHECK_MS)
    })
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [check])

  const install = useCallback(async () => {
    if (!update || busy.current) return
    busy.current = true
    setError('')
    setProgress({ done: 0, total: null })
    let stopped = false
    try {
      await update.download((event) => {
        if (event.event === 'Started') setProgress({ done: 0, total: event.data.contentLength ?? null })
        else if (event.event === 'Progress')
          setProgress((current) => ({ done: (current?.done ?? 0) + event.data.chunkLength, total: current?.total ?? null }))
      })
      await prepareForUpdate()
      stopped = true
      await update.install()
      const { relaunch } = await import('@tauri-apps/plugin-process')
      await relaunch()
    } catch (reason) {
      setError(`Update failed: ${message(reason)}`)
      setProgress(null)
      // Bring the backend back; the installed version keeps working.
      if (stopped) await retryBackend().catch(() => {})
    } finally {
      busy.current = false
    }
  }, [update])

  const value = useMemo<AppUpdateState>(
    () => ({
      info,
      update,
      checking,
      progress,
      error,
      lastChecked,
      noticeDismissed: !update || dismissedVersion === update.version,
      dismissNotice: () => setDismissedVersion(update?.version ?? ''),
      check,
      install,
    }),
    [info, update, checking, progress, error, lastChecked, dismissedVersion, check, install],
  )

  return <AppUpdateContext.Provider value={value}>{children}</AppUpdateContext.Provider>
}
