import { useState, FormEvent } from 'react'

interface Props {
  onSearch: (query: string) => void
  loading: boolean
}

export default function SearchBox({ onSearch, loading }: Props) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = value.trim()
    if (q) onSearch(q)
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderRadius: '0.75rem',
        padding: '2rem',
        boxShadow: 'var(--shadow-md)',
        marginBottom: '2rem',
      }}
    >
      <form onSubmit={handleSubmit} className="flex gap-3 items-end">
        <div className="flex-1">
          <label
            htmlFor="search-input"
            className="block text-xs font-semibold mb-1.5 uppercase tracking-wide"
            style={{ color: 'var(--text-secondary)' }}
          >
            Search by name, email, or username
          </label>
          <input
            id="search-input"
            type="text"
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder="e.g. Firstname Lastname, email@deltek.com, or username"
            autoComplete="off"
            autoFocus
            style={{
              width: '100%',
              padding: '0.75rem 1rem',
              border: '2px solid var(--border-medium)',
              borderRadius: '0.5rem',
              fontSize: '1rem',
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              outline: 'none',
              transition: 'border-color 200ms ease',
            }}
            onFocus={e => { e.currentTarget.style.borderColor = '#1742F5'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(23,66,245,0.15)' }}
            onBlur={e => { e.currentTarget.style.borderColor = 'var(--border-medium)'; e.currentTarget.style.boxShadow = 'none' }}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.75rem 2rem',
            border: 'none',
            borderRadius: '0.5rem',
            fontSize: '1rem',
            fontWeight: 500,
            color: '#fff',
            backgroundColor: '#1742F5',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: (loading || !value.trim()) ? 0.5 : 1,
            transition: 'all 200ms ease',
            whiteSpace: 'nowrap',
            flexShrink: 0,
          }}
          onMouseEnter={e => { if (!loading && value.trim()) { (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#070D63'; (e.currentTarget as HTMLButtonElement).style.boxShadow = 'var(--shadow-md)' } }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = '#1742F5'; (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none' }}
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span
                className="inline-block w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"
              />
              Searching…
            </span>
          ) : 'Search'}
        </button>
      </form>
    </div>
  )
}
