import { useState } from 'react'
import { CheckCircle, XCircle, Edit3, ChevronUp, AlertTriangle } from 'lucide-react'
import ScoreBadge from './ScoreBadge'
import GhlBadge from './GhlBadge'
import { formatRelative, contactName, formatPhone } from '../utils/formatters'

function ConfirmGhlPush({ lead, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-card border border-border rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
        <h3 className="text-text font-semibold text-sm mb-2">Push to GHL?</h3>
        <p className="text-muted text-xs mb-1">
          This will create a contact in GoHighLevel for:
        </p>
        <p className="text-accent font-semibold text-sm mb-4">{lead.company}</p>
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2 rounded bg-accent text-black text-xs font-semibold hover:bg-green-400 transition-all"
          >
            Confirm Push
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded border border-border text-muted hover:text-text text-xs transition-all"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

function ApprovalCard({ lead, onAction }) {
  const [expanded, setExpanded] = useState(true)
  const [showGhlConfirm, setShowGhlConfirm] = useState(false)
  const [approved, setApproved] = useState(false)
  const [editing, setEditing] = useState(false)
  const [dmText, setDmText] = useState((lead.outreach || {}).dm_draft || '')

  const name = contactName(lead)
  const outreach = lead.outreach || {}
  const scoring = lead.scoring || {}

  const doNotSay = (() => {
    const raw = outreach.do_not_say
    if (Array.isArray(raw)) return raw
    try { return JSON.parse(raw || '[]') } catch {
      return raw ? [raw] : []
    }
  })()

  function handleApprove() {
    setApproved(true)
    setShowGhlConfirm(true)
    onAction('approve', lead)
  }

  function handleGhlConfirm() {
    setShowGhlConfirm(false)
    onAction('push_to_ghl', lead)
  }

  return (
    <>
      {showGhlConfirm && (
        <ConfirmGhlPush
          lead={lead}
          onConfirm={handleGhlConfirm}
          onCancel={() => setShowGhlConfirm(false)}
        />
      )}

      <div className="border border-border rounded-lg bg-card overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <ScoreBadge score={scoring.score} />
          <div className="flex-1 min-w-0">
            <p className="text-text font-semibold text-sm truncate">{lead.company}</p>
            <p className="text-muted text-xs">{name} -- {lead.market}</p>
          </div>
          <GhlBadge lead={lead} />
          <span className="text-muted text-xs font-mono hidden sm:block">{formatRelative(lead.updated_at)}</span>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-muted hover:text-text"
          >
            <ChevronUp size={14} className={expanded ? '' : 'rotate-180'} />
          </button>
        </div>

        {expanded && (
          <div className="p-4 space-y-4">
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

            {/* DM Draft */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-muted text-xs font-mono uppercase tracking-wider">
                  DM Draft
                  {outreach.template_used && (
                    <span className="ml-2 text-accent">Template {outreach.template_used}</span>
                  )}
                </p>
              </div>
              {editing ? (
                <div className="space-y-2">
                  <textarea
                    value={dmText}
                    onChange={e => setDmText(e.target.value)}
                    className="w-full bg-bg border border-accent/50 rounded-lg p-3 text-sm text-text leading-relaxed resize-none h-40 focus:outline-none focus:border-accent"
                  />
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-mono ${
                      (() => {
                        const wc = dmText.trim().split(/\s+/).filter(Boolean).length
                        if (wc > 150) return 'text-red-400'
                        if (wc > 130) return 'text-yellow-400'
                        return 'text-green-400'
                      })()
                    }`}>
                      {dmText.trim().split(/\s+/).filter(Boolean).length} / 150 words
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setEditing(false)
                          onAction('save_dm', { ...lead, outreach: { ...outreach, dm_draft: dmText } })
                        }}
                        className="px-4 py-2 rounded bg-accent text-black text-xs font-semibold hover:bg-green-400 transition-all"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditing(false)
                          setDmText(outreach.dm_draft || '')
                        }}
                        className="px-4 py-2 rounded border border-border text-muted hover:text-text text-xs transition-all"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-bg border border-border rounded p-3">
                  <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
                    {outreach.dm_draft || <span className="text-muted italic">No DM draft</span>}
                  </p>
                </div>
              )}
            </div>

            {/* Actions */}
            {!approved ? (
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleApprove}
                  className="flex items-center gap-1.5 px-4 py-2 rounded bg-accent text-black text-xs font-bold hover:bg-green-400 transition-all"
                >
                  <CheckCircle size={14} />
                  Approve -- Push to GHL
                </button>
                <button
                  onClick={() => {
                    setDmText(outreach.dm_draft || '')
                    setEditing(true)
                  }}
                  className="flex items-center gap-1.5 px-4 py-2 rounded border border-border text-muted hover:text-text text-xs transition-all"
                >
                  <Edit3 size={14} />
                  Edit DM
                </button>
                <button
                  onClick={() => onAction('reject', lead)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded border border-red-900 text-red-400 hover:bg-red-950 text-xs transition-all"
                >
                  <XCircle size={14} />
                  Reject
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 py-2">
                <CheckCircle size={16} className="text-accent" />
                <span className="text-accent text-sm font-semibold">Approved</span>
                <button
                  onClick={() => setShowGhlConfirm(true)}
                  className="px-3 py-1 rounded bg-blue-900 text-blue-300 text-xs hover:bg-blue-800 transition-all ml-2"
                >
                  Push to GHL
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}

export default function ApprovalQueue({ leads, loading, onAction }) {
  const pending = leads.filter(l => (l.outreach?.approval_status) === 'PENDING')

  if (loading) {
    return (
      <div className="p-4 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="border border-border rounded-lg bg-card p-4">
            <div className="skeleton w-48 h-4 mb-3 rounded" />
            <div className="skeleton w-full h-24 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (pending.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <CheckCircle size={40} className="text-accent mb-4" />
        <p className="text-text font-semibold">Approval queue is clear</p>
        <p className="text-muted text-xs mt-1">No DM drafts pending review.</p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <p className="text-muted text-xs font-mono">
        {pending.length} DM{pending.length !== 1 ? 's' : ''} pending approval
      </p>
      {pending.map(lead => (
        <ApprovalCard key={lead.id} lead={lead} onAction={onAction} />
      ))}
    </div>
  )
}
