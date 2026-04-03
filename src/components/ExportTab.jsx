import { Download, ExternalLink, FileText, CheckCircle } from 'lucide-react'
import { exportToCsv } from '../utils/filters'
import { useState } from 'react'

function ExportButton({ label, description, onClick, disabled, icon: Icon = Download }) {
  const [done, setDone] = useState(false)

  function handleClick() {
    if (disabled) return
    onClick()
    setDone(true)
    setTimeout(() => setDone(false), 3000)
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={`flex items-start gap-4 p-4 rounded-lg border transition-all text-left w-full ${
        disabled
          ? 'border-border opacity-40 cursor-not-allowed'
          : 'border-border hover:border-accent hover:bg-card cursor-pointer'
      }`}
    >
      <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
        done ? 'bg-accent' : 'bg-card border border-border'
      }`}>
        {done
          ? <CheckCircle size={18} className="text-black" />
          : <Icon size={18} className="text-accent" />
        }
      </div>
      <div>
        <p className="text-text font-semibold text-sm">{label}</p>
        <p className="text-muted text-xs mt-0.5">{description}</p>
        {done && <p className="text-accent text-xs mt-1">Downloaded!</p>}
      </div>
    </button>
  )
}

function PlaceholderButton({ label, description }) {
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg border border-border border-dashed opacity-60">
      <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-card border border-border">
        <ExternalLink size={18} className="text-muted" />
      </div>
      <div>
        <p className="text-text font-semibold text-sm">{label}</p>
        <p className="text-muted text-xs mt-0.5">{description}</p>
        <p className="text-yellow-600 text-xs mt-1">Coming soon</p>
      </div>
    </div>
  )
}

export default function ExportTab({ leads, loading }) {
  const approvedLeads = leads.filter(l => l.outreach?.approval_status === 'APPROVED')
  const score5Leads = leads.filter(l => l.scoring?.score === 5)
  const score4Plus = leads.filter(l => (l.scoring?.score || 0) >= 4)

  return (
    <div className="p-6 max-w-2xl">
      <h3 className="text-text font-semibold text-sm mb-1">Export Data</h3>
      <p className="text-muted text-xs mb-6">Download lead data as CSV for reporting or import into other tools.</p>

      <div className="space-y-3">
        <ExportButton
          label="All Leads -- CSV"
          description={`Export all ${leads.length} leads with full field set`}
          onClick={() => exportToCsv(leads, 'exotiq-all-leads.csv')}
          disabled={loading || leads.length === 0}
        />

        <ExportButton
          label="Score 4 + 5 Leads -- CSV"
          description={`${score4Plus.length} high-priority leads (Score 4 and 5)`}
          onClick={() => exportToCsv(score4Plus, 'exotiq-score4plus.csv')}
          disabled={loading || score4Plus.length === 0}
        />

        <ExportButton
          label="Score 5 Only -- Gregory's List"
          description={`${score5Leads.length} top-tier leads for personal outreach`}
          onClick={() => exportToCsv(score5Leads, 'exotiq-score5-gregory.csv')}
          disabled={loading || score5Leads.length === 0}
          icon={FileText}
        />

        <ExportButton
          label="Approved DM Drafts -- CSV"
          description={`${approvedLeads.length} approved leads with DM copy and talking points`}
          onClick={() => exportToCsv(approvedLeads, 'exotiq-approved-dms.csv')}
          disabled={loading || approvedLeads.length === 0}
        />

        <div className="pt-2 border-t border-border">
          <p className="text-muted text-xs font-mono uppercase tracking-wider mb-3">Integrations</p>

          <PlaceholderButton
            label="Push to Google Sheets"
            description="Sync all leads to a Google Sheets document for team access"
          />

          <div className="mt-3">
            <PlaceholderButton
              label="GHL Bulk Import"
              description="Push multiple approved leads to GoHighLevel in one operation"
            />
          </div>
        </div>
      </div>

      <div className="mt-6 p-4 bg-card border border-border rounded-lg">
        <p className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Export Notes</p>
        <ul className="space-y-1 text-xs text-muted">
          <li>-- CSVs include all lead fields including provenance metadata</li>
          <li>-- DM draft export includes the full message copy for copy/paste</li>
          <li>-- GHL push is available per-lead from the Approval Queue tab</li>
          <li>-- All timestamps are in UTC ISO 8601 format</li>
        </ul>
      </div>
    </div>
  )
}
