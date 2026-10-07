# Deploy `simulator-ada.tofshield.com`

This deployment runs the Flask/h5py application in a Cloudflare Container and
routes requests through a Cloudflare Worker. The repository deliberately
excludes measured HDF5 data, uploads, local paths, caches, and credentials.

## One-time Cloudflare setup

1. Confirm **Workers & Pages > Containers** is enabled for the account that
   owns `tofshield.com`.
2. Create an API token with the permissions Wrangler requests for Workers,
   Containers, Durable Objects, and the `tofshield.com` zone.
3. In the public GitHub repository, add Actions secrets:
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`
4. Run the **Deploy to Cloudflare** workflow. The configuration claims the
   custom domain `simulator-ada.tofshield.com`.

## Protect the application with email OTP

In **Cloudflare Zero Trust > Access > Applications**:

1. Add a **Self-hosted** application.
2. Use application domain `simulator-ada.tofshield.com` and path `/*`.
3. Create one **Allow** policy with the selector **Emails** and these exact
   values:
   - `sali@tofshield.com`
   - `gonin@tofshield.com`
4. Under login methods, enable **One-time PIN**.
5. Do not add an `Everyone` allow rule.
6. Save, open a private browser window, and verify that an unlisted address is
   denied while each approved address receives a PIN.

## Local production-container check

```bash
docker build -t tofshield-ada-simulator .
docker run --rm -p 8080:8080 tofshield-ada-simulator
```

Then open `http://127.0.0.1:8080/api/health`.

## Data-handling note

The online deployment supports browser uploads and synthetic generation.
Cloudflare request-size and Container resource limits apply. Large measured
files should continue to use the local Ubuntu application. Uploaded and
generated files live only in the running Container's temporary filesystem and
must not be treated as durable storage.
