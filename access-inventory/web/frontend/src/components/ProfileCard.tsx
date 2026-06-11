import StatusBadge from './StatusBadge'

interface AdProfile {
  email?: string
  full_name?: string
  job_title?: string
  department?: string
  employee_id?: string
  is_active?: boolean
}

interface Props {
  profile: AdProfile
}

export default function ProfileCard({ profile }: Props) {
  const fields = [
    { label: 'Email', value: profile.email },
    { label: 'Full Name', value: profile.full_name },
    { label: 'Job Title', value: profile.job_title },
    { label: 'Department', value: profile.department },
    { label: 'Employee ID', value: profile.employee_id },
  ]

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
        className="px-5 py-3.5 border-b"
        style={{ borderColor: 'var(--border-light)', backgroundColor: 'var(--bg-secondary)' }}
      >
        <h2 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
          Active Directory Profile
        </h2>
      </div>
      <div className="px-5 py-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {fields.map(f => (
          <div key={f.label} className="flex flex-col gap-0.5">
            <span
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--text-tertiary)' }}
            >
              {f.label}
            </span>
            <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {f.value || '—'}
            </span>
          </div>
        ))}
        <div className="flex flex-col gap-0.5">
          <span
            className="text-xs font-semibold uppercase tracking-wide"
            style={{ color: 'var(--text-tertiary)' }}
          >
            AD Status
          </span>
          <span>
            <StatusBadge status={profile.is_active ? 'Active' : 'Inactive'} />
          </span>
        </div>
      </div>
    </div>
  )
}
