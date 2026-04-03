const CONFIDENCE_COLORS = {
  HIGH: 'text-green-400 border-green-800',
  MEDIUM: 'text-yellow-400 border-yellow-800',
  LOW: 'text-orange-400 border-orange-800',
  ESTIMATED: 'text-orange-400 border-orange-800',
  VERIFIED: 'text-green-400 border-green-800',
}

export default function ProvenanceTag({ source, confidence }) {
  if (!source && !confidence) return null

  const parts = [source, confidence].filter(Boolean)
  const colorClass = CONFIDENCE_COLORS[confidence] || 'text-gray-500 border-gray-700'

  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-mono border rounded px-1 py-0.5 ${colorClass} opacity-80`}>
      {parts.join(', ')}
    </span>
  )
}
