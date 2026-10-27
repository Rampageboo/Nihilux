import { X } from '@phosphor-icons/react'
import { useAppUpdate } from '../desktop/appUpdate'

/** Start-up notice when the installed app finds a newer release. */
export function UpdateNotice() {
  const { update, progress, error, noticeDismissed, dismissNotice, install } = useAppUpdate()
  if (!update || (noticeDismissed && !progress && !error)) return null
  const installing = progress !== null
  return (
    <div className="app-banner app-banner-info" role="status">
      <span>
        {error
          ? error
          : installing
            ? `Installing Nihilux ${update.version}… the app restarts when it is done.`
            : `Nihilux ${update.version} is available.`}
      </span>
      <span className="app-banner-actions">
        {!installing ? (
          <button type="button" className="primary" onClick={() => void install()}>
            Install and restart
          </button>
        ) : null}
        {!installing ? (
          <button type="button" className="ghost icon-btn" onClick={dismissNotice} aria-label="Later">
            <X size={14} />
          </button>
        ) : null}
      </span>
    </div>
  )
}
