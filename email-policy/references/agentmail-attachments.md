# AgentMail Attachments — Size Limits & Workarounds

## MCP tool limitation
The `mcp_agentmail_reply_to_message` and `mcp_agentmail_send_message` tools accept an `attachments` parameter, but base64-encoded content above ~500KB-1MB typically fails validation with `invalid_format`.

**Do not attempt to attach files via the MCP attachment parameter unless the file is very small (<500KB).**

## Working approach: direct REST API

Use the `v0/inboxes/:inboxId/messages/send` endpoint directly via curl or Python requests:

```python
import base64, requests

# Read API key from ~/.hermes/.env
with open("[home-dir]/.hermes/.env") as f:
    for line in f:
        if "AGENTMAIL_API_KEY" in line:
            api_key = line.split("=")[1].strip().strip('"\'')
            break

# Encode the file
with open("/path/to/file", "rb") as f:
    b64_content = base64.b64encode(f.read()).decode("ascii")

# Send
payload = {
    "to": "recipient@example.com",
    "subject": "Re: thread subject — attachment",
    "text": "Body text here.",
    "attachments": [{
        "content": b64_content,
        "filename": "filename.ext",
        "content_type": "application/octet-stream"
    }]
}

resp = requests.post(
    f"https://api.agentmail.to/v0/inboxes/{inbox_id}/messages/send",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=payload,
    timeout=60
)
```

## Important caveats

- **New thread created**: Sending via this endpoint creates a NEW thread, it does NOT nest under the existing thread. To reply in-thread, use `mcp_agentmail_reply_to_message` for text only, then use the REST API for the attachment if needed (you'll have to manage two messages).
- **Base64 size overhead**: 2.2MB video → ~3MB base64 — this worked fine with the REST API.
- **Content-Type**: `video/mp4`, `image/jpeg`, `application/pdf` all worked. For unknown types, use `application/octet-stream`.
- **API key location**: `AGENTMAIL_API_KEY` in `~/.hermes/.env`.
- **Endpoint**: `https://api.agentmail.to/v0/inboxes/{inboxId}/messages/send` (note: `v0`, not `v1`).
