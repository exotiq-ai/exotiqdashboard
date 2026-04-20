// Netlify Function: Promote a lead to GHL
// This is the primary function for creating new contacts and opportunities.
// POST /.netlify/functions/promote-to-ghl
// Body: { lead: { full lead object } }

// This file is a copy of the original push-to-ghl.js, repurposed
// for the new "Promote" workflow. All new lead creation logic lives here.

const https = require('https')

const GHL_TOKEN = process.env.GHL_API_TOKEN
const GHL_LOCATION = process.env.GHL_LOCATION_ID
const GHL_BASE = 'https://services.leadconnectorhq.com'

// Custom field IDs from ghl_config.json
const CUSTOM_FIELDS = {
  'Lead Score': 'XPkBEJOKRgV7DeZPKvS1',
  'Score Confidence': 'pRJGcFA15ccyjwMZEy2V',
  'Fleet Size': 'iA9wkjkAwneFIRH3sK1G',
  'Fleet Size Confidence': 'kjsORFx3ePhx1jUJswrS',
  'IG Handle': 'ZPB1aqwAac9FCni0E1NS',
  'IG Followers': 'lAKsYtvRqr4A5VcCKvaD',
  'Google Rating': '520dGS3ifDrj0QfvrkMR',
  'Google Reviews': '2k3t1mPsa5UMza9DBJlL',
  'Vehicle Types': 'L6cYyphzbD4WTaethcdW',
  'DM Template Used': 'w1SHCy6r4RrEKajn8iYq',
  'DM Draft': 'izdg9SFEiO10aOSPWd6z',
  'DO NOT SAY': 'sTXPnrvFbO3rSrbJcb8H',
  'Enrichment Sources': 'qJSS97RKJ8h2KYj2QCO8',
  'OpenClaw Lead ID': '6p8Xm6uR8ZlKDiyoiCOl',
  'Pipeline Entry Date': 'F0lnY590j5KnUJfbuQxM',
}

const PIPELINE_ID = 'FwSJkNdaae393EHWZyKq'
const STAGES = {
  'Gregory -- Personal Outreach': '1b61813b-8e74-43cc-a99f-5b16247b647a',
  'DM Drafted': 'a3bb9214-6292-41f9-9387-3e01f57c0a7b',
  'Qualified': 'a3bb9214-6292-41f9-9387-3e01f57c0a7b', // Qualified leads go to DM Drafted stage initially
}

function ghlFetch(method, path, body) {
  // (omitting identical ghlFetch implementation for brevity)
  return new Promise((resolve, reject) => {
    const url = new URL(path, GHL_BASE)
    const options = {
      method,
      hostname: url.hostname,
      path: url.pathname + url.search,
      headers: {
        'Authorization': `Bearer ${GHL_TOKEN}`,
        'Version': '2021-07-28',
        'Content-Type': 'application/json',
      },
    }
    const req = https.request(options, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) })
        } catch {
          resolve({ status: res.statusCode, body: data })
        }
      })
    })
    req.on('error', reject)
    if (body) req.write(JSON.stringify(body))
    req.end()
  })
}

function computeMonetary(fleetSize) {
  const size = parseInt(fleetSize) || 0
  if (size <= 0) return 79 * 12
  if (size <= 10) return Math.max(size * 29, 79) * 12
  if (size <= 25) return 399 * 12
  if (size <= 75) return 899 * 12
  return 1799 * 12
}

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

  try {
    const { lead } = JSON.parse(event.body || '{}')
    if (!lead || !lead.id) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'lead object required' }) }
    }

    // This function requires an email or phone number to proceed.
    if (!lead.contact_email && !lead.contact_phone) {
      return {
        statusCode: 422,
        headers,
        body: JSON.stringify({ error: 'Cannot promote lead: email or phone is required.' }),
      }
    }
    
    const now = new Date().toISOString().split('T')[0]

    // Build tags
    const market = (lead.market || 'unknown').toLowerCase().replace(/[\/\s]+/g, '-')
    const fleetSize = lead.fleet_size || 0
    const fleetTier = fleetSize < 10 ? 'under-10-fleet' : fleetSize < 25 ? '10-to-24-fleet' : '25-plus-fleet'
    const tags = ['exotiq-pipeline', `score-${lead.scoring_score || 0}`, market, fleetTier]
    if (lead.scoring_score === 5) tags.push('gregory-only')

    // Build custom fields
    const customFields = [
      { id: CUSTOM_FIELDS['Lead Score'], value: lead.scoring_score || '' },
      { id: CUSTOM_FIELDS['Score Confidence'], value: lead.scoring_confidence || '' },
      { id: CUSTOM_FIELDS['Fleet Size'], value: fleetSize || '' },
      { id: CUSTOM_FIELDS['IG Handle'], value: lead.company_ig_handle || '' },
      { id: CUSTOM_FIELDS['OpenClaw Lead ID'], value: lead.id },
      { id: CUSTOM_FIELDS['Pipeline Entry Date'], value: now },
    ]

    // Step 1: Create contact
    const contactPayload = {
      firstName: lead.contact_first_name || '',
      lastName: lead.contact_last_name || '',
      email: lead.contact_email || '',
      phone: lead.contact_phone || '',
      companyName: lead.company || '',
      website: lead.company_website || '',
      locationId: GHL_LOCATION,
      source: 'OpenClaw Pipeline',
      tags,
      customFields,
    }

    const contactRes = await ghlFetch('POST', '/contacts/', contactPayload)

    if (contactRes.status !== 200 && contactRes.status !== 201) {
      return { statusCode: contactRes.status, headers, body: JSON.stringify({ error: 'Failed to create GHL contact', detail: contactRes.body }) }
    }

    const contactId = contactRes.body?.contact?.id
    if (!contactId) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'No contact ID returned from GHL' }) }
    }

    // Step 2: Create opportunity
    const stageName = lead.scoring_score === 5 ? 'Gregory -- Personal Outreach' : 'Qualified'
    const stageId = STAGES[stageName]
    const monetary = computeMonetary(fleetSize)

    const oppPayload = {
      pipelineId: PIPELINE_ID,
      locationId: GHL_LOCATION,
      name: `${lead.company} - ${lead.market || 'Unknown'}`,
      pipelineStageId: stageId,
      status: 'open',
      contactId,
      monetaryValue: monetary,
    }

    const oppRes = await ghlFetch('POST', '/opportunities/', oppPayload)
    const oppId = oppRes.body?.opportunity?.id

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ success: true, contactId, opportunityId: oppId || null }),
    }
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) }
  }
}
