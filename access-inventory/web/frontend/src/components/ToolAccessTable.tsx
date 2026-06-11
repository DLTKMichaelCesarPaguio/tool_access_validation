import { useEffect, useState } from 'react'
import StatusBadge from './StatusBadge'
import EmptyState from './EmptyState'
import type { ToolRow } from '../api'

const APP_SECURITY_CATEGORY = 'Application Security'
const CLOUD_SECURITY_CATEGORIES = new Set([
  'Endpoint Detection and Response',
  'Vulnerability Management',
])

function sectionOf(row: ToolRow): 'app' | 'cloud' | 'other' {
  const cat = row.category || ''
  if (cat === APP_SECURITY_CATEGORY) return 'app'
  if (CLOUD_SECURITY_CATEGORIES.has(cat)) return 'cloud'
  return 'other'
}

interface TableSectionProps {
  title: string
  rows: ToolRow[]
  isDark: boolean
}

function TableSection({ title, rows, isDark }: TableSectionProps) {
  if (rows.length === 0) return null
  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div
        className="px-5 py-2.5 border-b flex items-baseline gap-2"
        style={{ borderColor: 'var(--border-light)', backgroundColor: 'var(--bg-secondary)' }}
      >
        <h3 className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>
          {title}
        </h3>
        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
          {rows.length} environment{rows.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="px-5 py-3 overflow-x-auto">
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
    </div>
  )
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

  const appRows = rows.filter(r => sectionOf(r) === 'app')
  const cloudRows = rows.filter(r => sectionOf(r) === 'cloud')
  const otherRows = rows.filter(r => sectionOf(r) === 'other')
  const totalEnvs = rows.length

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
        {totalEnvs > 0 && (
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {totalEnvs} environment{totalEnvs !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="px-5 py-4">
          <EmptyState query={query} />
        </div>
      ) : (
        <div>
          <TableSection title="Cloud Security" rows={cloudRows} isDark={isDark} />
          <TableSection title="Application Security" rows={appRows} isDark={isDark} />
          <TableSection title="Other" rows={otherRows} isDark={isDark} />
        </div>
      )}
    </div>
  )
}
