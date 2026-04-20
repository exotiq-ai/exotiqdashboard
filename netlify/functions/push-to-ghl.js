// Netlify Function: Push a lead to GHL
// POST /.netlify/functions/push-to-ghl
// Body: { lead: { full lead object } }

// This function is being deprecated for new lead creation in favor of promote-to-ghl.js.
// Its role will be for updating existing GHL contacts/opportunities in the future.
// For now, it returns a simple success message to avoid breaking existing frontend calls
// until they can be updated.

exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json',
  }

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers, body: '' }
  }

  return {
    statusCode: 200,
    headers,
    body: JSON.stringify({
      success: true,
      message: 'This lead does not need to be pushed to GHL at this stage.',
      skipped: true,
    }),
  }
}

