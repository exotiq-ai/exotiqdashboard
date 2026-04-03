import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer, LabelList
} from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

const FUNNEL_COLORS = ['#00D4AA', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981']

function VelocityCard({ label, value, unit = 'days' }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <p className="text-muted text-xs font-mono uppercase tracking-wider mb-1">{label}</p>
      <p className="text-text font-mono font-bold text-2xl">
        {value != null ? value : '--'}
        {value != null && <span className="text-muted text-sm font-normal ml-1">{unit}</span>}
      </p>
    </div>
  )
}

function TrendIndicator({ trend }) {
  if (!trend) return null
  if (trend === 'improving') return <TrendingUp size={16} className="text-green-400" />
  if (trend === 'slowing') return <TrendingDown size={16} className="text-red-400" />
  return <Minus size={16} className="text-muted" />
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const item = payload[0]
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 shadow-xl">
      <p className="text-text font-semibold text-sm">{label}</p>
      <p className="text-accent font-mono text-lg">{item.value}</p>
      {item.payload.pct != null && (
        <p className="text-muted text-xs">{item.payload.pct}% conversion</p>
      )}
    </div>
  )
}

export default function PipelineFunnel({ metrics, loading }) {
  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="skeleton w-full h-64 rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="skeleton h-20 rounded-lg" />)}
        </div>
      </div>
    )
  }

  const funnel = metrics?.funnel || {}
  const conversionRates = metrics?.conversion_rates || {}
  const velocity = metrics?.velocity || {}
  const byMarket = metrics?.by_market || {}

  const steps = [
    { name: 'Total Leads', key: 'total_leads', color: FUNNEL_COLORS[0] },
    { name: 'Scored', key: 'scored', color: FUNNEL_COLORS[1] },
    { name: 'Approved', key: 'approved_for_outreach', color: FUNNEL_COLORS[2] },
    { name: 'DM Sent', key: 'dm1_sent', color: FUNNEL_COLORS[3] },
    { name: 'Responded', key: 'responded', color: FUNNEL_COLORS[4] },
    { name: 'Demo', key: 'demo_scheduled', color: FUNNEL_COLORS[5] },
  ]

  const chartData = steps.map((step, i) => {
    const val = funnel[step.key] || 0
    const prevVal = i > 0 ? (funnel[steps[i-1].key] || 0) : null
    const pct = prevVal && prevVal > 0 ? Math.round((val / prevVal) * 100) : null
    return {
      name: step.name,
      value: val,
      pct,
      color: step.color,
    }
  })

  const marketData = Object.entries(byMarket).map(([market, data]) => ({
    name: market,
    total: data.total || 0,
    approved: data.approved || 0,
    dm_sent: data.dm_sent || 0,
  }))

  return (
    <div className="p-6 space-y-8">
      {/* Funnel chart */}
      <section>
        <h3 className="text-text font-semibold text-sm mb-1">Pipeline Funnel</h3>
        <p className="text-muted text-xs mb-4">Lead-to-customer conversion at each stage</p>

        <div className="bg-card border border-border rounded-lg p-4">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 20, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#8888A0', fontSize: 11 }}
                axisLine={{ stroke: '#1E1E2E' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#8888A0', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,212,170,0.05)' }} />
              <Bar dataKey="value" radius={[4,4,0,0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
                <LabelList
                  dataKey="value"
                  position="top"
                  style={{ fill: '#E8E8F0', fontSize: 12, fontFamily: 'JetBrains Mono', fontWeight: 600 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Conversion rates */}
          <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2">
              <span className="text-muted text-xs">Lead to DM:</span>
              <span className="font-mono text-accent text-sm font-semibold">
                {conversionRates.lead_to_dm != null
                  ? `${Math.round(conversionRates.lead_to_dm * 100)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted text-xs">DM to Response:</span>
              <span className="font-mono text-accent text-sm font-semibold">
                {conversionRates.dm_to_response != null
                  ? `${Math.round(conversionRates.dm_to_response * 100)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted text-xs">Response to Demo:</span>
              <span className="font-mono text-accent text-sm font-semibold">
                {conversionRates.response_to_demo != null
                  ? `${Math.round(conversionRates.response_to_demo * 100)}%`
                  : '--'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Velocity metrics */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-text font-semibold text-sm">Velocity Metrics</h3>
          <TrendIndicator trend={metrics?.pipeline_trend} />
          {metrics?.pipeline_trend && (
            <span className={`text-xs capitalize ${
              metrics.pipeline_trend === 'improving' ? 'text-green-400' :
              metrics.pipeline_trend === 'slowing' ? 'text-red-400' : 'text-muted'
            }`}>
              {metrics.pipeline_trend}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VelocityCard label="Discovery to Contact" value={metrics?.avg_days_discovery_to_contact} />
          <VelocityCard label="Contact to Response" value={metrics?.avg_days_contact_to_response} />
          <VelocityCard label="Response to Demo" value={metrics?.avg_days_response_to_demo} />
          <VelocityCard label="Leads (7 days)" value={velocity.leads_added_last_7_days} unit="new" />
        </div>
      </section>

      {/* By market */}
      {marketData.length > 0 && (
        <section>
          <h3 className="text-text font-semibold text-sm mb-4">By Market</h3>
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-4 py-2 text-muted text-xs font-mono">Market</th>
                  <th className="text-right px-4 py-2 text-muted text-xs font-mono">Total</th>
                  <th className="text-right px-4 py-2 text-muted text-xs font-mono">Approved</th>
                  <th className="text-right px-4 py-2 text-muted text-xs font-mono">DM Sent</th>
                </tr>
              </thead>
              <tbody>
                {marketData.map((row, i) => (
                  <tr key={row.name} className={i % 2 === 0 ? '' : 'bg-bg'}>
                    <td className="px-4 py-2 text-text font-medium">{row.name}</td>
                    <td className="px-4 py-2 text-right font-mono text-accent">{row.total}</td>
                    <td className="px-4 py-2 text-right font-mono text-text">{row.approved}</td>
                    <td className="px-4 py-2 text-right font-mono text-text">{row.dm_sent}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
