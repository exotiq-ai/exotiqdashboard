export function formatDate(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (isNaN(d)) return '--'
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateTime(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (isNaN(d)) return '--'
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    hour12: true,
  })
}

export function formatRelative(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (isNaN(d)) return '--'
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(iso)
}

export function formatNumber(n) {
  if (n == null) return '--'
  return Number(n).toLocaleString()
}

export function formatPhone(phone) {
  if (!phone) return '--'
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 10) {
    return `(${digits.slice(0,3)}) ${digits.slice(3,6)}-${digits.slice(6)}`
  }
  if (digits.length === 11 && digits[0] === '1') {
    return `+1 (${digits.slice(1,4)}) ${digits.slice(4,7)}-${digits.slice(7)}`
  }
  return phone
}

export function formatPct(n) {
  if (n == null) return '--'
  return `${Math.round(n * 100)}%`
}

export function contactName(lead) {
  // Handle both flat and nested structures
  const contact = lead.contact || {}
  const f = contact.first_name || lead.contact_first_name || ''
  const l = contact.last_name || lead.contact_last_name || ''
  const full = [f, l].filter(Boolean).join(' ')
  return full || '--'
}

export function ghlStageLabel(lead) {
  const ghl = lead.ghl || {}
  if (!ghl.contact_id && !lead.ghl_contact_id) return null
  return ghl.pipeline_stage || lead.ghl_pipeline_stage || 'In GHL'
}
