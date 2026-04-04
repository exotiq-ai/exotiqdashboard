import { useState, useEffect, useCallback } from 'react'

const POLL_INTERVAL = 30000

async function fetchJson(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`)
  return res.json()
}

export function useLeadData() {
  const [leads, setLeads] = useState([])
  const [activity, setActivity] = useState([])
  const [stats, setStats] = useState(null)
  const [ghlStatus, setGhlStatus] = useState(null)
  const [pipelineMetrics, setPipelineMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastSynced, setLastSynced] = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [leadsData, activityData, statsData, ghlData, metricsData] = await Promise.all([
        fetchJson('/data/leads.json'),
        fetchJson('/data/activity.json'),
        fetchJson('/data/stats.json'),
        fetchJson('/data/ghl_sync_status.json'),
        fetchJson('/data/pipeline_metrics.json'),
      ])
      setLeads(Array.isArray(leadsData) ? leadsData : [])
      setActivity(Array.isArray(activityData) ? activityData : [])
      setStats(statsData)
      setGhlStatus(ghlData)
      setPipelineMetrics(metricsData)
      setError(null)
      setLastSynced(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchAll])

  // Track local edits so poll doesn't overwrite them
  const [localEdits, setLocalEdits] = useState({})

  const updateLeadDm = useCallback(async (leadId, newDraft, action = 'save') => {
    // Update local state immediately
    setLeads(prev => prev.map(l =>
      l.id === leadId
        ? { ...l, outreach: { ...l.outreach, dm_draft: newDraft } }
        : l
    ))

    // Track this edit so poll doesn't overwrite
    setLocalEdits(prev => ({ ...prev, [leadId]: { dm_draft: newDraft, action, at: Date.now() } }))

    // Persist via Netlify Function
    try {
      await fetch('/.netlify/functions/update-dm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leadId, dmDraft: newDraft, action }),
      })
    } catch (err) {
      console.error('Failed to persist DM edit:', err)
    }
  }, [])

  // After each poll, re-apply local edits that are less than 5 minutes old
  useEffect(() => {
    if (Object.keys(localEdits).length === 0) return
    const now = Date.now()
    const fresh = {}
    let needsUpdate = false

    Object.entries(localEdits).forEach(([id, edit]) => {
      if (now - edit.at < 300000) { // 5 minutes
        fresh[id] = edit
        needsUpdate = true
      }
    })

    if (needsUpdate) {
      setLeads(prev => prev.map(l => {
        const edit = fresh[l.id]
        if (edit) {
          return { ...l, outreach: { ...l.outreach, dm_draft: edit.dm_draft } }
        }
        return l
      }))
    }

    setLocalEdits(fresh)
  }, [lastSynced]) // Re-apply after each poll

  return {
    leads,
    activity,
    stats,
    ghlStatus,
    pipelineMetrics,
    loading,
    error,
    lastSynced,
    refresh: fetchAll,
    updateLeadDm,
  }
}
