import { BookUser } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function TrainingTab() {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/SDR_ONBOARDING.md')
      .then(res => res.text())
      .then(text => {
        // Basic markdown to HTML conversion
        const html = text
          .replace(/```([^`]+)```/g, (match, code) => `<pre class="bg-card p-3 rounded-lg text-xs font-mono">${code.trim()}</pre>`)
          .split('\\n')
          .map(line => line.trim())
          .join('\\n')
          .split('\\n\\n')
          .map(p => {
            if (p.startsWith('# ')) return `<h2 class="text-xl font-bold mt-6 mb-3 text-accent">${p.substring(2)}</h2>`
            if (p.startsWith('## ')) return `<h3 class="text-lg font-semibold mt-4 mb-2 text-text">${p.substring(3)}</h3>`
            if (p.startsWith('### ')) return `<h4 class="text-md font-medium mt-3 mb-1 text-muted">${p.substring(4)}</h4>`
            if (p.startsWith('- ')) {
              return '<ul>' + p.split('\\n').map(item => `<li>${item.substring(item.startsWith('- ') ? 2 : 0).replace(/`([^`]+)`/g, '<code>$1</code>')}</li>`).join('') + '</ul>'
            }
            p = p.replace(/`([^`]+)`/g, '<code>$1</code>')
            p = p.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
            return `<p class="text-sm leading-relaxed text-muted mb-4">${p}</p>`
          })
          .join('')

        setContent(html)
      })
      .catch(err => setContent('<p class="text-red-400">Failed to load training content.</p>'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <BookUser size={24} className="text-accent" />
        <div>
          <h2 className="text-xl font-bold text-text">SDR Onboarding</h2>
          <p className="text-muted text-sm">How to use the Exotiq Intelligence Pipeline</p>
        </div>
      </div>
      
      {loading ? (
        <div className="space-y-4">
          <div className="skeleton h-8 w-1/2 rounded" />
          <div className="skeleton h-20 w-full rounded" />
          <div className="skeleton h-8 w-1/3 rounded" />
          <div className="skeleton h-40 w-full rounded" />
        </div>
      ) : (
        <div 
          className="prose prose-invert prose-sm"
          dangerouslySetInnerHTML={{ __html: content }} 
        />
      )}
    </div>
  )
}
