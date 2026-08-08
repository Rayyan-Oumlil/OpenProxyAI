import { Routes, Route } from 'react-router-dom';
import Navigation from './components/Navigation';
import FooterSection from './sections/FooterSection';
import HomePage from './pages/HomePage';
import ProductPage from './pages/ProductPage';
import SecurityPage from './pages/SecurityPage';
import ProvidersPage from './pages/ProvidersPage';
import PricingPage from './pages/PricingPage';
import './App.css';

function App() {
  return (
    <div style={{ background: 'var(--bg)', color: 'var(--ink)', minHeight: '100vh', position: 'relative' }}>
      <div className="grid-bg" />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Navigation />
        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/product" element={<ProductPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/providers" element={<ProvidersPage />} />
            <Route path="/pricing" element={<PricingPage />} />
          </Routes>
        </main>
        <FooterSection />
      </div>
    </div>
  );
}

export default App;
