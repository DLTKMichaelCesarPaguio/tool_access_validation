import { useState, useEffect } from 'react'

type Theme = 'light' | 'system' | 'dark'

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('theme')
  if (stored === 'light' || stored === 'dark') return stored
  return 'system'
}

function applyTheme(theme: Theme) {
  if (theme === 'system') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
  localStorage.setItem('theme', theme)
}

const OPTIONS: { value: Theme; label: string }[] = [
  { value: 'light',  label: '☀ Light'  },
  { value: 'system', label: '⬤ System' },
  { value: 'dark',   label: '☾ Dark'   },
]

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => { applyTheme(theme) }, [theme])

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        border: '1px solid rgba(255,255,255,0.25)',
        borderRadius: 6,
        overflow: 'hidden',
        background: 'rgba(255,255,255,0.08)',
      }}
    >
      {OPTIONS.map((opt, i) => (
        <button
          key={opt.value}
          role="radio"
          aria-checked={theme === opt.value}
          onClick={() => setTheme(opt.value)}
          style={{
            fontFamily: 'Figtree, system-ui, sans-serif',
            fontSize: 10,
            fontWeight: 600,
            padding: '3px 9px',
            border: 'none',
            borderRight: i < OPTIONS.length - 1 ? '1px solid rgba(255,255,255,0.2)' : 'none',
            background: theme === opt.value ? 'rgba(255,255,255,0.2)' : 'transparent',
            color: theme === opt.value ? '#fff' : 'rgba(255,255,255,0.7)',
            cursor: 'pointer',
            lineHeight: 1.6,
            transition: 'color 0.15s, background 0.15s',
            whiteSpace: 'nowrap',
          }}
          onMouseEnter={e => {
            if (theme !== opt.value)
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.12)'
          }}
          onMouseLeave={e => {
            if (theme !== opt.value)
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
