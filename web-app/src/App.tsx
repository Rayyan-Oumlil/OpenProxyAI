import Navigation from './components/Navigation';
import HeroSection from './sections/HeroSection';
import PipelineSection from './sections/PipelineSection';
import RouterSection from './sections/RouterSection';
import BudgetsPoliciesSection from './sections/BudgetsPoliciesSection';
import DeploySection from './sections/DeploySection';
import PricingSection from './sections/PricingSection';
import FooterSection from './sections/FooterSection';
import './App.css';

function App() {
  return (
    <div style={{ background: 'var(--bg)', color: 'var(--ink)', minHeight: '100vh', position: 'relative' }}>
      <div className="grid-bg" />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Navigation />
        <main>
          <HeroSection />
          <PipelineSection />
          <RouterSection />
          <BudgetsPoliciesSection />
          <DeploySection />
          <PricingSection />
          <FooterSection />
        </main>
      </div>
    </div>
  );
}

export default App;
