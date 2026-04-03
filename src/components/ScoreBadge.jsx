export default function ScoreBadge({ score }) {
  if (score == null) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold bg-gray-800 text-gray-500">
        --
      </span>
    )
  }

  const classMap = {
    5: 'score-5',
    4: 'score-4',
    3: 'score-3',
    2: 'score-2',
    1: 'score-1',
  }

  const labelMap = {
    5: 'S5',
    4: 'S4',
    3: 'S3',
    2: 'S2',
    1: 'S1',
  }

  const cls = classMap[score] || 'score-1'

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold ${cls}`}>
      {labelMap[score] || score}
    </span>
  )
}
