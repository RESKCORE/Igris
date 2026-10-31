# Welcome to your Lovable project

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Open your project in the [Lovable editor](https://lovable.dev) and keep building.

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: connect the project to GitHub and every change made in Lovable is committed straight to your repository.
- **Full ownership**: this code is yours. Push to your repository and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## Backend integration (SQL API)

The dashboard talks to the FastAPI backend in `../backend` (SQLAlchemy + SQLite by default).

```sh
# From the repo root — starts BOTH servers (backend :8000 + frontend :8080)
python run_all.py
```

or run them in separate terminals:

```sh
# Terminal 1 — backend (SQL database, seeds demo data on startup)
cd ../backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cp .env.example .env.local   # sets VITE_API_URL=http://localhost:8000
npm run dev
```

- Without `VITE_API_URL` the app runs fully in-browser against the built-in demo mock (used by the vitest suite).
- With it, every screen — Data, Plan, Exceptions, Outbox, Audit — reads and writes through the backend's SQL tables.
- Backend docs: http://localhost:8000/docs · Health: http://localhost:8000/health

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS
