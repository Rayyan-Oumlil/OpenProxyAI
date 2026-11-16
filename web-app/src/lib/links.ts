export const GITHUB_URL = 'https://github.com/Rayyan-Oumlil/OpenProxyAI';
export const DOCS_URL = 'https://docs.openproxyai.com';
export const CALENDLY_URL = 'https://calendly.com/rayyanoumlil/30min';

/** Where each claim on the site can be checked. Paths are relative to the repository root. */
export const repoFile = (path: string): string => `${GITHUB_URL}/blob/main/${path}`;
export const docsPage = (path: string): string => `${DOCS_URL}${path}`;
