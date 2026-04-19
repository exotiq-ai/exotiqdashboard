import { useState } from 'react'
import TopBar from './components/TopBar'
import FilterBar from './components/FilterBar'
import LeadList from './components/LeadList'
import ApprovalQueue from './components/ApprovalQueue'
import CallSheet from './components/CallSheet'
import PipelineFunnel from './components/PipelineFunnel'
import ActivityFeed from './components/ActivityFeed'
import ExportTab from './components/ExportTab'
import SequencesTab from './components/SequencesTab'
import { useLeadData } from './hooks/useLeadData'
import { applyFilters, getUniqueMarkets, getUniqueStatuses } from './utils/filters'

const TABS = [
  { id: 'leads', label: 'All Leads' },
  { id: 'approval', label: 'Approval Queue' },
  { id: 'sequences', label: 'Sequences' },
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
    updateLead,
    sequences,
    outreachQueue,
    leadSequences,
  } = useLeadData()

  const markets = getUniqueMarkets(leads)
  const statuses = getUniqueStatuses(leads)
  const filteredLeads = applyFilters(leads, filters)

  const pendingCount = leads.filter(l => l.outreach?.approval_status === 'PENDING').length

  const [pushingToGhl, setPushingToGhl] = useState(null)

  async function handleAction(action, lead, extra) {
    if (!lead?.id) return

    switch (action) {
      case 'save_dm':
        updateLead(lead.id, { dm_draft: lead?.outreach?.dm_draft }, 'save')
        break

      case 'save_dm_edit':
        updateLead(lead.id, { dm_draft: extra }, 'save')
        break

      case 'approve':
        updateLead(lead.id, { approval_status: 'APPROVED' }, 'approve')
        break

      case 'reject':
        updateLead(lead.id, { approval_status: 'REJECTED' }, 'reject')
        break

      case 'hold':
        updateLead(lead.id, { status: 'On Hold', approval_status: 'ON_HOLD' }, 'hold')
        break

      case 'not_a_fit':
        updateLead(lead.id, { status: 'Not a Fit', approval_status: 'REJECTED' }, 'not_a_fit')
        break

      case 'push_to_ghl':
        // Check if already in GHL locally
        if (lead.ghl?.contact_id || lead.ghl?.in_ghl) {
          alert(`${lead.company} is already in GHL. Use "Open in GHL" to view the contact.`)
          break
        }
        setPushingToGhl(lead.id)
        try {
          const res = await fetch('/.netlify/functions/push-to-ghl', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead }),
          })
          const data = await res.json()
          if (data.alreadyExists) {
            alert(`${lead.company} is already in GHL.`)
          } else if (data.success) {
            updateLead(lead.id, {
              status: data.stage || 'In GHL',
            }, 'push_to_ghl')
            alert(`✅ ${lead.company} pushed to GHL!\nStage: ${data.stage}\nValue: $${data.monetary?.toLocaleString()}/yr`)
          } else {
            alert(`GHL push failed: ${data.error || 'Unknown error'}`)
          }
        } catch (err) {
          alert(`GHL push failed: ${err.message}`)
        } finally {
          setPushingToGhl(null)
        }
        break

      case 'flag_for_call':
        updateLead(lead.id, { status: 'Call Scheduled' }, 'flag_for_call')
        break

      case 'send_to_gregory':
        updateLead(lead.id, { status: 'Gregory -- Personal Outreach' }, 'send_to_gregory')
        break

      default:
        console.log(`[Action] ${action}:`, lead?.id, lead?.company)
    }
  }

  const totalPipelineValue = leads.reduce((sum, l) => sum + (l.pricing?.annual_value || 0), 0)

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col">
      {/* Top bar */}
      <TopBar
        leads={leads}
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
        {activeTab === 'sequences' && (
          <SequencesTab
            sequences={sequences}
            queue={outreachQueue}
            enrollments={leadSequences}
            loading={loading}
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
            leads={leads}
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
      <footer className="border-t border-border px-4 py-2 flex items-center justify-between flex-wrap gap-2">
        <span className="text-muted text-xs font-mono">Exotiq AI -- Lead Intelligence Pipeline</span>
        {totalPipelineValue > 0 && (
          <span className="text-accent text-xs font-mono font-semibold">
            Pipeline: ${(totalPipelineValue / 1000).toFixed(0)}K/yr
          </span>
        )}
        <span className="text-muted text-xs font-mono">
          {lastSynced
            ? `Last synced: ${lastSynced.toLocaleTimeString()}`
            : 'Loading...'}
        </span>
      </footer>
    </div>
  )
}
