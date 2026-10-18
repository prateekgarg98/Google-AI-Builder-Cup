import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const UPSTREAM_URL = process.env.UPSTREAM_URL || "https://api-gw---9-5wn92d82.uc.gateway.dev";

app.use(express.json());

// Main Query Route
app.post('/api/query', async (req, res) => {
  const apiKey = process.env.GATEWAY_KEY;

  if (!apiKey) {
    console.error("❌ ERROR: GATEWAY_KEY is missing from environment!");
    return res.status(500).json({ error: 'Server configuration error' });
  }

  try {
    // 1. Forward both query AND session_id to the backend for memory
    const payload = { 
      query: req.body.query,
      session_id: req.body.session_id 
    };

    const response = await fetch(`${UPSTREAM_URL}/?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // 2. Capture exact upstream error text for debugging
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ Upstream API failed [${response.status}]:`, errorText);
      return res.status(response.status).json({ 
        error: 'Failed to fetch from upstream AI service',
        details: errorText
      });
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    console.error('❌ Network/Proxy Error:', error.message);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Approvals Route Proxy
app.post('/api/approvals/:id/decision', async (req, res) => {
  const apiKey = process.env.GATEWAY_KEY;
  const approvalId = req.params.id;
  const { decision } = req.body;

  if (!apiKey) return res.status(500).json({ error: 'Server configuration error' });

  try {
    const response = await fetch(`${UPSTREAM_URL}/?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approval_id: approvalId,
        decision: decision,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ Upstream Approval failed [${response.status}]:`, errorText);
      return res.status(response.status).json({ error: 'Failed to fetch from upstream AI service', details: errorText });
    }

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (error) {
    console.error('❌ Approval error:', error.message);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Secure Artifact Download Proxy
app.get('/api/download', async (req, res) => {
  const fileUrl = req.query.url;

  if (!fileUrl || typeof fileUrl !== 'string') {
    return res.status(400).json({ error: 'Missing url parameter' });
  }

  try {
    const parsedUrl = new URL(fileUrl);
    // Security check: Only allow downloads from Google Cloud Storage
    if (parsedUrl.hostname !== 'storage.googleapis.com') {
      return res.status(403).json({ error: 'Untrusted download host' });
    }

    const response = await fetch(fileUrl);
    if (!response.ok) {
      return res.status(response.status).json({ error: 'Failed to download artifact' });
    }

    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    const rawFilename = path.basename(parsedUrl.pathname) || `artifact-${Date.now()}.png`;

    res.setHeader('Content-Type', contentType);
    res.setHeader('Content-Disposition', `attachment; filename="${rawFilename}"`);

    const arrayBuffer = await response.arrayBuffer();
    res.send(Buffer.from(arrayBuffer));
  } catch (error) {
    console.error('Download proxy error:', error.message);
    res.status(500).json({ error: 'Failed to proxy download' });
  }
});

if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, 'dist')));
  app.get(/.*/, (req, res) => res.sendFile(path.join(__dirname, 'dist', 'index.html')));
}

app.listen(PORT, () => console.log(`Secure backend listening on port ${PORT}`));