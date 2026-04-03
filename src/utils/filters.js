export function applyFilters(leads, filters) {
  let result = [...leads]

  // Market filter
  if (filters.markets && filters.markets.length > 0) {
    result = result.filter(l => filters.markets.includes(l.market))
  }

  // Score filter
  if (filters.scores && filters.scores.length > 0) {
    result = result.filter(l => filters.scores.includes(String(l.scoring_score)))
  }

  // Status filter
  if (filters.statuses && filters.statuses.length > 0) {
    result = result.filter(l => filters.statuses.includes(l.status))
  }

  // Search
  if (filters.search) {
    const q = filters.search.toLowerCase()
    result = result.filter(l => {
      return (
        (l.company || '').toLowerCase().includes(q) ||
        (l.contact_first_name || '').toLowerCase().includes(q) ||
        (l.contact_last_name || '').toLowerCase().includes(q) ||
        (l.company_ig_handle || '').toLowerCase().includes(q) ||
        (l.notes || '').toLowerCase().includes(q) ||
        (l.market || '').toLowerCase().includes(q)
      )
    })
  }

  // Sort
  if (filters.sortBy === 'score_desc') {
    result.sort((a, b) => (b.scoring_score || 0) - (a.scoring_score || 0))
  } else if (filters.sortBy === 'score_asc') {
    result.sort((a, b) => (a.scoring_score || 0) - (b.scoring_score || 0))
  } else if (filters.sortBy === 'updated') {
    result.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
  } else if (filters.sortBy === 'market') {
    result.sort((a, b) => (a.market || '').localeCompare(b.market || ''))
  } else if (filters.sortBy === 'company') {
    result.sort((a, b) => (a.company || '').localeCompare(b.company || ''))
  } else {
    // Default: score desc, then updated
    result.sort((a, b) => {
      const scoreDiff = (b.scoring_score || 0) - (a.scoring_score || 0)
      if (scoreDiff !== 0) return scoreDiff
      return new Date(b.updated_at || 0) - new Date(a.updated_at || 0)
    })
  }

  return result
}

export function getUniqueMarkets(leads) {
  const markets = leads.map(l => l.market).filter(Boolean)
  return [...new Set(markets)].sort()
}

export function getUniqueStatuses(leads) {
  const statuses = leads.map(l => l.status).filter(Boolean)
  return [...new Set(statuses)].sort()
}

export function getPendingApprovals(leads) {
  return leads.filter(l => l.dm_approval_status === 'PENDING')
}

export function getCallSheetLeads(leads) {
  return leads.filter(l =>
    l.scoring_score === 5 ||
    l.status === 'warm' ||
    l.ghl_pipeline_stage === 'Responded' ||
    l.ghl_pipeline_stage === 'Demo Scheduled'
  )
}

export function exportToCsv(leads, filename) {
  if (!leads || leads.length === 0) return

  const cols = [
    'id', 'company', 'market', 'scoring_score', 'status',
    'contact_first_name', 'contact_last_name', 'contact_email', 'contact_phone',
    'company_ig_handle', 'company_ig_followers', 'fleet_size',
    'ghl_pipeline_stage', 'dm_approval_status', 'updated_at',
  ]

  const header = cols.join(',')
  const rows = leads.map(l =>
    cols.map(c => {
      const val = l[c] ?? ''
      const str = String(val).replace(/"/g, '""')
      return `"${str}"`
    }).join(',')
  )

  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
