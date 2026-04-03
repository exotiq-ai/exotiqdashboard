// netlify/functions/health.js
// Health check endpoint. Access at: /.netlify/functions/health

exports.handler = async (event, context) => {
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status: "ok",
      service: "exotiq-ghl-listener",
      timestamp: new Date().toISOString(),
    }),
  };
};
