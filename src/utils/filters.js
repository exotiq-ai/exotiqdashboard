// Helper to safely access nested fields
function get(lead, path) {
  return path.split('.').reduce((obj, key) => obj?.[key], lead)
}

export function applyFilters(leads, filters) {
  let result = [...leads]

  // Market filter
  if (filters.markets && filters.markets.length > 0) {
    result = result.filter(l => filters.markets.includes(l.market))
  }

  // Score filter
  if (filters.scores && filters.scores.length > 0) {
    result = result.filter(l => filters.scores.includes(String(get(l, 'scoring.score'))))
  }

  // Status filter
  if (filters.statuses && filters.statuses.length > 0) {
    result = result.filter(l => {
      const status = get(l, 'outreach.status') || 'New'
      return filters.statuses.includes(status)
    })
  }

  // Search
  if (filters.search) {
    const q = filters.search.toLowerCase()
    result = result.filter(l => {
      return (
        (l.company || '').toLowerCase().includes(q) ||
        (get(l, 'contact.first_name') || '').toLowerCase().includes(q) ||
        (get(l, 'contact.last_name') || '').toLowerCase().includes(q) ||
        (get(l, 'company_data.ig_handle') || '').toLowerCase().includes(q) ||
        (get(l, 'contact.ig_personal') || '').toLowerCase().includes(q) ||
        (l.notes || '').toLowerCase().includes(q) ||
        (l.market || '').toLowerCase().includes(q) ||
        (get(l, 'scoring.rationale') || '').toLowerCase().includes(q)
      )
    })
  }

  // Sort
  const getScore = l => get(l, 'scoring.score') || 0
  if (filters.sortBy === 'score_desc') {
    result.sort((a, b) => getScore(b) - getScore(a))
  } else if (filters.sortBy === 'score_asc') {
    result.sort((a, b) => getScore(a) - getScore(b))
  } else if (filters.sortBy === 'updated') {
    result.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
  } else if (filters.sortBy === 'market') {
    result.sort((a, b) => (a.market || '').localeCompare(b.market || ''))
  } else if (filters.sortBy === 'company') {
    result.sort((a, b) => (a.company || '').localeCompare(b.company || ''))
  } else {
    // Default: score desc, then updated
    result.sort((a, b) => {
      const scoreDiff = getScore(b) - getScore(a)
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
  const statuses = leads.map(l => get(l, 'outreach.status')).filter(Boolean)
  return [...new Set(statuses)].sort()
}

export function getPendingApprovals(leads) {
  return leads.filter(l => get(l, 'outreach.approval_status') === 'PENDING')
}

export function getCallSheetLeads(leads) {
  return leads.filter(l =>
    get(l, 'scoring.score') === 5 ||
    get(l, 'outreach.response_category') === 'Interested - Gave Phone' ||
    get(l, 'outreach.response_category') === 'Interested - Won\'t Confirm Call' ||
    get(l, 'outreach.status') === 'Responded' ||
    get(l, 'outreach.status') === 'Demo Scheduled' ||
    get(l, 'ghl.pipeline_stage') === 'Responded -- Warm' ||
    get(l, 'ghl.pipeline_stage') === 'Demo Scheduled'
  )
}

export function exportToCsv(leads, filename) {
  if (!leads || leads.length === 0) return

  // Flatten nested lead data for CSV export
  const flatRows = leads.map(l => ({
    id: l.id,
    company: l.company,
    market: l.market,
    score: get(l, 'scoring.score'),
    score_confidence: get(l, 'scoring.confidence'),
    status: get(l, 'outreach.status'),
    first_name: get(l, 'contact.first_name'),
    last_name: get(l, 'contact.last_name'),
    title: get(l, 'contact.title') || '',
    email: get(l, 'contact.email'),
    phone: get(l, 'contact.phone'),
    ig_personal: get(l, 'contact.ig_personal'),
    linkedin: get(l, 'contact.linkedin'),
    company_ig: get(l, 'company_data.ig_handle'),
    ig_followers: get(l, 'company_data.ig_followers'),
    website: get(l, 'company_data.website'),
    address: get(l, 'company_data.address'),
    google_rating: get(l, 'company_data.google_rating'),
    google_reviews: get(l, 'company_data.google_reviews'),
    fleet_size: get(l, 'fleet.size'),
    fleet_confidence: get(l, 'fleet.size_confidence'),
    vehicle_types: Array.isArray(get(l, 'fleet.vehicle_types'))
      ? get(l, 'fleet.vehicle_types').join(', ')
      : get(l, 'fleet.vehicle_types') || '',
    dm_draft: get(l, 'outreach.dm_draft'),
    dm_template: get(l, 'outreach.template_used'),
    approval_status: get(l, 'outreach.approval_status'),
    dm1_sent: get(l, 'outreach.dm1_sent'),
    dm2_sent: get(l, 'outreach.dm2_sent'),
    dm3_sent: get(l, 'outreach.dm3_sent'),
    response_received: get(l, 'outreach.response_received') ? 'Y' : '',
    response_category: get(l, 'outreach.response_category'),
    response_date: get(l, 'outreach.response_date'),
    demo_scheduled: get(l, 'outreach.demo_scheduled') ? 'Y' : '',
    ghl_stage: get(l, 'ghl.pipeline_stage'),
    ghl_in_ghl: get(l, 'ghl.in_ghl') ? 'Y' : '',
    pricing_tier: get(l, 'pricing.tier') || '',
    pricing_annual_value: get(l, 'pricing.annual_value') || '',
    lead_source: l.lead_source,
    enrichment_notes: get(l, 'scoring.rationale') || '',
    notes: l.notes || '',
    updated_at: l.updated_at,
  }))

  if (flatRows.length === 0) return

  const cols = Object.keys(flatRows[0])
  const header = cols.join(',')
  const rows = flatRows.map(row =>
    cols.map(c => {
      const val = row[c] ?? ''
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
