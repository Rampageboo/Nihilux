import { useEffect, useState } from 'react'
import { getIntegrations, openIntegration, type IntegrationsInfo } from '../api'

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    return
  } catch {
    // Fall back to a selection copy where the async clipboard is unavailable.
  }
  const area = document.createElement('textarea')
  area.value = text
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  const ok = document.execCommand('copy')
  area.remove()
  if (!ok) throw new Error('Copy failed. Select the text below and copy it.')
}

/** Settings → Integrations: Photoshop plugin, Blender add-on and the MCP config for agents. */
export function IntegrationsSettings() {
  const [info, setInfo] = useState<IntegrationsInfo | null>(null)
  const [message, setMessage] = useState('')
  const [showJson, setShowJson] = useState(false)

  useEffect(() => {
    getIntegrations().then(setInfo).catch(() => setInfo(null))
  }, [])

  if (!info) return null
  const mcpJson = JSON.stringify(info.mcp_config, null, 2)

  const run = async (action: () => Promise<string>) => {
    setMessage('')
    try {
      setMessage(await action())
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <fieldset className="settings-section">
      <legend>Integrations</legend>
      <p className="settings-hint">
        {info.photoshop_plugin_kind === 'ccx'
          ? 'Install the Photoshop panel once; Creative Cloud asks to confirm. Reinstall it after a Nihilux update that changes the plugin.'
          : 'Development checkout: load the Photoshop plugin folder with Adobe UXP Developer Tool.'}
      </p>
      <div className="settings-key-row">
        <button
          type="button"
          className="ghost"
          disabled={!info.photoshop_plugin}
          onClick={() => void run(async () => {
            await openIntegration('photoshop_plugin')
            return info.photoshop_plugin_kind === 'ccx' ? 'Opening the plugin installer…' : 'Opened the plugin folder.'
          })}
        >
          {info.photoshop_plugin_kind === 'ccx' ? 'Install Photoshop plugin' : 'Photoshop plugin folder'}
        </button>
        <button
          type="button"
          className="ghost"
          onClick={() => void run(async () => {
            await openIntegration('blender_addon')
            return 'Opened the Blender add-on folder. Nihilux loads it into Blender by itself when it opens a scene.'
          })}
        >
          Blender add-on folder
        </button>
      </div>
      <p className="settings-hint">
        Let Claude Code or Codex drive this app: add this server to the agent&apos;s MCP config (for Claude Code,
        <code> .mcp.json</code> or <code>claude mcp add-json</code>).
      </p>
      <div className="settings-key-row">
        <button type="button" className="ghost" onClick={() => void run(async () => {
          await copyText(mcpJson)
          return 'MCP config copied.'
        })}>
          Copy MCP config
        </button>
        <button type="button" className="ghost" onClick={() => setShowJson((value) => !value)}>
          {showJson ? 'Hide' : 'Show'}
        </button>
      </div>
      {showJson ? <pre className="settings-release-notes">{mcpJson}</pre> : null}
      {message ? <p className="settings-hint" role="status">{message}</p> : null}
    </fieldset>
  )
}
