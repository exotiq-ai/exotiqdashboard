import { useState } from 'react'
import { Phone, Copy, CheckCircle, AlertTriangle, Star } from 'lucide-react'
import ScoreBadge from './ScoreBadge'
import { formatPhone, contactName } from '../utils/formatters'

function CopyablePhone({ phone }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    if (!phone) return
    navigator.clipboard.writeText(phone).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-2 px-3 py-2 rounded border border-border hover:border-accent bg-bg group transition-all"
      title="Click to copy"
    >
      <Phone size={14} className="text-accent" />
      <span className="font-mono text-text text-sm">{formatPhone(phone)}</span>
      {copied
        ? <CheckCircle size={13} className="text-accent" />
        : <Copy size={13} className="text-muted opacity-0 group-hover:opacity-100" />
      }
    </button>
  )
}

function CallCard({ lead }) {
  const name = contactName(lead)
  const scoring = lead.scoring || {}
  const contact = lead.contact || {}
  const companyData = lead.company_data || {}
  const fleet = lead.fleet || {}
  const outreach = lead.outreach || {}
  const isScore5 = scoring.score === 5

  const doNotSay = (() => {
    const raw = outreach.do_not_say
    if (Array.isArray(raw)) return raw
    try { return JSON.parse(raw || '[]') } catch {
      return raw ? [raw] : []
    }
  })()

  return (
    <div className={`border rounded-lg bg-card overflow-hidden ${
      isScore5 ? 'border-yellow-700' : 'border-border'
    }`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
        {isScore5 && <Star size={14} className="text-yellow-400 flex-shrink-0" />}
        <ScoreBadge score={scoring.score} />
        <div className="flex-1 min-w-0">
          <p className="text-text font-semibold text-sm">{lead.company}</p>
          <p className="text-muted text-xs">{name}{contact.title ? ` -- ${contact.title}` : ''} -- {lead.market}</p>
        </div>
        <span className="text-muted text-xs hidden sm:block">{lead.ghl?.pipeline_stage || outreach.status}</span>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: contact info */}
        <div className="space-y-3">
          {contact.phone ? (
            <CopyablePhone phone={contact.phone} />
          ) : (
            <p className="text-muted text-xs italic">No phone on file</p>
          )}

          {contact.email && (
            <p className="text-muted text-xs font-mono">{contact.email}</p>
          )}

          {companyData.ig_handle && (
            <p className="text-muted text-xs">
              <span className="text-muted">IG:</span>{' '}
              <span className="text-text font-mono">{companyData.ig_handle}</span>
              {companyData.ig_followers && (
                <span className="text-accent ml-1">({Number(companyData.ig_followers).toLocaleString()})</span>
              )}
            </p>
          )}

          {fleet.size && (
            <p className="text-muted text-xs">
              Fleet: <span className="text-text font-mono">{fleet.size} vehicles</span>
            </p>
          )}

          {scoring.rationale && (
            <div>
              <p className="text-muted text-xs font-mono uppercase mb-1">Intel</p>
              <p className="text-xs text-text leading-relaxed max-h-24 overflow-y-auto">{scoring.rationale}</p>
            </div>
          )}
        </div>

        {/* Right: outreach status + notes + do not say */}
        <div className="space-y-3">
          {/* Outreach status */}
          {(outreach.response_received || outreach.response_category) && (
            <div className="p-2 rounded bg-green-900/20 border border-green-900/50">
              <p className="text-green-400 text-xs font-semibold">Response: {outreach.response_category}</p>
              {outreach.response_date && (
                <p className="text-xs text-muted mt-0.5">Date: {outreach.response_date}</p>
              )}
            </div>
          )}

          {/* Notes */}
          {lead.notes && (
            <div>
              <p className="text-muted text-xs font-mono uppercase mb-1">Notes</p>
              <p className="text-xs text-text leading-relaxed">{lead.notes}</p>
            </div>
          )}

          {/* DO NOT SAY */}
          {doNotSay.length > 0 && doNotSay.some(s => s && s.trim()) && (
            <div className="bg-red-950/30 border border-red-900/50 rounded-lg p-3">
              <p className="text-red-400 text-xs font-mono font-semibold flex items-center gap-1 mb-1">
                <AlertTriangle size={12} />
                Do Not Say
              </p>
              {doNotSay.filter(s => s && s.trim()).map((item, i) => (
                <p key={i} className="text-xs text-red-300">{item}</p>
              ))}
            </div>
          )}

          {!lead.notes && doNotSay.length === 0 && !outreach.response_category && (
            <p className="text-muted text-xs italic">No talking points or restrictions on file.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function CallSheet({ leads, loading }) {
  const callLeads = leads.filter(l => {
    const score = l.scoring?.score
    const status = l.outreach?.status
    const respCat = l.outreach?.response_category
    const ghlStage = l.ghl?.pipeline_stage
    return (
      score === 5 ||
      status === 'Responded' ||
      status === 'Demo Scheduled' ||
      (respCat && respCat.toLowerCase().includes('interested')) ||
      ghlStage === 'Responded -- Warm' ||
      ghlStage === 'Demo Scheduled'
    )
  })

  callLeads.sort((a, b) => (b.scoring?.score || 0) - (a.scoring?.score || 0))

  if (loading) {
    return (
      <div className="p-4 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="border border-border rounded-lg bg-card p-4">
            <div className="skeleton w-32 h-4 mb-3 rounded" />
            <div className="skeleton w-full h-16 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (callLeads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Phone size={40} className="text-muted mb-4" />
        <p className="text-text font-semibold">No call-ready leads</p>
        <p className="text-muted text-xs mt-1">
          Score 5 leads and warm/responding leads appear here.
        </p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-muted text-xs font-mono">{callLeads.length} lead{callLeads.length !== 1 ? 's' : ''} ready for outreach</p>
        {callLeads.some(l => l.scoring?.score === 5) && (
          <p className="text-yellow-400 text-xs flex items-center gap-1">
            <Star size={12} />
            Score 5 leads: Gregory handles personally
          </p>
        )}
      </div>
      {callLeads.map(lead => (
        <CallCard key={lead.id} lead={lead} />
      ))}
    </div>
  )
}
