export default function GhlBadge({ lead }) {
  if (!lead) return null

  const { ghl_contact_id, ghl_pipeline_stage, scoring_score } = lead

  if (!ghl_contact_id) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-not-in">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-500 inline-block" />
        Not in GHL
      </span>
    )
  }

  if (scoring_score === 5) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-gregory">
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />
        Gregory Only
      </span>
    )
  }

  const warmStages = ['Responded', 'Demo Scheduled', 'Demo Complete', 'Pilot', 'Customer']
  if (warmStages.includes(ghl_pipeline_stage)) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-warm">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
        {ghl_pipeline_stage}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ghl-in">
      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />
      {ghl_pipeline_stage || 'In GHL'}
    </span>
  )
}
