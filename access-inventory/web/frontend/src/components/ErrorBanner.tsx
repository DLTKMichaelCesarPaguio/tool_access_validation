interface Props {
  message: string
}

export default function ErrorBanner({ message }: Props) {
  return (
    <div
      role="alert"
      className="rounded-lg px-4 py-3 mb-4 text-sm"
      style={{
        backgroundColor: 'rgba(199,50,43,0.08)',
        border: '1px solid rgba(199,50,43,0.3)',
        color: '#C7322B',
      }}
    >
      {message}
    </div>
  )
}
