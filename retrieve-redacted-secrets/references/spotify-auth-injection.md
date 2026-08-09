# Spotify Auth Injection

When `hermes auth spotify login` times out (no browser available in a headless/remote
context), you can inject the provider state directly into your auth state file if you
have the credentials available.

## Prerequisites

- `SPOTIFY_CLIENT_ID` and `SPOTIFY_REFRESH_TOKEN` (from `.env` or a previous session)
- The redirect URI must match what's registered in the Spotify Developer Dashboard
- The refresh token must still be valid (not revoked)

## State structure

The provider state goes under `providers.spotify` in your auth state file:

```json
{
  "providers": {
    "spotify": {
      "client_id": "<CLIENT_ID>",
      "redirect_uri": "http://127.0.0.1:43827/spotify/callback",
      "accounts_base_url": "https://accounts.spotify.com",
      "api_base_url": "https://api.spotify.com/v1",
      "scope": "<FULL_SCOPE_STRING>",
      "granted_scope": "<FULL_SCOPE_STRING>",
      "token_type": "Bearer",
      "access_token": "",
      "refresh_token": "<REFRESH_TOKEN>",
      "obtained_at": "<ISO_TIMESTAMP>",
      "expires_at": "<ISO_TIMESTAMP>",
      "expires_in": 0,
      "auth_type": "oauth_pkce"
    }
  }
}
```

Key points:
- Set `access_token` to `""` — the empty value forces a refresh on first use
- Set `expires_at` to `now` — already-expired timestamp also forces a refresh
- `expires_in: 0` signals immediate expiry
- The refresh token is what matters; everything else auto-refreshes

## Verification

```bash
hermes auth spotify status
# Should show: spotify: logged in

# Gateway restart picks up the change:
systemctl --user restart hermes-gateway
```

## The refresh flow

On first tool use, `resolve_spotify_runtime_credentials()` detects the expired
`expires_at`, calls `_refresh_spotify_oauth_state()` which does:

```
POST https://accounts.spotify.com/api/token
  grant_type=refresh_token
  refresh_token=<token>
  client_id=<id>
```

If the refresh token is still valid, a fresh access token is returned and the
state is updated in-place. No further manual intervention needed.

## Scope string

The default Hermes scope covers everything the Spotify tools need:

```
user-read-playback-state user-modify-playback-state
user-read-currently-playing playlist-read-private
playlist-read-collaborative playlist-modify-public
playlist-modify-private user-follow-modify user-follow-read
user-library-read user-library-modify user-read-playback-position
user-top-read user-read-recently-played
```

## Pitfalls

- **Revoked refresh token**: If the token was revoked (client secret rotation,
  app deletion, explicit logout), the refresh will fail with a 400 and you'll
  need a full OAuth re-auth with a browser.
- **Wrong redirect URI**: The redirect URI in the state must match what's
  registered in the Spotify app dashboard, or token exchange may behave oddly
  (though this primarily affects the auth code flow, not refresh).
- **Gateway restart required**: Config changes and auth state changes need a
  gateway restart to take effect in messaging surfaces.
