import { Search, X, ChevronDown, ChevronUp, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

const SCORE_OPTIONS = ['5', '4', '3', '2', '1']

const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Score (high to low)' },
  { value: 'score_asc', label: 'Score (low to high)' },
  { value: 'updated', label: 'Last Updated' },
  { value: 'market', label: 'Market' },
  { value: 'company', label: 'Company (A-Z)' },
]

function MultiSelect({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false)

  function toggle(val) {
    if (selected.includes(val)) {
      onChange(selected.filter(v => v !== val))
    } else {
      onChange([...selected, val])
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs transition-all ${
          selected.length > 0
            ? 'border-accent text-accent'
            : 'border-border text-muted hover:border-gray-600'
        }`}
      >
        {label}
        {selected.length > 0 && (
          <span className="bg-accent text-black rounded-full px-1.5 text-[10px] font-bold">
            {selected.length}
          </span>
        )}
        <ChevronDown size={12} />
      </button>

      {open && (
        <div className="absolute top-full mt-1 left-0 z-20 bg-card border border-border rounded shadow-xl min-w-36">
          {options.map(opt => {
            const val = typeof opt === 'string' ? opt : opt.value
            const label2 = typeof opt === 'string' ? opt : opt.label
            const checked = selected.includes(val)
            return (
              <button
                key={val}
                onClick={() => toggle(val)}
                className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 hover:bg-border transition-all ${
                  checked ? 'text-accent' : 'text-text'
                }`}
              >
                <span className={`w-3 h-3 rounded border flex-shrink-0 flex items-center justify-center ${
                  checked ? 'bg-accent border-accent' : 'border-muted'
                }`}>
                  {checked && <span className="text-black text-[8px] font-bold">x</span>}
                </span>
                {label2}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function FilterBar({ filters, onChange, markets, statuses }) {
  const [open, setOpen] = useState(false)

  function clearAll() {
    onChange({
      markets: [],
      scores: [],
      statuses: [],
      search: '',
      sortBy: 'score_desc',
    })
  }

  const hasFilters =
    filters.markets.length > 0 ||
    filters.scores.length > 0 ||
    filters.statuses.length > 0 ||
    filters.search

  const marketOptions = (markets || []).map(m => ({ value: m, label: m }))
  const statusOptions = (statuses || []).map(s => ({ value: s, label: s }))

  return (
    <div className="border-b border-border bg-bg">
      {/* Toggle row -- always visible on mobile */}
      <div className="flex items-center gap-2 px-4 py-2 md:hidden">
        <button
          onClick={() => setOpen(o => !o)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs transition-all ${
            hasFilters ? 'border-accent text-accent' : 'border-border text-muted'
          }`}
        >
          <SlidersHorizontal size={12} />
          Filters
          {hasFilters && <span className="bg-accent text-black rounded-full px-1.5 text-[10px] font-bold">
            {(filters.markets.length + filters.scores.length + filters.statuses.length + (filters.search ? 1 : 0))}
          </span>}
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {/* Inline search always visible */}
        <div className="relative flex-1">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search..."
            value={filters.search}
            onChange={e => onChange({ ...filters, search: e.target.value })}
            className="w-full pl-8 pr-3 py-1.5 bg-card border border-border rounded text-xs text-text placeholder-muted focus:outline-none focus:border-accent"
          />
          {filters.search && (
            <button onClick={() => onChange({ ...filters, search: '' })}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text">
              <X size={12} />
            </button>
          )}
        </div>
        {hasFilters && (
          <button onClick={clearAll} className="flex items-center gap-1 px-2 py-1.5 rounded border border-red-900 text-red-400 text-xs">
            <X size={12} />
          </button>
        )}
      </div>

      {/* Full filter bar -- desktop always visible, mobile collapsible */}
      <div className={`${open ? 'flex' : 'hidden'} md:flex flex-wrap items-center gap-2 px-4 py-2`}>
      {/* Search */}
      <div className="relative flex-1 min-w-48 max-w-64">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="text"
          placeholder="Search company, contact, IG..."
          value={filters.search}
          onChange={e => onChange({ ...filters, search: e.target.value })}
          className="w-full pl-8 pr-3 py-1.5 bg-card border border-border rounded text-xs text-text placeholder-muted focus:outline-none focus:border-accent"
        />
        {filters.search && (
          <button
            onClick={() => onChange({ ...filters, search: '' })}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Market */}
      <MultiSelect
        label="Market"
        options={marketOptions}
        selected={filters.markets}
        onChange={val => onChange({ ...filters, markets: val })}
      />

      {/* Score */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border">
        <span className="text-muted text-xs mr-1">Score:</span>
        {SCORE_OPTIONS.map(s => {
          const active = filters.scores.includes(s)
          const colorMap = { '5': 'text-yellow-400', '4': 'text-accent', '3': 'text-blue-400', '2': 'text-gray-400', '1': 'text-gray-600' }
          return (
            <button
              key={s}
              onClick={() => {
                const next = active
                  ? filters.scores.filter(v => v !== s)
                  : [...filters.scores, s]
                onChange({ ...filters, scores: next })
              }}
              className={`w-6 h-6 rounded text-xs font-mono font-bold transition-all ${
                active
                  ? `bg-card border border-accent ${colorMap[s]}`
                  : `text-muted hover:text-text`
              }`}
            >
              {s}
            </button>
          )
        })}
      </div>

      {/* Status */}
      {statusOptions.length > 0 && (
        <MultiSelect
          label="Status"
          options={statusOptions}
          selected={filters.statuses}
          onChange={val => onChange({ ...filters, statuses: val })}
        />
      )}

      {/* Sort */}
      <select
        value={filters.sortBy}
        onChange={e => onChange({ ...filters, sortBy: e.target.value })}
        className="px-3 py-1.5 bg-card border border-border rounded text-xs text-text focus:outline-none focus:border-accent"
      >
        {SORT_OPTIONS.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>

      {/* Clear */}
      {hasFilters && (
        <button
          onClick={clearAll}
          className="flex items-center gap-1 px-3 py-1.5 rounded border border-red-900 text-red-400 hover:bg-red-950 text-xs transition-all"
        >
          <X size={12} />
          Clear
        </button>
      )}
      </div>
    </div>
  )
}
