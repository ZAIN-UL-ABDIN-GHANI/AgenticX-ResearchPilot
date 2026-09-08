import { NextResponse } from 'next/server';

/**
 * Lightweight liveness endpoint for the frontend container.
 *
 * Used by frontend/Dockerfile's HEALTHCHECK and by Docker Compose /
 * orchestrators to confirm the Next.js server itself is up and serving
 * requests (independent of backend/API availability).
 */
export async function GET() {
  return NextResponse.json({ status: 'healthy', service: 'researchpilot-frontend' });
}
