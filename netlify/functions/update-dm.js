// Netlify Function: update a DM draft for a lead
// POST /.netlify/functions/update-dm
// Body: { "leadId": "lead_mia_001", "dmDraft": "new draft text", "action": "save"|"approve"|"reject" }

// For v1: writes to a pending edits queue file that OpenClaw processes
// For production: would write directly to the data store

const fs = require('fs')
const path = require('path')

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

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) }
  }

  try {
    const body = JSON.parse(event.body || '{}')
    const { leadId, dmDraft, action } = body

    if (!leadId) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'leadId required' }) }
    }

    // For now, update the leads.json directly in the publish directory
    // In production, this would hit SQLite or an API
    const dataDir = path.join(__dirname, '..', '..', 'dist', 'data')
    const leadsPath = path.join(dataDir, 'leads.json')
    
    // Netlify Functions run in a read-only filesystem except /tmp
    // So we'll store edits in /tmp and return success
    // The real persistence happens when OpenClaw syncs
    const editsPath = '/tmp/pending_edits.json'
    
    let edits = []
    try {
      const existing = fs.readFileSync(editsPath, 'utf8')
      edits = JSON.parse(existing)
    } catch (e) {
      // File doesn't exist yet
    }

    edits.push({
      leadId,
      dmDraft: dmDraft || null,
      action: action || 'save',
      timestamp: new Date().toISOString(),
    })

    fs.writeFileSync(editsPath, JSON.stringify(edits, null, 2))

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ 
        success: true, 
        message: `DM ${action || 'save'} queued for ${leadId}`,
        pendingEdits: edits.length 
      }),
    }
  } catch (err) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: err.message }),
    }
  }
}
