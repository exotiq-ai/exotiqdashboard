import { useState } from 'react'
import TopBar from './components/TopBar'
import FilterBar from './components/FilterBar'
import LeadList from './components/LeadList'
import ApprovalQueue from './components/ApprovalQueue'
import CallSheet from './components/CallSheet'
import PipelineFunnel from './components/PipelineFunnel'
import ActivityFeed from './components/ActivityFeed'
import ExportTab from './components/ExportTab'
import { useLeadData } from './hooks/useLeadData'
import { applyFilters, getUniqueMarkets, getUniqueStatuses } from './utils/filters'

const TABS = [
  { id: 'leads', label: 'All Leads' },
  { id: 'approval', label: 'Approval Queue' },
  { id: 'callsheet', label: 'Call Sheet' },
  { id: 'funnel', label: 'Pipeline Funnel' },
  { id: 'activity', label: 'Activity Feed' },
  { id: 'export', label: 'Export' },
]

const DEFAULT_FILTERS = {
  markets: [],
  scores: [],
  statuses: [],
  search: '',
  sortBy: 'score_desc',
}

export default function App() {
  const [activeTab, setActiveTab] = useState('leads')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const {
    leads,
    activity,
    stats,
    ghlStatus,
    pipelineMetrics,
    loading,
    error,
    lastSynced,
    refresh,
  } = useLeadData()

  const markets = getUniqueMarkets(leads)
  const statuses = getUniqueStatuses(leads)
  const filteredLeads = applyFilters(leads, filters)

  const pendingCount = leads.filter(l => l.outreach?.approval_status === 'PENDING').length

  function handleAction(action, lead) {
    console.log(`[Action] ${action}:`, lead?.id, lead?.company)
  }

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col">
      {/* Top bar */}
      <TopBar
        stats={stats}
        ghlStatus={ghlStatus}
        lastSynced={lastSynced}
        onRefresh={refresh}
        loading={loading}
      />

      {/* Tab nav */}
      <nav className="sticky top-[53px] z-20 bg-bg border-b border-border px-4 flex gap-0 overflow-x-auto">
        {TABS.map(tab => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-xs font-medium flex-shrink-0 transition-all relative ${
                isActive
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-muted hover:text-text'
              }`}
            >
              {tab.label}
              {tab.id === 'approval' && pendingCount > 0 && (
                <span className="ml-1.5 bg-accent text-black text-[10px] font-bold rounded-full px-1.5 py-0.5">
                  {pendingCount}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Filter bar -- shown on leads tab */}
      {activeTab === 'leads' && (
        <FilterBar
          filters={filters}
          onChange={setFilters}
          markets={markets}
          statuses={statuses}
        />
      )}

      {/* Error banner */}
      {error && (
        <div className="mx-4 mt-3 px-4 py-3 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">
          Data load error: {error} -- Dashboard will retry in 30s.
        </div>
      )}

      {/* Tab content */}
      <main className="flex-1 overflow-auto">
        {activeTab === 'leads' && (
          <LeadList
            leads={filteredLeads}
            loading={loading}
            onAction={handleAction}
          />
        )}
        {activeTab === 'approval' && (
          <ApprovalQueue
            leads={leads}
            loading={loading}
            onAction={handleAction}
          />
        )}
        {activeTab === 'callsheet' && (
          <CallSheet
            leads={leads}
            loading={loading}
          />
        )}
        {activeTab === 'funnel' && (
          <PipelineFunnel
            metrics={pipelineMetrics}
            loading={loading}
          />
        )}
        {activeTab === 'activity' && (
          <ActivityFeed
            activity={activity}
            loading={loading}
          />
        )}
        {activeTab === 'export' && (
          <ExportTab
            leads={filteredLeads}
            loading={loading}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border px-4 py-2 flex items-center justify-between">
        <span className="text-muted text-xs font-mono">Exotiq AI -- Lead Intelligence Pipeline</span>
        <span className="text-muted text-xs font-mono">
          {lastSynced
            ? `Last synced: ${lastSynced.toLocaleTimeString()}`
            : 'Loading...'}
        </span>
      </footer>
    </div>
  )
}
