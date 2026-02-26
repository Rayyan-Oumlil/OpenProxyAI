import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';

export default function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 100);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        isScrolled
          ? 'bg-[#0B0C0F]/90 backdrop-blur-md border-b border-white/5'
          : 'bg-transparent'
      }`}
    >
      <div className="w-full px-6 lg:px-10">
        <div className="flex items-center justify-between h-16 lg:h-20">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2">
            <span className="text-xl lg:text-2xl font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              openproxy<span className="text-[#B6FF2E]">AI</span>
            </span>
          </a>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center gap-8">
            <a href="#product" className="text-sm text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
              Product
            </a>
            <a href="#docs" className="text-sm text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
              Docs
            </a>
            <a href="#pricing" className="text-sm text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
              Pricing
            </a>
          </div>

          {/* Desktop CTAs */}
          <div className="hidden lg:flex items-center gap-4">
            <a href="#" className="text-sm text-[#A7AFBA] hover:text-[#F2F5F9] transition-colors">
              Sign in
            </a>
            <a href="#" className="btn-primary text-sm py-2 px-4">
              Get started
            </a>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="lg:hidden p-2 text-[#F2F5F9]"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="lg:hidden bg-[#0B0C0F]/95 backdrop-blur-md border-t border-white/5">
          <div className="px-6 py-6 space-y-4">
            <a href="#product" className="block text-lg text-[#F2F5F9]">Product</a>
            <a href="#docs" className="block text-lg text-[#F2F5F9]">Docs</a>
            <a href="#pricing" className="block text-lg text-[#F2F5F9]">Pricing</a>
            <div className="pt-4 border-t border-white/10 space-y-3">
              <a href="#" className="block text-lg text-[#A7AFBA]">Sign in</a>
              <a href="#" className="btn-primary w-full text-center">Get started</a>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
