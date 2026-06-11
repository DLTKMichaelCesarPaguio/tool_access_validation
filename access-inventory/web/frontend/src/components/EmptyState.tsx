interface Props {
  query: string
}

export default function EmptyState({ query }: Props) {
  return (
    <p className="text-sm py-2" style={{ color: 'var(--text-secondary)' }}>
      No active tool access found for <strong style={{ color: 'var(--text-primary)' }}>{query}</strong>.
    </p>
  )
}
