import { useEffect } from 'react';
import HeroSection from '../sections/HeroSection';

export default function HomePage() {
  useEffect(() => { document.title = 'OpenProxyAI · The control plane for enterprise AI'; }, []);

  return <HeroSection />;
}
