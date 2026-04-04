import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer, LabelList
} from 'recharts'

const FUNNEL_COLORS = ['#00D4AA', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981']

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const item = payload[0]
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 shadow-xl">
      <p className="text-text font-semibold text-sm">{label}</p>
      <p className="text-accent font-mono text-lg">{item.value}</p>
      {item.payload.pct != null && (
        <p className="text-muted text-xs">{item.payload.pct}% of previous stage</p>
      )}
    </div>
  )
}

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

export default function PipelineFunnel({ leads, metrics, loading }) {
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

  const allLeads = leads || []

  // Compute funnel from actual lead data
  const totalLeads = allLeads.length
  const scored = allLeads.filter(l => l.scoring?.score != null).length
  const qualified = allLeads.filter(l => (l.scoring?.score || 0) >= 3).length
  const withDm = allLeads.filter(l => l.outreach?.dm_draft).length
  const approved = allLeads.filter(l => l.outreach?.approval_status === 'APPROVED').length
  const dmSent = allLeads.filter(l => l.outreach?.dm1_sent).length
  const responded = allLeads.filter(l => l.outreach?.response_received).length
  const demoScheduled = allLeads.filter(l => l.outreach?.demo_scheduled).length

  const steps = [
    { name: 'Total Leads', value: totalLeads },
    { name: 'Scored', value: scored },
    { name: 'Qualified (3+)', value: qualified },
    { name: 'DM Drafted', value: withDm },
    { name: 'DM Approved', value: approved },
    { name: 'DM Sent', value: dmSent },
    { name: 'Responded', value: responded },
    { name: 'Demo', value: demoScheduled },
  ]

  const chartData = steps.map((step, i) => {
    const prevVal = i > 0 ? steps[i-1].value : null
    const pct = prevVal && prevVal > 0 ? Math.round((step.value / prevVal) * 100) : null
    return {
      name: step.name,
      value: step.value,
      pct,
      color: FUNNEL_COLORS[i % FUNNEL_COLORS.length],
    }
  })

  // Conversion rates
  const pct = (a, b) => b > 0 ? Math.round((a / b) * 100) : null
  const leadToDm = pct(dmSent, totalLeads)
  const dmToResponse = pct(responded, dmSent)
  const responseToDemo = pct(demoScheduled, responded)

  // By market breakdown
  const marketMap = {}
  allLeads.forEach(l => {
    const m = l.market || 'Unknown'
    if (!marketMap[m]) marketMap[m] = { total: 0, scored: 0, qualified: 0, dmSent: 0, responded: 0 }
    marketMap[m].total++
    if (l.scoring?.score != null) marketMap[m].scored++
    if ((l.scoring?.score || 0) >= 3) marketMap[m].qualified++
    if (l.outreach?.dm1_sent) marketMap[m].dmSent++
    if (l.outreach?.response_received) marketMap[m].responded++
  })

  const marketData = Object.entries(marketMap)
    .map(([name, data]) => ({ name, ...data }))
    .sort((a, b) => b.total - a.total)

  return (
    <div className="p-6 space-y-8">
      {/* Funnel chart */}
      <section>
        <h3 className="text-text font-semibold text-sm mb-1">Pipeline Funnel</h3>
        <p className="text-muted text-xs mb-4">Lead progression through each pipeline stage</p>

        <div className="bg-card border border-border rounded-lg p-4">
          <ResponsiveContainer width="100%" height={typeof window !== 'undefined' && window.innerWidth < 640 ? 180 : 280}>
            <BarChart data={chartData} margin={{ top: 20, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E1E2E" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#8888A0', fontSize: 10 }}
                axisLine={{ stroke: '#1E1E2E' }}
                tickLine={false}
                angle={-15}
                textAnchor="end"
                height={50}
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
          <div className="flex flex-wrap gap-6 mt-4 pt-4 border-t border-border">
            <div>
              <span className="text-muted text-xs block">Lead → DM Sent</span>
              <span className="font-mono text-accent text-lg font-bold">{leadToDm != null ? `${leadToDm}%` : '--'}</span>
            </div>
            <div>
              <span className="text-muted text-xs block">DM → Response</span>
              <span className="font-mono text-accent text-lg font-bold">{dmToResponse != null ? `${dmToResponse}%` : '--'}</span>
            </div>
            <div>
              <span className="text-muted text-xs block">Response → Demo</span>
              <span className="font-mono text-accent text-lg font-bold">{responseToDemo != null ? `${responseToDemo}%` : '--'}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Velocity */}
      <section>
        <h3 className="text-text font-semibold text-sm mb-4">Pipeline Snapshot</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VelocityCard label="Qualified Leads" value={qualified} unit="(S3+)" />
          <VelocityCard label="Awaiting Approval" value={allLeads.filter(l => l.outreach?.approval_status === 'PENDING').length} unit="DMs" />
          <VelocityCard label="Active Outreach" value={dmSent} unit="sent" />
          <VelocityCard label="Response Rate" value={dmToResponse} unit="%" />
        </div>
      </section>

      {/* By market */}
      <section>
        <h3 className="text-text font-semibold text-sm mb-4">By Market</h3>
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2 text-muted text-xs font-mono">Market</th>
                <th className="text-right px-4 py-2 text-muted text-xs font-mono">Total</th>
                <th className="text-right px-4 py-2 text-muted text-xs font-mono">Qualified</th>
                <th className="text-right px-4 py-2 text-muted text-xs font-mono">DM Sent</th>
                <th className="text-right px-4 py-2 text-muted text-xs font-mono">Responded</th>
              </tr>
            </thead>
            <tbody>
              {marketData.map((row, i) => (
                <tr key={row.name} className={i % 2 === 0 ? '' : 'bg-bg'}>
                  <td className="px-4 py-2 text-text font-medium">{row.name}</td>
                  <td className="px-4 py-2 text-right font-mono text-accent">{row.total}</td>
                  <td className="px-4 py-2 text-right font-mono text-text">{row.qualified}</td>
                  <td className="px-4 py-2 text-right font-mono text-text">{row.dmSent}</td>
                  <td className="px-4 py-2 text-right font-mono text-text">{row.responded}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
