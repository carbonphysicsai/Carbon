import askCarbon from "./index.mjs";
import { stagingRequestAuthorized } from "./staging-auth.mjs";

const previewHeaders = {
  "cache-control": "no-store",
  "content-type": "text/html; charset=utf-8",
  "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff",
  "x-robots-tag": "noindex, nofollow, noarchive",
};

const accessDenied = () => new Response("Private staging authentication is required.", {
  status: 401,
  headers: {
    ...previewHeaders,
    "www-authenticate": "Basic realm=\"Carbon Ask private staging\", charset=\"UTF-8\"",
  },
});

export default {
  async fetch(request, env, context) {
    if (!stagingRequestAuthorized(request, env)) return accessDenied();
    const url = new URL(request.url);
    if (url.pathname === "/pilot") {
      if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed.", { status: 405, headers: previewHeaders });
      return new Response(null, {
        status: 302,
        headers: { ...previewHeaders, location: "/ask-carbon/pilot-designer.html" },
      });
    }
    return askCarbon.fetch(request, env, context);
  },
};
