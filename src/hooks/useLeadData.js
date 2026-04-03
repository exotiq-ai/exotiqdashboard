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
  }
}
