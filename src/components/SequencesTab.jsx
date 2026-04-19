import { useState } from 'react'
import {
  Play, Pause, MessageSquare, Mail, Phone, Send,
  ChevronRight, ChevronDown, Users, Clock, Zap, Facebook
} from 'lucide-react'

const CHANNEL_ICONS = {
  ig_dm: { icon: MessageSquare, color: 'text-pink-400', label: 'IG DM' },
  fb_dm: { icon: Facebook, color: 'text-blue-400', label: 'FB Messenger' },
  email: { icon: Mail, color: 'text-yellow-400', label: 'Email' },
  sms: { icon: Send, color: 'text-green-400', label: 'SMS' },
  phone: { icon: Phone, color: 'text-accent', label: 'Phone' },
}

function ChannelBadge({ channel }) {
  const cfg = CHANNEL_ICONS[channel] || { icon: Zap, color: 'text-muted', label: channel }
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded bg-card border border-border text-[10px] font-mono ${cfg.color}`}>
      <Icon size={10} />
      {cfg.label}
    </span>
  )
}

function SequenceCard({ sequence }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <button
        className="w-full text-left px-4 py-3 flex items-center gap-3"
        onClick={() => setExpanded(e => !e)}
      >
        <span className="text-muted flex-shrink-0">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-text font-semibold text-sm">{sequence.name}</p>
          <p className="text-muted text-xs">{sequence.description}</p>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <span className="text-muted text-xs font-mono flex items-center gap-1">
            <Users size={12} />
            {sequence.active_enrollments || 0} active
          </span>

          <span className="text-muted text-xs font-mono flex items-center gap-1">
            <Clock size={12} />
            {sequence.steps?.length || 0} steps
          </span>

          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono ${
            sequence.active ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
          }`}>
            {sequence.active ? <><Play size={10} /> Active</> : <><Pause size={10} /> Paused</>}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-border pt-3">
          <div className="space-y-2">
            {(sequence.steps || []).map((step, i) => (
              <div key={step.id || i} className="flex items-center gap-3 text-xs">
                <span className="text-muted font-mono w-16 flex-shrink-0">
                  Day {step.delay_days}
                </span>
                <ChannelBadge channel={step.channel} />
                <span className="text-muted truncate flex-1">
                  {step.template_id || step.template_override?.substring(0, 80) + '...' || 'No content'}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-border flex items-center gap-2">
            <span className="text-muted text-xs font-mono">Trigger: {sequence.trigger_type} / {sequence.trigger_value}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function QueuePreview({ queue }) {
  if (!queue || queue.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Clock size={32} className="text-muted mb-3" />
        <p className="text-text font-semibold text-sm">No touches queued</p>
        <p className="text-muted text-xs mt-1">Enroll leads into sequences to start generating outreach drafts.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {queue.map(item => (
        <div key={item.id} className="flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-lg">
          <ChannelBadge channel={item.channel} />
          <span className="text-text text-sm font-semibold flex-shrink-0">{item.company || item.lead_id}</span>
          <span className="text-muted text-xs truncate flex-1">{item.content?.substring(0, 100)}...</span>
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${
            item.status === 'pending' ? 'bg-yellow-900/50 text-yellow-400' :
            item.status === 'approved' ? 'bg-green-900/50 text-green-400' :
            item.status === 'sent' ? 'bg-blue-900/50 text-blue-400' :
            'bg-border text-muted'
          }`}>{item.status}</span>
        </div>
      ))}
    </div>
  )
}

function EnrollmentList({ enrollments }) {
  if (!enrollments || enrollments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Users size={32} className="text-muted mb-3" />
        <p className="text-text font-semibold text-sm">No active enrollments</p>
        <p className="text-muted text-xs mt-1">Enroll leads from the All Leads tab.</p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-2 text-muted text-xs font-mono">Lead</th>
            <th className="text-left px-4 py-2 text-muted text-xs font-mono">Sequence</th>
            <th className="text-left px-4 py-2 text-muted text-xs font-mono">Step</th>
            <th className="text-left px-4 py-2 text-muted text-xs font-mono">Next Touch</th>
            <th className="text-left px-4 py-2 text-muted text-xs font-mono">Status</th>
          </tr>
        </thead>
        <tbody>
          {enrollments.map(e => (
            <tr key={e.id} className="border-b border-border/50">
              <td className="px-4 py-2 text-text font-medium">{e.company || e.lead_id}</td>
              <td className="px-4 py-2 text-muted">{e.sequence_name || e.sequence_id}</td>
              <td className="px-4 py-2 text-muted font-mono">{e.current_step || 0}</td>
              <td className="px-4 py-2 text-muted font-mono text-xs">{e.next_touch_due || '--'}</td>
              <td className="px-4 py-2">
                <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                  e.status === 'active' ? 'bg-green-900/50 text-green-400' :
                  e.status === 'paused' ? 'bg-yellow-900/50 text-yellow-400' :
                  e.status === 'completed' ? 'bg-blue-900/50 text-blue-400' :
                  e.status === 'stopped_responded' ? 'bg-accent/20 text-accent' :
                  'bg-border text-muted'
                }`}>{e.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function SequencesTab({ sequences, queue, enrollments, loading }) {
  const [subTab, setSubTab] = useState('campaigns')

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton h-20 rounded-lg" />
        ))}
      </div>
    )
  }

  const SUB_TABS = [
    { id: 'campaigns', label: 'Campaigns', count: sequences?.length },
    { id: 'enrollments', label: 'Active Enrollments', count: enrollments?.filter(e => e.status === 'active').length },
    { id: 'queue', label: 'Queue Preview', count: queue?.filter(q => q.status === 'pending').length },
  ]

  return (
    <div className="p-4">
      {/* Sub-tab nav */}
      <div className="flex gap-1 mb-4 border-b border-border">
        {SUB_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`px-3 py-2 text-xs font-mono transition-all border-b-2 ${
              subTab === tab.id
                ? 'text-accent border-accent'
                : 'text-muted border-transparent hover:text-text'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-1.5 bg-card border border-border rounded-full px-1.5 py-0.5 text-[10px]">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {subTab === 'campaigns' && (
        <div className="space-y-3">
          {(sequences || []).map(seq => (
            <SequenceCard key={seq.id} sequence={seq} />
          ))}
          {(!sequences || sequences.length === 0) && (
            <p className="text-muted text-xs text-center py-12">No sequences defined yet.</p>
          )}
        </div>
      )}

      {subTab === 'enrollments' && (
        <EnrollmentList enrollments={enrollments} />
      )}

      {subTab === 'queue' && (
        <QueuePreview queue={queue} />
      )}
    </div>
  )
}
