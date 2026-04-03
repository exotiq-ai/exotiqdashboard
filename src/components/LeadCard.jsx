import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Copy, Phone, Mail, Globe,
  Instagram, CheckCircle, XCircle, Edit3, Flag, AlertTriangle
} from 'lucide-react'
import ScoreBadge from './ScoreBadge'
import GhlBadge from './GhlBadge'
import ProvenanceTag from './ProvenanceTag'
import { formatRelative, formatDateTime, formatPhone, contactName } from '../utils/formatters'

function CopyButton({ text, children }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 text-muted hover:text-accent transition-all group"
      title={`Copy: ${text}`}
    >
      {children}
      {copied
        ? <CheckCircle size={12} className="text-accent" />
        : <Copy size={12} className="opacity-0 group-hover:opacity-100" />
      }
    </button>
  )
}

function ExpandedDetail({ lead, onAction }) {
  const vehicleTypes = (() => {
    try { return JSON.parse(lead.fleet_vehicle_types || '[]') } catch { return [] }
  })()

  const doNotSay = (() => {
    try { return JSON.parse(lead.dm_do_not_say || '[]') } catch {
      return lead.dm_do_not_say ? [lead.dm_do_not_say] : []
    }
  })()

  const isPending = lead.dm_approval_status === 'PENDING'

  return (
    <div className="border-t border-border mt-2 pt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Left column */}
      <div className="space-y-4">
        {/* Contact info */}
        <section>
          <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Contact</h4>
          <div className="space-y-1.5">
            {lead.contact_phone && (
              <CopyButton text={lead.contact_phone}>
                <Phone size={13} className="text-muted" />
                <span className="text-sm font-mono text-text">{formatPhone(lead.contact_phone)}</span>
              </CopyButton>
            )}
            {lead.contact_email && (
              <CopyButton text={lead.contact_email}>
                <Mail size={13} className="text-muted" />
                <span className="text-sm font-mono text-text">{lead.contact_email}</span>
              </CopyButton>
            )}
            {lead.company_website && (
              <div className="flex items-center gap-1 text-muted">
                <Globe size={13} />
                <a href={lead.company_website} target="_blank" rel="noopener noreferrer"
                  className="text-sm font-mono text-blue-400 hover:text-blue-300 truncate">
                  {lead.company_website}
                </a>
              </div>
            )}
            {lead.company_ig_handle && (
              <div className="flex items-center gap-1 text-muted">
                <Instagram size={13} />
                <span className="text-sm font-mono text-text">{lead.company_ig_handle}</span>
                {lead.company_ig_followers && (
                  <span className="text-xs text-muted">({Number(lead.company_ig_followers).toLocaleString()} followers)</span>
                )}
              </div>
            )}
            {lead.company_address && (
              <p className="text-xs text-muted pl-1">{lead.company_address}</p>
            )}
          </div>
        </section>

        {/* Fleet info */}
        <section>
          <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Fleet</h4>
          <div className="space-y-1">
            {lead.fleet_size && (
              <div className="flex items-center gap-2">
                <span className="font-mono text-text text-sm">{lead.fleet_size} vehicles</span>
                <ProvenanceTag source={lead.fleet_size_source} confidence={lead.fleet_size_confidence} />
              </div>
            )}
            {vehicleTypes.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {vehicleTypes.map(v => (
                  <span key={v} className="px-2 py-0.5 rounded bg-border text-xs text-muted font-mono">{v}</span>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* GHL status */}
        <section>
          <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">GHL Status</h4>
          <div className="flex items-center gap-2">
            <GhlBadge lead={lead} />
            {lead.ghl_contact_id && (
              <button
                className="text-xs text-blue-400 hover:text-blue-300"
                onClick={() => console.log('Open GHL contact:', lead.ghl_contact_id)}
              >
                Open in GHL
              </button>
            )}
          </div>
        </section>

        {/* Score rationale */}
        {lead.scoring_rationale && (
          <section>
            <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Score Rationale</h4>
            <p className="text-xs text-text leading-relaxed bg-card border border-border rounded p-3">
              {lead.scoring_rationale}
            </p>
          </section>
        )}

        {/* Notes */}
        <section>
          <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Notes</h4>
          <p className="text-xs text-text leading-relaxed">
            {lead.notes || <span className="text-muted italic">No notes</span>}
          </p>
        </section>
      </div>

      {/* Right column */}
      <div className="space-y-4">
        {/* DO NOT SAY */}
        {doNotSay.length > 0 && (
          <section>
            <h4 className="text-red-400 text-xs font-mono uppercase tracking-wider mb-2 flex items-center gap-1">
              <AlertTriangle size={12} />
              Do Not Say
            </h4>
            <div className="do-not-say space-y-1">
              {doNotSay.map((item, i) => (
                <p key={i} className="text-xs">{item}</p>
              ))}
            </div>
          </section>
        )}

        {/* DM Draft */}
        {lead.dm_draft && (
          <section>
            <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">
              DM Draft
              {lead.dm_template_used && (
                <span className="ml-2 text-accent">Template {lead.dm_template_used}</span>
              )}
            </h4>
            <div className="bg-card border border-border rounded p-3">
              <p className="text-xs text-text leading-relaxed whitespace-pre-wrap">{lead.dm_draft}</p>
            </div>

            {/* Approval buttons */}
            {isPending && (
              <div className="flex gap-2 mt-2">
                <button
                  onClick={() => onAction('approve', lead)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent text-black text-xs font-semibold hover:bg-green-400 transition-all"
                >
                  <CheckCircle size={13} />
                  Approve
                </button>
                <button
                  onClick={() => onAction('edit', lead)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border text-muted hover:text-text text-xs transition-all"
                >
                  <Edit3 size={13} />
                  Edit
                </button>
                <button
                  onClick={() => onAction('reject', lead)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-red-900 text-red-400 hover:bg-red-950 text-xs transition-all"
                >
                  <XCircle size={13} />
                  Reject
                </button>
              </div>
            )}

            {lead.dm_approval_status === 'APPROVED' && (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-accent flex items-center gap-1">
                  <CheckCircle size={12} />
                  Approved
                </span>
                {!lead.ghl_contact_id && (
                  <button
                    onClick={() => onAction('push_to_ghl', lead)}
                    className="px-3 py-1 rounded bg-blue-900 text-blue-300 text-xs hover:bg-blue-800 transition-all"
                  >
                    Push to GHL
                  </button>
                )}
              </div>
            )}
          </section>
        )}

        {/* Quick actions */}
        <section>
          <h4 className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Quick Actions</h4>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onAction('push_to_ghl', lead)}
              className="px-3 py-1.5 rounded border border-border text-muted hover:text-accent hover:border-accent text-xs transition-all"
            >
              Push to GHL
            </button>
            <button
              onClick={() => onAction('flag_for_call', lead)}
              className="flex items-center gap-1 px-3 py-1.5 rounded border border-border text-muted hover:text-yellow-400 hover:border-yellow-700 text-xs transition-all"
            >
              <Flag size={12} />
              Flag for Call
            </button>
            <button
              onClick={() => onAction('send_to_gregory', lead)}
              className="px-3 py-1.5 rounded border border-border text-muted hover:text-yellow-400 hover:border-yellow-700 text-xs transition-all"
            >
              Send to Gregory
            </button>
            <button
              onClick={() => onAction('not_a_fit', lead)}
              className="px-3 py-1.5 rounded border border-red-900 text-red-400 hover:bg-red-950 text-xs transition-all"
            >
              Not a Fit
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}

export default function LeadCard({ lead, onAction }) {
  const [expanded, setExpanded] = useState(false)

  const name = contactName(lead)
  const updatedAgo = formatRelative(lead.updated_at)

  return (
    <div
      className={`lead-card border border-border rounded-lg overflow-hidden transition-all ${
        expanded ? 'bg-card' : 'bg-card hover:border-gray-600'
      }`}
    >
      {/* Collapsed row */}
      <button
        className="w-full text-left px-4 py-3"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Toggle icon */}
          <span className="text-muted flex-shrink-0">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>

          {/* Company */}
          <span className="font-semibold text-text text-sm truncate min-w-0 max-w-48">
            {lead.company}
          </span>

          {/* Contact */}
          <span className="text-muted text-xs truncate hidden sm:block min-w-0 max-w-32">
            {name}
          </span>

          {/* Score */}
          <ScoreBadge score={lead.scoring_score} />

          {/* Market */}
          <span className="text-muted text-xs font-mono hidden md:block flex-shrink-0">
            {lead.market || '--'}
          </span>

          {/* Status */}
          <span className="text-muted text-xs hidden lg:block flex-shrink-0">
            {lead.status || '--'}
          </span>

          {/* GHL */}
          <div className="hidden xl:block flex-shrink-0">
            <GhlBadge lead={lead} />
          </div>

          {/* Updated */}
          <span className="text-muted text-xs font-mono ml-auto flex-shrink-0">
            {updatedAgo}
          </span>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4">
          <ExpandedDetail lead={lead} onAction={onAction} />
        </div>
      )}
    </div>
  )
}
