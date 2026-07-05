# Aetheris X Creative Studio - Technical Documentation

Welcome to the official developer manual for the **Aetheris X Creative Studio** (formerly Google Cloud Creative Studio). This manual covers the core architecture, installation steps, Web3 integration protocols, and edge agent APIs.

---

## 1. Project Overview & Architecture
Aetheris X Creative Studio is a state-of-the-art multimedia generative suite. It consists of:
*   **Frontend**: Angular 18 Single Page Application styled with custom dark glassmorphic elements and Outfit typography. Deployed via GitHub Actions to `https://aetherisx.studio`.
*   **Backend**: FastAPI Python application serving rest APIs, managing queues, database migrations (Alembic/PostgreSQL), and orchestration workflows.
*   **Generative AI Models**: Connected to Google Cloud Vertex AI (Imagen for images, Veo for video, Gemini for text generation and prompt enhancement).
*   **Web3 Engine**: Multi-chain support for asset tokenization (Base Mainnet and Flow Blockchain).

---

## 2. Local Development Setup
For local development, we run the services using Docker Compose.

### Prerequisites
*   **Docker & Docker Compose**
*   **Google Cloud SDK (`gcloud`)** authenticated with `gcloud auth application-default login`
*   **Node.js v20+** and **uv** (for fast Python dependency resolution)

### Quick Start
1.  **Configure environment files**:
    *   Create `backend/.env` (use PostgreSQL connection: `DB_HOST=postgres`, `DB_PORT=5432`).
    *   Create `frontend/src/environments/development.environment.ts` with your Firebase credentials.
2.  **Start the application**:
    ```bash
    docker-compose up --build
    ```
    *   **Frontend**: `http://localhost:4200`
    *   **Backend REST API**: `http://localhost:8080`
    *   **Swagger API Docs**: `http://localhost:8080/docs`

---

## 3. User Authentication & Security
*   **Firebase Authentication**: Authenticates users via Google SSO.
*   **reCAPTCHA Enterprise**: Client-side bot defense configuration.
    *   **Site Key**: `6LeRPkAtAAAAAKnaiVVAsifsZcq2mSi6Zi_yKlLe`
    *   **Integration**: Loaded in `index.html` and triggered via `grecaptcha.enterprise.execute` during the sign-in action (`action: 'LOGIN'`).

---

## 4. Multi-Chain Web3 NFT Tokenization
The Web3 engine permits tokenizing generated image/video files directly into NFTs.

### A. Base Mainnet Integration (Ethereum L2)
*   **LEV Token Address**: `0xf61771F3C6c2a59C8C99f7f2Fd04684b7182E340`
*   **Mint Protocol**:
    1.  The asset file (from Google Cloud Storage) is pinned to IPFS using the Pinata API.
    2.  An ERC-721 compliant metadata JSON is created, pointing to the IPFS media CID.
    3.  The metadata JSON is pinned to IPFS to obtain the Token URI CID.
    4.  The frontend invokes a wallet contract transaction to mint the NFT using the LEV token.

### B. Flow Blockchain Integration (Cadence)
*   **Smart Contract**: Uses Cadence NFT standard templates (`CreativeStudioNFT.cdc`).
*   **Frontend Wallet Connection**: Handled by the Flow Client Library (FCL).
*   **Resource-Oriented Model**: NonFungibleToken resources are stored directly within the user's account storage path `/storage/CreativeStudioNFTCollection`.

---

## 5. Edge Agent APIs (Aetheris Hub)
Exposes endpoint workflows to external agent networks like `aetherisx.stream`.
*   **Execution Route**: `POST /api/agent/run-workflow`
*   **Trigger Protocol**: Agents provide signature verification headers and trigger customized generation recipes.
*   **Webhooks**: Backend posts the finished generative media (GCS/IPFS links) back to the registered webhook URL upon completion.
