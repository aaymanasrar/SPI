import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Drawings and IFC models are uploaded through a Server Action. The 1 MB
    // default would refuse almost every real drawing; this sits just above
    // MAX_FILE_BYTES (150 MB, src/modules/prototype/storage.ts) to leave room
    // for multipart overhead. Both limits must move together.
    serverActions: { bodySizeLimit: "160mb" },
    // The proxy buffers request bodies; without this a large upload is cut
    // off at 10 MB before the action sees it.
    proxyClientMaxBodySize: "160mb",
  },
};

export default nextConfig;
