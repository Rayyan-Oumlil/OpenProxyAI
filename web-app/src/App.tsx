import { useEffect } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import Navigation from './components/Navigation';
import FooterSection from './sections/FooterSection';
import HomePage from './pages/HomePage';
import ProductPage from './pages/ProductPage';
import SecurityPage from './pages/SecurityPage';
import ProvidersPage from './pages/ProvidersPage';
import ComparePage from './pages/ComparePage';
import PricingPage from './pages/PricingPage';
import { useScrollReveal } from './lib/useScrollReveal';
import { useSiteMotion } from './lib/useSiteMotion';
import { useSiteMeasurement } from './lib/useSiteMeasurement';
import './App.css';

function App() {
  const { pathname } = useLocation();
  useScrollReveal([pathname]);
  // A new page starts at its top; a link with a #section goes to that section.
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    const target = hash ? document.getElementById(hash) : null;
    if (target) target.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [pathname]);
  useSiteMotion(pathname);
  useSiteMeasurement(pathname);

  return (
    <div style={{ background: 'var(--bg)', color: 'var(--ink)', minHeight: '100vh', position: 'relative' }}>
      <div className="sprog" aria-hidden="true" style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: 2, background: 'var(--ink)', zIndex: 40 }} />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Navigation />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/product" element={<ProductPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/providers" element={<ProvidersPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/pricing" element={<PricingPage />} />
          </Routes>
        </main>
        <FooterSection />
      </div>
      <Analytics />
    </div>
  );
}

export default App;
