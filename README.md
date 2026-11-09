# AI Shorts Studio — cloud deployment package

## Deploy to Render
1. Create a private GitHub repository and upload the files in this folder (including Dockerfile and render.yaml).
2. On https://dashboard.render.com select New > Blueprint and connect the repository. Confirm plan and deploy.
3. Render provides an HTTPS address; open it on your phone or desktop.
4. The service needs enough RAM and CPU to encode video; starter tier may need upgrading. gTTS uses external internet access.

## Publishing
Current `Share / Publish` button opens the device's native share sheet for a generated MP4. Select YouTube or Instagram if available, or save MP4 and upload from the respective app. **Direct YouTube/Instagram account posting is not implemented.** That requires platform OAuth, approved API permissions, secure token storage, and account authorization. Never paste OAuth secrets into the web page or commit them to GitHub.

## Security before public deployment
This starter is intended for private testing, not an open public service. `/api/render` is unauthenticated and can consume CPU/bandwidth. Add authentication, per-user quotas, rate limiting, job queue, secure temp cleanup, and persistent storage before exposing it publicly. Also verify the source image's usage rights and product label data before publication.

## Local test
`docker build -t ai-shorts-studio .`
`docker run --rm -p 8000:8000 ai-shorts-studio`
Visit http://localhost:8000
