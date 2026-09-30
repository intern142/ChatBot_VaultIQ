import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { PATHS } from '../routes/paths';

export default function NotFoundPage() {
  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.code}>404</h1>
        <p style={styles.message}>Page not found</p>
        <Link to={PATHS.home}>
          <Button>Go home</Button>
        </Link>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
  },
  card: {
    textAlign: 'center',
  },
  code: {
    margin: '0 0 12px',
    fontSize: '72px',
    fontWeight: 700,
    color: '#1e293b',
    lineHeight: 1,
  },
  message: {
    margin: '0 0 24px',
    fontSize: '18px',
    color: '#64748b',
  },
};