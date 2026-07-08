# Aetheris X Studio (NICOLE Hub) — Project Knowledge & Memory File

This file serves as a memory and knowledge source for **Jules** (and other AI agents) collaborating on the **Aetheris X Creative Studio** repository.

---

## 1. Project Overview & Identity
* **Name**: Aetheris X Creative Studio (evolutionary target: **NICOLE Agentic Hub**)
* **Company**: ANW Foundations (Owner: Ashleigh Walker, `ashleighwalker@anwfoundations.com`)
* **Primary URL**: [https://aetherisx.studio](https://aetherisx.studio) (central hub for sovereign intelligence and agentic cloud experiments)
* **Associated Domains**:
  * Central Agentic Hub: `aetherisx.stream` (spaceship.com)
  * Edge Protocols: `levityprotocol.cloud` (spaceship.com)

---

## 2. Core Architecture
The project is a premium generative AI media studio with:
1. **Frontend**: Angular 18 Single Page Application.
   * *Styles*: Tailwind CSS + custom SCSS theme in `styles.scss` (Dark Glassmorphic design).
   * *Fonts*: Outfit & Inter.
   * *Custom Assets*: Transparent `aetherisX-logo.png` blending with a custom glowing filter on top of the `google-deepmind-veo3.mp4` login video.
2. **Backend**: FastAPI (Python 3.11+).
   * *Database*: PostgreSQL 15, managed on Cloud SQL under standard instance `creative-studio-db` (`db-f1-micro` tier) in `us-central1`. Configured database: `creative_studio`, user: `studio_user`.
   * *Migrations*: Alembic.
   * *AI Integrations*: Vertex AI SDK (Imagen for image, Veo for video, Gemini for prompt analysis & expansion).
3. **Smart Contracts**: Multi-chain NFT tokenization engine:
   * *Flow Blockchain*: Resource-oriented NFT contract in `cadence/CreativeStudioNFT.cdc` (Cadence 1.0).
   * *Base Mainnet*: EVM solidity contract in `contracts/CreativeStudioNFT.sol`.

---

## 3. Web3 & Token Integration
* **LEV Token (Base Mainnet)**: `0xf61771F3C6c2a59C8C99f7f2Fd04684b7182E340` (100M total supply).
* **Creator Smart Wallet**: `0x81631e082767e0F545386420cCB1128b98C70F60`.
* **Liquidity Pool (LEV/USDC)**: `0x498581ff718922c3f8e6a244956af099b2652b2b` (Base network).
* **ENS**: `levity.base.eth`.
* **Bitcoin**: `bc1qfm5qs5hyd0u2u6kpvm25u0u6nncau02xt8pa7z`.
* **Ethereum**: `0x52De261665e8D1b488F76eec8742B592D9b292D8`.

---

## 4. Key Workflows & Scripts

### Local Development
* **Frontend**: Run `npm start` in `frontend/` (served at `http://localhost:4200`).
* **Backend**: Run local environment inside `backend/` using uv/virtualenv (`uv run uvicorn src.main:app --reload`).

### Deployment
* **Google Cloud Run (Backend)**:
  * Handled by the script [deploy_cloud_run.ps1](file:///C:/Users/Ashle/Documents/GitHub/gcc-creative-studio/deploy_cloud_run.ps1).
  * Project: `gentle-scene-485705-n4`.
* **GitHub Pages (Frontend)**:
  * Automated by GitHub Actions `.github/workflows/deploy.yml` upon push to the `main` branch.
  * Targets the `gh-pages` branch, served via the custom domain `aetherisx.studio` configured with a `CNAME` file and `.nojekyll` configuration.
