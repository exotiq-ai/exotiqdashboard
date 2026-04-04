// Netlify Function: Push a lead to GHL
// POST /.netlify/functions/push-to-ghl
// Body: { lead: { full lead object } }

const https = require('https')

const GHL_TOKEN = process.env.GHL_API_TOKEN || 'pit-6bc107a4-45c3-410c-a35a-97badf293bd7'
const GHL_LOCATION = process.env.GHL_LOCATION_ID || 'hTOVcYDLS1UfuiNzuzpT'
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
}

function ghlFetch(method, path, body) {
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

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) }
  }

  try {
    const { lead } = JSON.parse(event.body || '{}')
    if (!lead || !lead.id) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'lead object required' }) }
    }

    const contact = lead.contact || {}
    const company = lead.company_data || {}
    const fleet = lead.fleet || {}
    const scoring = lead.scoring || {}
    const outreach = lead.outreach || {}
    const now = new Date().toISOString().split('T')[0]

    // GHL requires at least email or phone
    if (!contact.email && !contact.phone) {
      return {
        statusCode: 422,
        headers,
        body: JSON.stringify({
          error: `Cannot push ${lead.company} to GHL: no email or phone on file. Add contact info first.`,
          missing: 'email_or_phone',
        }),
      }
    }

    // Build tags
    const market = (lead.market || 'unknown').toLowerCase().replace(/[\/\s]+/g, '-')
    const fleetSize = fleet.size || 0
    const fleetTier = fleetSize < 10 ? 'under-10-fleet' : fleetSize < 25 ? '10-to-24-fleet' : '25-plus-fleet'
    const tags = ['exotiq-pipeline', `score-${scoring.score || 0}`, market, fleetTier]
    if (scoring.score === 5) tags.push('gregory-only')

    // Build custom fields
    const customFields = [
      { id: CUSTOM_FIELDS['Lead Score'], value: scoring.score || '' },
      { id: CUSTOM_FIELDS['Score Confidence'], value: scoring.confidence || '' },
      { id: CUSTOM_FIELDS['Fleet Size'], value: fleetSize || '' },
      { id: CUSTOM_FIELDS['IG Handle'], value: company.ig_handle || '' },
      { id: CUSTOM_FIELDS['DM Template Used'], value: outreach.template_used || '' },
      { id: CUSTOM_FIELDS['DM Draft'], value: (outreach.dm_draft || '').substring(0, 500) },
      { id: CUSTOM_FIELDS['Enrichment Sources'], value: 'Pipeline Dashboard' },
      { id: CUSTOM_FIELDS['OpenClaw Lead ID'], value: lead.id },
      { id: CUSTOM_FIELDS['Pipeline Entry Date'], value: now },
    ]

    // Step 1: Create contact
    const contactPayload = {
      firstName: contact.first_name || '',
      lastName: contact.last_name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      companyName: lead.company || '',
      address1: company.address || '',
      website: company.website || '',
      locationId: GHL_LOCATION,
      source: 'OpenClaw Pipeline',
      tags,
      customFields,
    }

    const contactRes = await ghlFetch('POST', '/contacts/', contactPayload)

    if (contactRes.status !== 200 && contactRes.status !== 201) {
      return {
        statusCode: contactRes.status,
        headers,
        body: JSON.stringify({ error: 'Failed to create contact', detail: contactRes.body }),
      }
    }

    const contactId = contactRes.body?.contact?.id || contactRes.body?.id
    if (!contactId) {
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'No contact ID returned' }) }
    }

    // Step 2: Create opportunity
    const stageName = scoring.score === 5 ? 'Gregory -- Personal Outreach' : 'DM Drafted'
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
    const oppId = oppRes.body?.opportunity?.id || oppRes.body?.id

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        success: true,
        contactId,
        opportunityId: oppId || null,
        stage: stageName,
        monetary,
        tags,
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
