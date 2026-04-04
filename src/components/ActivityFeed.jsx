import {
  Search, Database, Star, MessageSquare, Send,
  ArrowLeftRight, RefreshCw, CheckCircle, XCircle, Clock
} from 'lucide-react'
import { formatDateTime, formatRelative } from '../utils/formatters'
import { useState } from 'react'

const TYPE_CONFIG = {
  discovery: { icon: Search, color: 'text-blue-400', bg: 'bg-blue-950', label: 'Discovery' },
  enrichment: { icon: Database, color: 'text-purple-400', bg: 'bg-purple-950', label: 'Enrichment' },
  scoring: { icon: Star, color: 'text-yellow-400', bg: 'bg-yellow-950', label: 'Scoring' },
  dm_draft: { icon: MessageSquare, color: 'text-accent', bg: 'bg-emerald-950', label: 'DM Draft' },
  outreach: { icon: Send, color: 'text-pink-400', bg: 'bg-pink-950', label: 'Outreach' },
  status_change: { icon: RefreshCw, color: 'text-muted', bg: 'bg-gray-900', label: 'Status' },
  ghl_push: { icon: ArrowLeftRight, color: 'text-blue-400', bg: 'bg-blue-950', label: 'GHL Push' },
  ghl_sync: { icon: RefreshCw, color: 'text-sky-400', bg: 'bg-sky-950', label: 'GHL Sync' },
  approved: { icon: CheckCircle, color: 'text-accent', bg: 'bg-emerald-950', label: 'Approved' },
  rejected: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-950', label: 'Rejected' },
  dashboard_sync: { icon: RefreshCw, color: 'text-sky-400', bg: 'bg-sky-950', label: 'Sync' },
}

const TYPE_FILTERS = [
  'all',
  'discovery',
  'enrichment',
  'scoring',
  'dm_draft',
  'ghl_push',
  'ghl_sync',
  'approved',
  'rejected',
]

function TypeBadge({ type }) {
  const config = TYPE_CONFIG[type] || { icon: Clock, color: 'text-muted', bg: 'bg-gray-900', label: type }
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono ${config.color} ${config.bg}`}>
      <Icon size={10} />
      {config.label || type}
    </span>
  )
}

function ActivityItem({ item }) {
  return (
    <div className="flex gap-3 py-3 border-b border-border last:border-0">
      {/* Time */}
      <div className="flex-shrink-0 w-28 pt-0.5">
        <p className="text-muted text-xs font-mono leading-tight" title={formatDateTime(item.timestamp)}>
          {formatRelative(item.timestamp)}
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <TypeBadge type={item.type} />
          {item.lead_id && (
            <span className="text-muted text-xs font-mono">{item.lead_id}</span>
          )}
        </div>
        <p className="text-text text-xs leading-relaxed">{item.description}</p>
        {item.source && (
          <p className="text-muted text-[10px] font-mono mt-1">
            source: {item.source}
            {item.agent && ` -- agent: ${item.agent}`}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ActivityFeed({ activity, loading }) {
  const [typeFilter, setTypeFilter] = useState('all')

  const filtered = typeFilter === 'all'
    ? activity
    : activity.filter(a => a.type === typeFilter)

  if (loading) {
    return (
      <div className="p-4 space-y-3">
        {[1,2,3,4,5].map(i => (
          <div key={i} className="flex gap-3 py-3">
            <div className="skeleton w-24 h-4 rounded" />
            <div className="flex-1">
              <div className="skeleton w-20 h-4 rounded mb-2" />
              <div className="skeleton w-full h-3 rounded" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Type filter tabs */}
      <div className="flex gap-1 px-4 pt-3 pb-2 overflow-x-auto border-b border-border">
        {TYPE_FILTERS.map(type => (
          <button
            key={type}
            onClick={() => setTypeFilter(type)}
            className={`px-3 py-1 rounded text-xs font-mono flex-shrink-0 capitalize transition-all ${
              typeFilter === type
                ? 'bg-accent text-black font-semibold'
                : 'text-muted hover:text-text hover:bg-card'
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto px-4">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Clock size={40} className="text-muted mb-4" />
            <p className="text-text font-semibold">No activity yet</p>
            <p className="text-muted text-xs mt-1">Pipeline events will appear here as they happen.</p>
          </div>
        ) : (
          <div>
            <p className="text-muted text-xs font-mono py-2">{filtered.length} event{filtered.length !== 1 ? 's' : ''}</p>
            {filtered.map((item, i) => (
              <ActivityItem key={item.id || i} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
