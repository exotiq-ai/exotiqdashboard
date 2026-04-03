import LeadCard from './LeadCard'

function SkeletonCard() {
  return (
    <div className="border border-border rounded-lg bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="skeleton w-4 h-4 rounded" />
        <div className="skeleton w-40 h-4 rounded" />
        <div className="skeleton w-24 h-4 rounded" />
        <div className="skeleton w-8 h-5 rounded" />
        <div className="skeleton w-16 h-4 rounded ml-auto" />
      </div>
    </div>
  )
}

export default function LeadList({ leads, loading, onAction }) {
  if (loading) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (!leads || leads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-muted text-4xl mb-4">--</div>
        <p className="text-muted text-sm">No leads match your filters.</p>
        <p className="text-muted text-xs mt-1">Try clearing filters or check the data pipeline.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2 p-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-muted text-xs font-mono">{leads.length} lead{leads.length !== 1 ? 's' : ''}</span>
      </div>
      {leads.map(lead => (
        <LeadCard key={lead.id} lead={lead} onAction={onAction} />
      ))}
    </div>
  )
}
