export const GITHUB_URL = 'https://github.com/Rayyan-Oumlil/OpenProxyAI';
export const DOCS_URL = 'https://docs.openproxyai.com';
export const LINKEDIN_URL = 'https://www.linkedin.com/in/rayyan-oumlil-871b192b6';

export function sourceUrl(repoPath: string): string {
  if (repoPath.startsWith('/') || repoPath.includes('..')) {
    throw new Error(`sourceUrl: expected a repo-relative path, got "${repoPath}"`);
  }
  return `${GITHUB_URL}/blob/main/${repoPath}`;
}
