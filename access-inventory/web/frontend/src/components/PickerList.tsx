interface PickerUser {
  email?: string
  full_name?: string
  first_name?: string
  last_name?: string
  department?: string
  job_title?: string
}

interface Props {
  users: PickerUser[]
  query: string
  onSelect: (email: string) => void
}

function displayName(u: PickerUser): string {
  if (u.full_name) return u.full_name
  const parts = [u.first_name, u.last_name].filter(Boolean)
  return parts.join(' ') || '—'
}

export default function PickerList({ users, query, onSelect }: Props) {
  const atLimit = users.length >= 50

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
      }}
    >
      <div
        className="px-5 py-3.5 border-b flex items-baseline gap-2"
        style={{ borderColor: 'var(--border-light)', backgroundColor: 'var(--bg-secondary)' }}
      >
        <h2 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
          {users.length}{atLimit ? '+' : ''} user{users.length !== 1 ? 's' : ''} found for &ldquo;{query}&rdquo;
        </h2>
        {atLimit && (
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Showing first 50 — refine your search for better results
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-secondary)' }}>
              {['Full Name', 'Email', 'Department', 'Job Title'].map(h => (
                <th
                  key={h}
                  className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide"
                  style={{ color: 'var(--text-secondary)', borderBottom: '2px solid var(--border-light)' }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => (
              <tr
                key={u.email ?? i}
                onClick={() => u.email && onSelect(u.email)}
                className="cursor-pointer transition-colors"
                style={{ borderBottom: '1px solid var(--border-light)' }}
                onMouseEnter={e => { (e.currentTarget as HTMLTableRowElement).style.backgroundColor = 'rgba(23,66,245,0.04)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLTableRowElement).style.backgroundColor = '' }}
              >
                <td className="px-4 py-3" style={{ color: 'var(--text-primary)' }}>{displayName(u)}</td>
                <td className="px-4 py-3" style={{ color: '#1742F5' }}>{u.email || '—'}</td>
                <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{u.department || '—'}</td>
                <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{u.job_title || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
