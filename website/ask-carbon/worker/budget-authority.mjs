import { AskCarbonUsageLedger } from "./ledger.mjs";

export { AskCarbonUsageLedger };

// The shared budget authority is reachable only through an explicit Durable
// Object binding from approved Ask Carbon deployments. It has no public API.
export default {
  async fetch() {
    return new Response(JSON.stringify({ error: { code: "not_found", message: "Not found." } }), {
      status: 404,
      headers: { "cache-control": "no-store", "content-type": "application/json; charset=utf-8" },
    });
  },
};
