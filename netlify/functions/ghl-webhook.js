// netlify/functions/ghl-webhook.js
//
// Receives GHL outbound webhook events and writes them to an event queue
// for skills/ghl_listener_poller.py to process.
//
// SIGNATURE VERIFICATION (X-GHL-Signature, Ed25519):
//   GHL signs the raw request body with Ed25519. To enable in production:
//   1. npm install tweetnacl
//   2. Set GHL_WEBHOOK_PUBLIC_KEY env var to the base64-encoded public key
//      from https://services.leadconnectorhq.com/.well-known/webhooks-public-key
//   3. Uncomment the verification block in verifySignature() below.
//
// EVENT QUEUE:
//   Events are written as timestamped JSON files to QUEUE_PATH.
//   Set the QUEUE_PATH env var to a path readable by the Python poller.
//   For local dev: point QUEUE_PATH to netlify/functions/event_queue/
//   For production: replace with a persistent store (Netlify Blobs, Supabase).

const fs = require("fs");
const path = require("path");

const SUPPORTED_EVENTS = new Set([
  "ContactCreate",
  "ContactUpdate",
  "OpportunityStatusUpdate",
  "NoteCreate",
  "InboundMessage",
  "AppointmentCreate",
]);

const QUEUE_PATH =
  process.env.QUEUE_PATH ||
  path.join(__dirname, "event_queue");

function verifySignature(body, signature) {
  // STUB: Ed25519 verification. Logs a warning in v1 but does not block.
  //
  // To enable:
  // const nacl = require('tweetnacl');
  // const publicKey = Buffer.from(process.env.GHL_WEBHOOK_PUBLIC_KEY, 'base64');
  // const sigBytes = Buffer.from(signature, 'base64');
  // const bodyBytes = Buffer.from(body, 'utf-8');
  // return nacl.sign.detached.verify(bodyBytes, sigBytes, publicKey);
  if (!signature) {
    console.warn("[ghl-webhook] No X-GHL-Signature header -- verification not enforced in v1");
  }
  return true;
}

function writeEventToQueue(event) {
  const timestamp = Date.now();
  const eventType = (event.type || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `${timestamp}_${eventType}.json`;
  const filepath = path.join(QUEUE_PATH, filename);

  if (!fs.existsSync(QUEUE_PATH)) {
    fs.mkdirSync(QUEUE_PATH, { recursive: true });
  }

  fs.writeFileSync(filepath, JSON.stringify(event, null, 2), "utf-8");
  return filename;
}

exports.handler = async (netlifyEvent, context) => {
  if (netlifyEvent.httpMethod !== "POST") {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: "Method not allowed" }),
    };
  }

  const signature = netlifyEvent.headers["x-ghl-signature"] || "";
  const rawBody = netlifyEvent.body || "";

  verifySignature(rawBody, signature);

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch (e) {
    console.error("[ghl-webhook] Invalid JSON body:", e.message);
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Invalid JSON body" }),
    };
  }

  const eventType = payload.type || payload.event || "unknown";

  if (!SUPPORTED_EVENTS.has(eventType)) {
    console.log(`[ghl-webhook] Ignoring unsupported event type: ${eventType}`);
    return {
      statusCode: 200,
      body: JSON.stringify({ status: "ignored", type: eventType }),
    };
  }

  const enrichedEvent = {
    ...payload,
    type: eventType,
    received_at: new Date().toISOString(),
  };

  let filename;
  try {
    filename = writeEventToQueue(enrichedEvent);
  } catch (e) {
    console.error("[ghl-webhook] Failed to write event to queue:", e.message);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Failed to queue event" }),
    };
  }

  console.log(`[ghl-webhook] Queued ${eventType} -> ${filename}`);

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "queued", type: eventType, file: filename }),
  };
};
