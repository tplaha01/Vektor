interface FeatureCardProps {
  title: string;
  description: string;
  icon: string;
}

export function FeatureCard({ title, description, icon }: FeatureCardProps) {
  return (
    <div style={{
      padding: '2rem',
      borderRadius: '12px',
      background: 'linear-gradient(135deg, rgba(0, 212, 255, 0.05) 0%, rgba(255, 0, 255, 0.05) 100%)',
      border: '1px solid rgba(0, 212, 255, 0.1)',
      transition: 'all 0.3s ease',
      cursor: 'pointer',
    }}>
      <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>{icon}</div>
      <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.75rem', color: '#00d4ff' }}>
        {title}
      </h3>
      <p style={{ color: '#a0aec0', lineHeight: 1.6 }}>
        {description}
      </p>
    </div>
  );
}