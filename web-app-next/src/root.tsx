import type { ReactNode } from 'react';
import { Links, Meta, Outlet, Scripts, ScrollRestoration, isRouteErrorResponse } from 'react-router';
import { Analytics } from '@vercel/analytics/react';
import '@fontsource-variable/inter-tight';
import '@fontsource-variable/jetbrains-mono';
import './index.css';
import Navigation from './components/Navigation';
import Footer from './components/Footer';
import CommandPalette from './components/CommandPalette';

export function links() {
  return [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }];
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-signal focus:px-3 focus:py-2 focus:text-bg">
        Skip to content
      </a>
      <Navigation />
      <div id="main">
        <Outlet />
      </div>
      <Footer />
      <CommandPalette />
      <Analytics />
    </>
  );
}

export function ErrorBoundary({ error }: { error: unknown }) {
  const message = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : 'Something went wrong';
  return (
    <main>
      <h1>{message}</h1>
    </main>
  );
}
