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
  const isScore5 = lead.scoring_score === 5

  const doNotSay = (() => {
    try { return JSON.parse(lead.dm_do_not_say || '[]') } catch {
      return lead.dm_do_not_say ? [lead.dm_do_not_say] : []
    }
  })()

  const talkingPoints = (() => {
    try { return JSON.parse(lead.talking_points || '[]') } catch {
      return lead.talking_points ? [lead.talking_points] : []
    }
  })()

  return (
    <div className={`border rounded-lg bg-card overflow-hidden ${
      isScore5 ? 'border-yellow-700' : 'border-border'
    }`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
        {isScore5 && <Star size={14} className="text-yellow-400 flex-shrink-0" />}
        <ScoreBadge score={lead.scoring_score} />
        <div className="flex-1 min-w-0">
          <p className="text-text font-semibold text-sm">{lead.company}</p>
          <p className="text-muted text-xs">{name} -- {lead.market}</p>
        </div>
        <span className="text-muted text-xs hidden sm:block">{lead.ghl_pipeline_stage || lead.status}</span>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: contact info */}
        <div className="space-y-3">
          {lead.contact_phone ? (
            <CopyablePhone phone={lead.contact_phone} />
          ) : (
            <p className="text-muted text-xs italic">No phone on file</p>
          )}

          {lead.contact_email && (
            <p className="text-muted text-xs font-mono">{lead.contact_email}</p>
          )}

          {lead.company_ig_handle && (
            <p className="text-muted text-xs">
              <span className="text-muted">IG:</span>{' '}
              <span className="text-text font-mono">{lead.company_ig_handle}</span>
            </p>
          )}

          {lead.fleet_size && (
            <p className="text-muted text-xs">
              Fleet: <span className="text-text font-mono">{lead.fleet_size} vehicles</span>
            </p>
          )}

          {lead.scoring_rationale && (
            <div>
              <p className="text-muted text-xs font-mono uppercase mb-1">Why call</p>
              <p className="text-xs text-text leading-relaxed">{lead.scoring_rationale}</p>
            </div>
          )}
        </div>

        {/* Right: talking points + do not say */}
        <div className="space-y-3">
          {talkingPoints.length > 0 && (
            <div>
              <p className="text-muted text-xs font-mono uppercase mb-1">Talking Points</p>
              <ul className="space-y-1">
                {talkingPoints.map((pt, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-text">
                    <span className="text-accent mt-0.5 flex-shrink-0">--</span>
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {doNotSay.length > 0 && (
            <div className="do-not-say">
              <p className="text-red-400 text-xs font-mono font-semibold flex items-center gap-1 mb-1">
                <AlertTriangle size={12} />
                Do Not Say
              </p>
              {doNotSay.map((item, i) => (
                <p key={i} className="text-xs">{item}</p>
              ))}
            </div>
          )}

          {talkingPoints.length === 0 && doNotSay.length === 0 && (
            <p className="text-muted text-xs italic">No talking points or restrictions on file.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function CallSheet({ leads, loading }) {
  const callLeads = leads.filter(l =>
    l.scoring_score === 5 ||
    l.status === 'warm' ||
    l.ghl_pipeline_stage === 'Responded' ||
    l.ghl_pipeline_stage === 'Demo Scheduled'
  )

  // Sort: score 5 first, then by score desc
  callLeads.sort((a, b) => (b.scoring_score || 0) - (a.scoring_score || 0))

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
        {callLeads.some(l => l.scoring_score === 5) && (
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
