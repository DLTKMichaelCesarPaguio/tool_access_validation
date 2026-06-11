import { useState } from 'react'
import Header from './components/Header'
import SearchBox from './components/SearchBox'
import ErrorBanner from './components/ErrorBanner'
import PickerList from './components/PickerList'
import ProfileCard from './components/ProfileCard'
import ToolAccessTable from './components/ToolAccessTable'
import { searchUsers, type SearchResult } from './api'

export default function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSearch(q: string) {
    setQuery(q)
    setLoading(true)
    setResult(null)
    try {
      const data = await searchUsers(q)
      setResult(data)
    } catch {
      setResult({ ad_profile: null, tool_access: [], picker_users: [], error: 'Network error — could not reach the server.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-secondary)' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem', paddingTop: 'calc(1.5rem + 4px)' }}>
        <Header />
        <SearchBox onSearch={handleSearch} loading={loading} />

        {result?.error && <ErrorBanner message={result.error} />}

        {result?.picker_users && result.picker_users.length > 0 && (
          <PickerList
            users={result.picker_users}
            query={query}
            onSelect={email => handleSearch(email)}
          />
        )}

        {result?.ad_profile && (
          <ProfileCard profile={result.ad_profile} />
        )}

        {result?.ad_profile && (
          <ToolAccessTable
            rows={result.tool_access ?? []}
            query={query}
          />
        )}

        <footer className="mt-6 text-xs text-center" style={{ color: 'var(--text-tertiary)' }}>
          Deltek Global Information Security &mdash; Access Inventory v1
        </footer>
      </div>
    </div>
  )
}
