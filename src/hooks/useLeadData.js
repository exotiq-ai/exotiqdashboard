import { useState, useEffect, useCallback, useRef } from 'react'

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
  const [sequences, setSequences] = useState([])
  const [outreachQueue, setOutreachQueue] = useState([])
  const [leadSequences, setLeadSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastSynced, setLastSynced] = useState(null)

  // Local overrides that survive poll cycles (keyed by leadId)
  // Each override is a partial lead object merged on top of server data
  const localOverrides = useRef({})

  function applyOverrides(serverLeads) {
    const now = Date.now()
    // Clean expired overrides (older than 10 minutes)
    Object.entries(localOverrides.current).forEach(([id, entry]) => {
      if (now - entry._ts > 600000) delete localOverrides.current[id]
    })

    return serverLeads.map(l => {
      const override = localOverrides.current[l.id]
      if (!override) return l
      // Deep merge outreach overrides
      return {
        ...l,
        outreach: { ...l.outreach, ...override.outreach },
      }
    })
  }

  const fetchAll = useCallback(async () => {
    try {
      const [leadsData, activityData, statsData, ghlData, metricsData, seqData, queueData, enrollData] = await Promise.all([
        fetchJson('/data/leads.json'),
        fetchJson('/data/activity.json'),
        fetchJson('/data/stats.json'),
        fetchJson('/data/ghl_sync_status.json'),
        fetchJson('/data/pipeline_metrics.json'),
        fetchJson('/data/sequences.json').catch(() => []),
        fetchJson('/data/outreach_queue.json').catch(() => []),
        fetchJson('/data/lead_sequences.json').catch(() => []),
      ])
      const serverLeads = Array.isArray(leadsData) ? leadsData : []
      setLeads(applyOverrides(serverLeads))
      setActivity(Array.isArray(activityData) ? activityData : [])
      setStats(statsData)
      setGhlStatus(ghlData)
      setPipelineMetrics(metricsData)
      setSequences(Array.isArray(seqData) ? seqData : [])
      setOutreachQueue(Array.isArray(queueData) ? queueData : [])
      setLeadSequences(Array.isArray(enrollData) ? enrollData : [])
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

  // Update a lead locally and persist to Netlify Function
  const updateLead = useCallback(async (leadId, outreachUpdates, action) => {
    // Store override
    const existing = localOverrides.current[leadId]?.outreach || {}
    localOverrides.current[leadId] = {
      outreach: { ...existing, ...outreachUpdates },
      _ts: Date.now(),
    }

    // Update state immediately
    setLeads(prev => prev.map(l =>
      l.id === leadId
        ? { ...l, outreach: { ...l.outreach, ...outreachUpdates } }
        : l
    ))

    // Persist
    try {
      await fetch('/.netlify/functions/update-dm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          leadId,
          dmDraft: outreachUpdates.dm_draft,
          action: action || 'update',
          updates: outreachUpdates,
        }),
      })
    } catch (err) {
      console.error('Failed to persist update:', err)
    }
  }, [])

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
    updateLead,
    sequences,
    outreachQueue,
    leadSequences,
  }
}
