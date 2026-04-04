import { RefreshCw, AlertCircle, Zap, AlertTriangle } from 'lucide-react'
import { formatRelative } from '../utils/formatters'

function StatPill({ label, value, accent }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-card border border-border">
      <span className="text-muted text-[10px] sm:text-xs">{label}</span>
      <span className={`font-mono font-semibold text-xs sm:text-sm ${accent ? 'text-accent' : 'text-text'}`}>
        {value ?? '--'}
      </span>
    </div>
  )
}

function ScoreMini({ score, count, colorClass }) {
  return (
    <div className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] sm:text-xs font-mono font-bold ${colorClass}`}>
      S{score} <span className="font-normal">{count}</span>
    </div>
  )
}

function GhlHealthDot({ ghlSynced, totalLeads }) {
  let color = 'bg-yellow-400'
  if (ghlSynced > 0) color = 'bg-green-400'
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
}

export default function TopBar({ leads, stats, ghlStatus, lastSynced, onRefresh, loading }) {
  // Compute stats from leads array directly for accuracy
  const allLeads = leads || []
  const totalLeads = allLeads.length
  const scoreCount = (s) => allLeads.filter(l => l.scoring?.score === s).length
  const pendingApproval = allLeads.filter(l => l.outreach?.approval_status === 'PENDING').length
  const demosScheduled = allLeads.filter(l => l.outreach?.demo_scheduled).length
  const responded = allLeads.filter(l => l.outreach?.response_received).length
  const ghlSynced = allLeads.filter(l => l.ghl?.in_ghl).length
  const staleCount = allLeads.filter(l => l.stale === true).length

  return (
    <header className="sticky top-0 z-30 bg-bg border-b border-border">
      <div className="px-3 py-2 flex flex-wrap items-center gap-2">
        {/* Brand */}
        <div className="flex items-center gap-1.5 mr-1">
          <Zap size={16} className="text-accent" />
          <span className="font-mono font-bold text-text text-xs tracking-wide">EXOTIQ</span>
          <span className="text-muted text-[10px] font-mono hidden sm:inline">INTELLIGENCE</span>
        </div>

        {/* Stats pills */}
        <div className="flex flex-wrap items-center gap-1.5 flex-1 min-w-0">
          <StatPill label="Leads" value={totalLeads} />

          {/* Score mini badges */}
          <div className="flex items-center gap-1">
            <ScoreMini score={5} count={scoreCount(5)} colorClass="score-5" />
            <ScoreMini score={4} count={scoreCount(4)} colorClass="score-4" />
            <ScoreMini score={3} count={scoreCount(3)} colorClass="score-3" />
          </div>

          <StatPill label="Pending" value={pendingApproval} accent={pendingApproval > 0} />
          {responded > 0 && <StatPill label="Responses" value={responded} accent />}
          {demosScheduled > 0 && <StatPill label="Demos" value={demosScheduled} accent />}
          {staleCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-card border border-orange-800">
              <AlertTriangle size={12} className="text-orange-500" />
              <span className="text-orange-400 text-xs font-mono">{staleCount} stale</span>
            </div>
          )}

          {/* GHL indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-card border border-border">
            <GhlHealthDot ghlSynced={ghlSynced} totalLeads={totalLeads} />
            <span className="text-muted text-xs">GHL</span>
            <span className="font-mono text-sm text-text">
              {ghlSynced}/{totalLeads}
            </span>
          </div>
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
