export default function GhlBadge({ lead }) {
  if (!lead) return null

  const ghl = lead.ghl || {}
  const contactId = ghl.contact_id || lead.ghl_contact_id
  const stage = ghl.pipeline_stage || lead.ghl_pipeline_stage
  const score = lead.scoring?.score || lead.scoring_score

  if (!contactId) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-not-in">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-500 inline-block" />
        Not in GHL
      </span>
    )
  }

  if (score === 5) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-gregory">
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />
        Gregory Only
      </span>
    )
  }

  const warmStages = ['Responded', 'Demo Scheduled', 'Demo Complete', 'Pilot', 'Customer']
  if (warmStages.some(s => stage?.includes(s))) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-warm">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
        {stage}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-in">
      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />
      {stage || 'In GHL'}
    </span>
  )
}
