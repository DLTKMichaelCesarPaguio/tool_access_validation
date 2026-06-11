type BadgeVariant = 'active' | 'inactive' | 'active-access' | 'other'

function getVariant(status: string): BadgeVariant {
  const s = status.toLowerCase()
  if (s === 'active access') return 'active-access'
  if (s.includes('active') && !s.includes('inactive')) return 'active'
  if (s.includes('inactive') || s.includes('disabled')) return 'inactive'
  return 'other'
}

const COLORS: Record<BadgeVariant, { text: string; bg: string }> = {
  active:        { text: '#1F8B3D', bg: 'rgba(31,139,61,0.1)' },
  inactive:      { text: '#C7322B', bg: 'rgba(199,50,43,0.1)' },
  'active-access': { text: '#1742F5', bg: 'rgba(23,66,245,0.1)' },
  other:         { text: '#3C454E', bg: 'rgba(60,69,78,0.1)' },
}

const DARK_COLORS: Record<BadgeVariant, { text: string }> = {
  active:        { text: '#3fb950' },
  inactive:      { text: '#f85149' },
  'active-access': { text: '#6b9eff' },
  other:         { text: '#9ca3af' },
}

interface Props {
  status: string
  isDark?: boolean
}

export default function StatusBadge({ status, isDark = false }: Props) {
  const variant = getVariant(status)
  const colors = COLORS[variant]
  const darkText = DARK_COLORS[variant].text

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.175rem 0.6rem',
        borderRadius: '20px',
        fontSize: '0.75rem',
        fontWeight: 600,
        backgroundColor: colors.bg,
        color: isDark ? darkText : colors.text,
      }}
    >
      {status || '—'}
    </span>
  )
}
