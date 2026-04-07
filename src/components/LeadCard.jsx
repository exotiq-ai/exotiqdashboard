import { useState } from 'react'
import {
  ChevronDown, ChevronRight, Copy, Phone, Mail, Globe,
  Instagram, Linkedin, CheckCircle, XCircle, Edit3, Flag,
  AlertTriangle, User, Car, MessageSquare, Clock, ArrowRight
} from 'lucide-react'
import ScoreBadge from './ScoreBadge'
import GhlBadge from './GhlBadge'
import ProvenanceTag from './ProvenanceTag'
import { formatRelative, formatPhone, contactName } from '../utils/formatters'

function CopyButton({ text, children }) {
  const [copied, setCopied] = useState(false)

  function handleCopy(e) {
    e.stopPropagation()
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-muted hover:text-accent transition-all group"
      title={`Copy: ${text}`}
    >
      {children}
      {copied
        ? <CheckCircle size={12} className="text-accent" />
        : <Copy size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
      }
    </button>
  )
}

function EmptyField({ label }) {
  return <span className="text-xs text-gray-600 italic">No {label}</span>
}

function IgLink({ handle, suffix }) {
  if (!handle) return null
  // Clean the handle: strip @, strip full URLs
  let clean = handle.trim()
  if (clean.startsWith('http')) {
    // Extract handle from URL
    clean = clean.replace(/https?:\/\/(www\.)?instagram\.com\//i, '').replace(/\/$/, '')
  }
  clean = clean.replace(/^@/, '')
  const display = `@${clean}`
  const url = `https://instagram.com/${clean}`

  return (
    <a href={url} target="_blank" rel="noopener noreferrer"
      className="flex items-center gap-1.5 text-muted hover:text-pink-400 transition-all group">
      <Instagram size={13} />
      <span className="text-sm font-mono text-text group-hover:text-pink-400">{display}</span>
      {suffix && <span className="text-xs text-muted">{suffix}</span>}
    </a>
  )
}

function SectionHeader({ icon: Icon, label, accent }) {
  return (
    <h4 className={`text-xs font-mono uppercase tracking-wider mb-2 flex items-center gap-1.5 ${accent || 'text-muted'}`}>
      {Icon && <Icon size={12} />}
      {label}
    </h4>
  )
}

function PricingBadge({ pricing }) {
  if (!pricing?.tier) return null
  const colorMap = {
    'Enterprise': 'bg-yellow-950 text-yellow-400 border-yellow-800',
    'Business': 'bg-purple-950 text-purple-400 border-purple-800',
    'Professional': 'bg-blue-950 text-blue-400 border-blue-800',
    'Starter': 'bg-gray-900 text-gray-400 border-gray-700',
  }
  const tier = pricing.tier.replace(' (est.)', '')
  const colors = colorMap[tier] || 'bg-gray-900 text-gray-400 border-gray-700'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-mono ${colors}`}>
      {tier}
    </span>
  )
}

function ExpandedDetail({ lead, onAction }) {
  const [editingDm, setEditingDm] = useState(false)
  const [dmText, setDmText] = useState((lead.outreach || {}).dm_draft || '')

  const contact = lead.contact || {}
  const company = lead.company_data || {}
  const fleet = lead.fleet || {}
  const scoring = lead.scoring || {}
  const outreach = lead.outreach || {}
  const ghl = lead.ghl || {}

  const vehicleTypes = (() => {
    if (Array.isArray(fleet.vehicle_types)) return fleet.vehicle_types
    try { return JSON.parse(fleet.vehicle_types || '[]') } catch { return [] }
  })()

  const doNotSay = (() => {
    if (Array.isArray(outreach.do_not_say)) return outreach.do_not_say
    try { return JSON.parse(outreach.do_not_say || '[]') } catch {
      return outreach.do_not_say ? [outreach.do_not_say] : []
    }
  })()

  const isPending = outreach.approval_status === 'PENDING'
  const isApproved = outreach.approval_status === 'APPROVED'
  const isRejected = outreach.approval_status === 'REJECTED'
  const name = contactName(lead)

  return (
    <div className="border-t border-border mt-2 pt-4 grid grid-cols-1 lg:grid-cols-3 gap-6">

      {/* Column 1: Contact + Company */}
      <div className="space-y-4">
        <section>
          <SectionHeader icon={User} label="Contact" />
          <div className="space-y-1.5 bg-bg/50 rounded-lg p-3 border border-border/50">
            {name && name !== '--' ? (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-semibold text-text">{name}</span>
                {contact.title && <span className="text-xs text-muted">-- {contact.title}</span>}
              </div>
            ) : <EmptyField label="contact name" />}

            {contact.phone ? (
              <CopyButton text={contact.phone}>
                <Phone size={13} />
                <span className="text-sm font-mono text-text">{formatPhone(contact.phone)}</span>
              </CopyButton>
            ) : <div className="flex items-center gap-1.5"><Phone size={13} className="text-gray-700" /><EmptyField label="phone" /></div>}

            {contact.email ? (
              <CopyButton text={contact.email}>
                <Mail size={13} />
                <span className="text-sm font-mono text-text">{contact.email}</span>
              </CopyButton>
            ) : <div className="flex items-center gap-1.5"><Mail size={13} className="text-gray-700" /><EmptyField label="email" /></div>}

            {contact.ig_personal && (
              <IgLink handle={contact.ig_personal} suffix="(personal)" />
            )}

            {contact.linkedin && (
              <a href={contact.linkedin} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-muted hover:text-blue-400 transition-all">
                <Linkedin size={13} />
                <span className="text-sm text-blue-400 hover:text-blue-300">LinkedIn</span>
              </a>
            )}
          </div>
        </section>

        <section>
          <SectionHeader icon={Globe} label="Company" />
          <div className="space-y-1.5 bg-bg/50 rounded-lg p-3 border border-border/50">
            {company.ig_handle && (
              <div className="flex items-center gap-1.5">
                <IgLink handle={company.ig_handle} 
                  suffix={company.ig_followers ? `(${Number(company.ig_followers).toLocaleString()})` : null} />
              </div>
            )}

            {company.website ? (
              <a href={company.website.startsWith('http') ? company.website : `https://${company.website}`}
                target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-all">
                <Globe size={13} />
                <span className="text-sm font-mono truncate">{company.website}</span>
              </a>
            ) : <div className="flex items-center gap-1.5"><Globe size={13} className="text-gray-700" /><EmptyField label="website" /></div>}

            {company.google_rating && (
              <div className="flex items-center gap-1.5 text-muted">
                <span className="text-yellow-400 text-sm">★ {company.google_rating}</span>
                {company.google_reviews && (
                  <span className="text-xs">({company.google_reviews} reviews)</span>
                )}
              </div>
            )}

            {company.address && (
              <p className="text-xs text-muted">{company.address}</p>
            )}
          </div>
        </section>

        <section>
          <SectionHeader icon={Car} label="Fleet" />
          <div className="bg-bg/50 rounded-lg p-3 border border-border/50">
            {fleet.size ? (
              <div className="flex items-center gap-2">
                <span className="font-mono text-text text-sm font-semibold">{fleet.size} vehicles</span>
                <ProvenanceTag source={fleet.size_source} confidence={fleet.size_confidence} />
              </div>
            ) : <EmptyField label="fleet size" />}

            {vehicleTypes.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {vehicleTypes.map((v, i) => (
                  <span key={i} className="px-2 py-0.5 rounded bg-border text-xs text-muted font-mono">{v}</span>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Column 2: Outreach Timeline + DM */}
      <div className="space-y-4">
        <section>
          <SectionHeader icon={MessageSquare} label="Outreach Timeline" />
          <div className="bg-bg/50 rounded-lg p-3 border border-border/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted">Status</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                outreach.status === 'Responded' ? 'bg-green-900/50 text-green-400' :
                outreach.status === 'Contacted' ? 'bg-blue-900/50 text-blue-400' :
                outreach.status === 'Demo Scheduled' ? 'bg-accent/20 text-accent' :
                outreach.status === 'Error Flagged' ? 'bg-red-900/50 text-red-400' :
                outreach.status === 'Not a Fit' ? 'bg-red-900/50 text-red-400 line-through' :
                outreach.status === 'On Hold' ? 'bg-yellow-900/50 text-yellow-400' :
                outreach.status === 'Pending Approval' ? 'bg-yellow-900/50 text-yellow-400' :
                'bg-border text-muted'
              }`}>{outreach.status || 'New'}</span>
            </div>

            {outreach.dm1_sent && (
              <div className="flex items-center gap-2 text-xs">
                <ArrowRight size={10} className="text-accent" />
                <span className="text-muted">DM1 sent:</span>
                <span className="text-text font-mono">{outreach.dm1_sent}</span>
              </div>
            )}

            {outreach.dm2_sent && (
              <div className="flex items-center gap-2 text-xs">
                <ArrowRight size={10} className="text-blue-400" />
                <span className="text-muted">DM2 sent:</span>
                <span className="text-text font-mono">{outreach.dm2_sent}</span>
              </div>
            )}

            {outreach.dm3_sent && (
              <div className="flex items-center gap-2 text-xs">
                <ArrowRight size={10} className="text-purple-400" />
                <span className="text-muted">DM3 sent:</span>
                <span className="text-text font-mono">{outreach.dm3_sent}</span>
              </div>
            )}

            {(outreach.response_received === true || outreach.response_received === 'Y' || outreach.response_received === 1) && (
              <div className="mt-1 p-2 rounded bg-green-900/20 border border-green-900/50">
                <div className="flex items-center gap-2 text-xs">
                  <CheckCircle size={12} className="text-green-400" />
                  <span className="text-green-400 font-semibold">Response received</span>
                </div>
                {outreach.response_category && (
                  <span className="text-xs text-muted ml-5">Category: {outreach.response_category}</span>
                )}
                {outreach.response_date && (
                  <span className="text-xs text-muted ml-5 block">Date: {outreach.response_date}</span>
                )}
              </div>
            )}

            {!!outreach.demo_scheduled && (
              <div className="mt-1 p-2 rounded bg-accent/10 border border-accent/30">
                <div className="flex items-center gap-2 text-xs">
                  <CheckCircle size={12} className="text-accent" />
                  <span className="text-accent font-semibold">Demo scheduled</span>
                </div>
              </div>
            )}

            {!outreach.dm1_sent && !outreach.response_received && !outreach.demo_scheduled && outreach.status === 'New' && (
              <p className="text-xs text-gray-600 italic">No outreach activity yet</p>
            )}
          </div>
        </section>

        {/* DM Draft */}
        <section>
          <SectionHeader icon={Edit3} label={`DM Draft${outreach.template_used ? ` -- Template ${outreach.template_used}` : ''}`} />
          {outreach.dm_draft ? (
            <>
              {editingDm ? (
                <div className="space-y-2">
                  <textarea
                    value={dmText}
                    onChange={e => setDmText(e.target.value)}
                    className="w-full bg-bg border border-accent/50 rounded-lg p-3 text-xs text-text leading-relaxed resize-none h-32 focus:outline-none focus:border-accent"
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
                          setEditingDm(false)
                          onAction('save_dm', { ...lead, outreach: { ...lead.outreach, dm_draft: dmText } })
                        }}
                        className="px-3 py-1.5 rounded bg-accent text-black text-xs font-semibold hover:bg-green-400 transition-all"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditingDm(false)
                          setDmText(outreach.dm_draft || '')
                        }}
                        className="px-3 py-1.5 rounded border border-border text-muted hover:text-text text-xs transition-all"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-bg/50 rounded-lg p-3 border border-border/50">
                  <p className="text-xs text-text leading-relaxed whitespace-pre-wrap">{outreach.dm_draft}</p>
                </div>
              )}

              {!editingDm && isPending && (
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => onAction('approve', lead)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent text-black text-xs font-semibold hover:bg-green-400 transition-all"
                  >
                    <CheckCircle size={13} />
                    Approve
                  </button>
                  <button
                    onClick={() => {
                      setDmText(outreach.dm_draft || '')
                      setEditingDm(true)
                    }}
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

              {!editingDm && isApproved && (
                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-accent flex items-center gap-1">
                    <CheckCircle size={12} />
                    Approved
                  </span>
                  <button
                    onClick={() => {
                      setDmText(outreach.dm_draft || '')
                      setEditingDm(true)
                    }}
                    className="flex items-center gap-1.5 px-3 py-1 rounded border border-border text-muted hover:text-text text-xs transition-all"
                  >
                    <Edit3 size={12} />
                    Edit
                  </button>
                  {!ghl.contact_id && (contact.email || contact.phone) && (
                    <button
                      onClick={() => onAction('push_to_ghl', lead)}
                      className="px-3 py-1 rounded bg-blue-900 text-blue-300 text-xs hover:bg-blue-800 transition-all"
                    >
                      Push to GHL
                    </button>
                  )}
                  {!ghl.contact_id && !contact.email && !contact.phone && (
                    <span className="text-xs text-yellow-400 italic">Needs email or phone to push</span>
                  )}
                </div>
              )}

              {!editingDm && isRejected && (
                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-red-400 flex items-center gap-1">
                    <XCircle size={12} />
                    Rejected
                  </span>
                  <button
                    onClick={() => {
                      setDmText(outreach.dm_draft || '')
                      setEditingDm(true)
                    }}
                    className="flex items-center gap-1.5 px-3 py-1 rounded border border-border text-muted hover:text-text text-xs transition-all"
                  >
                    <Edit3 size={12} />
                    Redraft
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="bg-bg/50 rounded-lg p-3 border border-border/50">
              <EmptyField label="DM draft" />
            </div>
          )}
        </section>
      </div>

      {/* Column 3: GHL + Score + Notes + Actions */}
      <div className="space-y-4">
        {/* DO NOT SAY -- top of column, impossible to miss */}
        {doNotSay.length > 0 && doNotSay.some(s => s && s.trim()) && (
          <section>
            <SectionHeader icon={AlertTriangle} label="Do Not Say" accent="text-red-400" />
            <div className="bg-red-950/30 border border-red-900/50 rounded-lg p-3 space-y-1">
              {doNotSay.filter(s => s && s.trim()).map((item, i) => (
                <p key={i} className="text-xs text-red-300">{item}</p>
              ))}
            </div>
          </section>
        )}

        {/* Pricing Badge */}
        {lead.pricing && (
          <section>
            <SectionHeader label="Pricing Tier" />
            <div className="bg-bg/50 rounded-lg p-3 border border-border/50 flex items-center gap-2">
              <PricingBadge pricing={lead.pricing} />
              {lead.pricing?.annual_value > 0 && (
                <span className="text-xs text-accent font-mono font-semibold">
                  ${lead.pricing.annual_value.toLocaleString()}/yr
                </span>
              )}
            </div>
          </section>
        )}

        {/* GHL Status */}
        <section>
          <SectionHeader label="GHL Status" />
          <div className="bg-bg/50 rounded-lg p-3 border border-border/50">
            <div className="flex items-center gap-2">
              <GhlBadge lead={lead} />
              {ghl.pipeline_stage && (
                <span className="text-xs text-muted font-mono">{ghl.pipeline_stage}</span>
              )}
            </div>
            {ghl.contact_id && (
              <a
                href={`https://app.gohighlevel.com/v2/location/hTOVcYDLS1UfuiNzuzpT/contacts/detail/${ghl.contact_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block"
              >
                Open in GHL →
              </a>
            )}
          </div>
        </section>

        {/* Score Rationale */}
        {scoring.rationale && (
          <section>
            <SectionHeader label="Enrichment Intel" />
            <div className="bg-bg/50 rounded-lg p-3 border border-border/50 max-h-32 overflow-y-auto">
              <p className="text-xs text-text leading-relaxed whitespace-pre-wrap">{scoring.rationale}</p>
            </div>
          </section>
        )}

        {/* Notes */}
        <section>
          <SectionHeader label="Notes" />
          <div className="bg-bg/50 rounded-lg p-3 border border-border/50">
            {lead.notes ? (
              <p className="text-xs text-text leading-relaxed whitespace-pre-wrap">{lead.notes}</p>
            ) : <EmptyField label="notes" />}
          </div>
        </section>

        {/* Quick Actions */}
        <section>
          <SectionHeader label="Quick Actions" />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                if (!contact.email && !contact.phone) {
                  alert(`Cannot push ${lead.company} to GHL: no email or phone on file.`)
                  return
                }
                onAction('push_to_ghl', lead)
              }}
              className={`px-3 py-1.5 rounded border text-xs transition-all ${
                !contact.email && !contact.phone
                  ? 'border-gray-800 text-gray-600 cursor-not-allowed'
                  : 'border-border text-muted hover:text-accent hover:border-accent'
              }`}
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
              className="px-3 py-1.5 rounded border border-border text-muted hover:text-accent hover:border-accent text-xs transition-all"
            >
              Send to Gregory
            </button>
            {outreach.status !== 'Not a Fit' ? (
              <button
                onClick={() => {
                  if (window.confirm(`Mark ${lead.company} as Not a Fit? This will remove them from active pipeline.`)) {
                    onAction('not_a_fit', lead)
                  }
                }}
                className="px-3 py-1.5 rounded border border-red-900 text-red-400 hover:bg-red-950 text-xs transition-all"
              >
                Not a Fit
              </button>
            ) : (
              <span className="px-3 py-1.5 rounded bg-red-950/50 text-red-400 text-xs flex items-center gap-1">
                <XCircle size={12} />
                Marked Not a Fit
              </span>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

export default function LeadCard({ lead, onAction }) {
  const [expanded, setExpanded] = useState(false)

  const name = contactName(lead)
  const outreach = lead.outreach || {}
  const updatedAgo = formatRelative(lead.updated_at)
  const isStale = lead.stale === true

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
          <span className="text-muted flex-shrink-0">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>

          <span className="font-semibold text-text text-sm truncate min-w-0 max-w-48 flex items-center gap-1.5">
            {lead.company}
            {isStale && (
              <span className="inline-block w-2 h-2 rounded-full bg-orange-500 flex-shrink-0" title={`Stale: ${lead.days_since_activity} days since activity`} />
            )}
          </span>

          <span className="text-muted text-xs truncate hidden sm:block min-w-0 max-w-32">
            {name}
          </span>

          <ScoreBadge score={lead.scoring?.score} />

          <span className="text-muted text-xs font-mono hidden md:block flex-shrink-0">
            {lead.market || '--'}
          </span>

          <span className={`text-xs hidden lg:block flex-shrink-0 px-2 py-0.5 rounded ${
            outreach.status === 'Responded' ? 'bg-green-900/50 text-green-400' :
            outreach.status === 'Contacted' ? 'bg-blue-900/50 text-blue-400' :
            outreach.status === 'Demo Scheduled' ? 'bg-accent/20 text-accent' :
            outreach.status === 'Error Flagged' ? 'bg-red-900/50 text-red-400' :
            'text-muted'
          }`}>
            {outreach.status || 'New'}
          </span>

          <div className="hidden xl:block flex-shrink-0">
            <GhlBadge lead={lead} />
          </div>

          <span className="text-muted text-xs font-mono ml-auto flex-shrink-0">
            {updatedAgo}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4">
          <ExpandedDetail lead={lead} onAction={onAction} />
        </div>
      )}
    </div>
  )
}
