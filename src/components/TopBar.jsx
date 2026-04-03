import { RefreshCw, AlertCircle, Zap } from 'lucide-react'
import { formatRelative, formatDateTime } from '../utils/formatters'

function StatPill({ label, value, accent }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-card border border-border">
      <span className="text-muted text-xs">{label}</span>
      <span className={`font-mono font-semibold text-sm ${accent ? 'text-accent' : 'text-text'}`}>
        {value ?? '--'}
      </span>
    </div>
  )
}

function GhlHealthDot({ status }) {
  const synced = status?.total_in_ghl ?? 0
  const errors = status?.sync_errors?.length ?? 0

  let color = 'bg-green-400'
  if (errors > 0) color = 'bg-red-400'
  else if (synced === 0) color = 'bg-yellow-400'

  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
}

export default function TopBar({ stats, ghlStatus, lastSynced, onRefresh, loading }) {
  const byScore = stats?.by_score || {}
  const totalLeads = stats?.total_leads ?? 0
  const pendingApproval = stats?.pending_approval ?? 0
  const ghlSynced = stats?.ghl_synced ?? 0
  const totalInGhl = ghlStatus?.total_in_ghl ?? 0
  const syncErrors = ghlStatus?.sync_errors?.length ?? 0
  const lastWebhook = ghlStatus?.last_sync_at

  return (
    <header className="sticky top-0 z-30 bg-bg border-b border-border">
      <div className="px-4 py-3 flex flex-wrap items-center gap-3">
        {/* Brand */}
        <div className="flex items-center gap-2 mr-2">
          <Zap size={18} className="text-accent" />
          <span className="font-mono font-bold text-text text-sm tracking-wide">EXOTIQ</span>
          <span className="text-muted text-xs font-mono">INTELLIGENCE</span>
        </div>

        {/* Stats pills */}
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <StatPill label="Total" value={totalLeads} />
          <StatPill label="S5" value={byScore[5] ?? 0} accent />
          <StatPill label="S4" value={byScore[4] ?? 0} />
          <StatPill label="S3" value={byScore[3] ?? 0} />
          <StatPill label="Pending" value={pendingApproval} accent={pendingApproval > 0} />

          {/* GHL indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-card border border-border">
            <GhlHealthDot status={ghlStatus} />
            <span className="text-muted text-xs">GHL</span>
            <span className="font-mono text-sm text-text">
              {ghlSynced}/{totalLeads}
            </span>
            <span className="text-muted text-xs">synced</span>
            {syncErrors > 0 && (
              <button
                className="flex items-center gap-1 text-red-400 text-xs hover:text-red-300"
                title="View sync errors"
                onClick={() => console.log('Sync errors:', ghlStatus?.sync_errors)}
              >
                <AlertCircle size={12} />
                {syncErrors} err
              </button>
            )}
          </div>

          {lastWebhook && (
            <span className="text-muted text-xs font-mono hidden lg:block">
              last webhook: {formatRelative(lastWebhook)}
            </span>
          )}
        </div>

        {/* Right: sync time + refresh */}
        <div className="flex items-center gap-3 ml-auto">
          {lastSynced && (
            <span className="text-muted text-xs font-mono hidden sm:block">
              synced {formatRelative(lastSynced.toISOString())}
            </span>
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border text-muted hover:text-accent hover:border-accent transition-all text-xs"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>
    </header>
  )
}
