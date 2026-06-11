import { useEffect, useState } from 'react'
import StatusBadge from './StatusBadge'
import EmptyState from './EmptyState'

interface ToolRow {
  tool_name?: string
  username?: string
  status?: string
  user_role?: string
  last_login_date?: string
}

interface Props {
  rows: ToolRow[]
  query: string
}

export default function ToolAccessTable({ rows, query }: Props) {
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    const check = () => {
      const theme = document.documentElement.getAttribute('data-theme')
      if (theme === 'dark') {
        setIsDark(true)
      } else if (theme === 'light') {
        setIsDark(false)
      } else {
        setIsDark(window.matchMedia('(prefers-color-scheme: dark)').matches)
      }
    }
    check()
    const obs = new MutationObserver(check)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-primary)',
        border: '1px solid var(--border-light)',
        borderRadius: '0.75rem',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-md)',
        marginBottom: '2rem',
        animation: 'fadeIn 0.3s ease',
        transition: 'box-shadow 200ms ease',
      }}
    >
      <div
        className="px-5 py-3.5 border-b flex items-baseline gap-2"
        style={{ borderColor: 'var(--border-light)', backgroundColor: 'var(--bg-secondary)' }}
      >
        <h2 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
          Tool Access
        </h2>
        {rows.length > 0 && (
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {rows.length} environment{rows.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <div className="px-5 py-4">
        {rows.length === 0 ? (
          <EmptyState query={query} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  {['Tool / Environment', 'Username', 'Status', 'Role', 'Last Login'].map(h => (
                    <th
                      key={h}
                      className="text-left px-3 py-2 text-xs font-semibold uppercase tracking-wide"
                      style={{ color: 'var(--text-secondary)', borderBottom: '2px solid var(--border-light)' }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: '1px solid var(--border-light)' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLTableRowElement).style.backgroundColor = 'var(--bg-secondary)' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.backgroundColor = '' }}
                  >
                    <td className="px-3 py-2.5" style={{ color: 'var(--text-primary)' }}>
                      {row.tool_name || '—'}
                    </td>
                    <td
                      className="px-3 py-2.5"
                      style={{ color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8125rem' }}
                    >
                      {row.username || '—'}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge status={row.status || '—'} isDark={isDark} />
                    </td>
                    <td className="px-3 py-2.5" style={{ color: 'var(--text-secondary)' }}>
                      {row.user_role || '—'}
                    </td>
                    <td className="px-3 py-2.5" style={{ color: 'var(--text-tertiary)' }}>
                      {row.last_login_date || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
