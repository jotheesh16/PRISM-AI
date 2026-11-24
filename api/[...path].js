// ==============================================================================
// PRISM AI — Vercel Serverless Edge Gateway
// Proxies all /api/* requests to the PRISM AI container backend
// ==============================================================================

export const config = {
  api: {
    bodyParser: false, // Enable streaming for binary PDF uploads & page rendering
    externalResolver: true,
  },
};

export default async function handler(req, res) {
  // Configured in Vercel Project Settings > Environment Variables
  const backendBase = (
    process.env.PRISM_BACKEND_URL ||
    process.env.BACKEND_URL ||
    "http://localhost:8765"
  ).replace(/\/+$/, "");

  let requestPath = req.url || "";
  if (requestPath.includes("[...path]")) {
    const segments = Array.isArray(req.query?.path)
      ? req.query.path.join("/")
      : req.query?.path || "";
    const queryParams = new URLSearchParams();
    for (const [k, v] of Object.entries(req.query || {})) {
      if (k !== "path") {
        if (Array.isArray(v)) v.forEach((val) => queryParams.append(k, val));
        else queryParams.append(k, v);
      }
    }
    const q = queryParams.toString();
    requestPath = `/api/${segments}${q ? "?" + q : ""}`;
  } else if (!requestPath.startsWith("/api/")) {
    requestPath = `/api${requestPath.startsWith("/") ? "" : "/"}${requestPath}`;
  }

  const targetUrl = `${backendBase}${requestPath}`;

  // Forward request headers, excluding host
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key.toLowerCase() !== "host") {
      headers[key] = value;
    }
  }

  try {
    const fetchOptions = {
      method: req.method,
      headers: headers,
      redirect: "manual",
    };

    // Forward request body for POST/PUT/DELETE
    if (!["GET", "HEAD"].includes(req.method.toUpperCase())) {
      const chunks = [];
      for await (const chunk of req) {
        chunks.push(chunk);
      }
      fetchOptions.body = Buffer.concat(chunks);
    }

    const backendRes = await fetch(targetUrl, fetchOptions);

    res.status(backendRes.status);
    backendRes.headers.forEach((value, name) => {
      // Don't forward transport-specific headers
      if (!["content-encoding", "transfer-encoding"].includes(name.toLowerCase())) {
        res.setHeader(name, value);
      }
    });

    const arrayBuffer = await backendRes.arrayBuffer();
    return res.send(Buffer.from(arrayBuffer));
  } catch (err) {
    console.error(`[PRISM Gateway Error] Failed to reach ${targetUrl}:`, err);
    return res.status(502).json({
      error: `PRISM AI Gateway Error: Unable to reach backend service at ${backendBase}. Ensure your PRISM backend is running and PRISM_BACKEND_URL is set in Vercel Project Settings. Error: ${err.message}`,
      status: 502,
    });
  }
}
