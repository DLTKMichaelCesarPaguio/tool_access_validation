import ThemeToggle from './ThemeToggle'

export default function Header() {
  return (
    <div
      style={{
        position: 'relative',
        background: 'linear-gradient(135deg, #1742F5 0%, #070D63 100%)',
        color: '#ffffff',
        padding: '0 3rem 0 0',
        borderRadius: '1rem',
        marginBottom: '2rem',
        boxShadow: '0px 3px 10px 1px rgba(7,26,36,0.32)',
        overflow: 'hidden',
      }}
    >
      {/* Theme toggle — absolutely positioned top-right */}
      <div style={{ position: 'absolute', top: 12, right: 12 }}>
        <ThemeToggle />
      </div>

      {/* Header content row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '3rem' }}>
        {/* Logo block */}
        <div style={{ flexShrink: 0, display: 'flex', alignItems: 'stretch' }}>
          <img
            src="/static/img/ProductSecurity_HD.png"
            alt="Deltek Product Security"
            style={{
              height: 140,
              width: 140,
              objectFit: 'cover',
              display: 'block',
              borderRight: '1px solid rgba(255,255,255,0.2)',
              marginRight: '3rem',
            }}
          />
        </div>

        {/* Text block — centered */}
        <div style={{ flex: 1, minWidth: 0, textAlign: 'center' }}>
          <h1
            style={{
              fontSize: 48,
              fontWeight: 700,
              marginBottom: '0.5rem',
              letterSpacing: '-0.5px',
              lineHeight: 1.1,
              color: '#ffffff',
            }}
          >
            ToolScope
          </h1>
          <p
            style={{
              fontSize: 11,
              fontWeight: 400,
              opacity: 0.65,
              lineHeight: 1.45,
              margin: '0 auto',
              maxWidth: 520,
            }}
          >
            Search for a user's active tool access across all security environments.
          </p>
        </div>
      </div>
    </div>
  )
}
