import { BookUser } from 'lucide-react'
import { useEffect, useState } from 'react'
import { marked } from 'marked'

export default function TrainingTab() {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/SDR_ONBOARDING.md')
      .then(res => res.text())
      .then(text => {
        // Use a proper markdown parser
        const html = marked.parse(text)
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
