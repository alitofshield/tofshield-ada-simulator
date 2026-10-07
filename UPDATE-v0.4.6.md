# Version 0.4.6

- Adds a production Gunicorn container image for the Flask/h5py application.
- Adds a Cloudflare Worker and Container configuration for
  `simulator-ada.tofshield.com`.
- Adds GitHub Actions test and deployment workflows.
- Excludes measured HDF5 files, local caches, credentials, and the private Team
  Share acquisition catalog from the public deployment.
- Retains browser upload, HDF5 analysis, companion-file analysis, synthetic
  Vocus/mipTOF generation, and generated-file download.
