import { useAppUpdate } from '../desktop/appUpdate'

function megabytes(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Settings → Updates. Rendered only inside the desktop shell. */
export function UpdatesSettings() {
  const { info, update, checking, progress, error, lastChecked, check, install } = useAppUpdate()
  if (!info) return null

  const installing = progress !== null
  let status: string
  if (installing) {
    status = progress.total
      ? `Downloading ${megabytes(progress.done)} of ${megabytes(progress.total)}…`
      : `Downloading ${megabytes(progress.done)}…`
  } else if (checking) {
    status = 'Checking for updates…'
  } else if (update) {
    status = `Nihilux ${update.version} is available.`
  } else if (lastChecked) {
    status = `Nihilux is up to date (checked ${lastChecked.toLocaleTimeString()}).`
  } else {
    status = info.packaged ? 'Not checked yet.' : 'Development build: updates apply to the installed app.'
  }

  return (
    <fieldset className="settings-section">
      <legend>Updates</legend>
      <p className="settings-hint">
        Version {info.version}. Updates come from the Nihilux releases on GitHub, are verified before they
        install, and keep your projects and settings.
      </p>
      <p className="settings-hint" role="status">{status}</p>
      {update?.body ? <pre className="settings-release-notes">{update.body}</pre> : null}
      <div className="settings-key-row">
        <button type="button" className="ghost" onClick={() => void check()} disabled={checking || installing}>
          Check for updates
        </button>
        {update ? (
          <button type="button" className="primary" onClick={() => void install()} disabled={installing}>
            {installing ? 'Installing…' : 'Install and restart'}
          </button>
        ) : null}
      </div>
      {error ? <p className="settings-hint is-error" role="alert">{error}</p> : null}
    </fieldset>
  )
}
