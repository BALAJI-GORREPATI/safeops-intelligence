import type { NextConfig } from 'next';
const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
const config: NextConfig = {
  devIndicators: false,
  turbopack: { root: process.cwd() },
  async rewrites() { return [{ source: '/api/:path*', destination: `${backendUrl}/api/:path*` }]; },
};
export default config;
