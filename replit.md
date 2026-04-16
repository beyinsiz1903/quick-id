# Quick ID Reader - Hotel Guest Management System

## Overview
A professional hotel reception and guest management system for automating identity document scanning and processing using AI (OpenAI GPT-4o Vision). Supports Turkish ID types, KVKK compliance, multi-property management, and more.

## Architecture

### Backend (FastAPI + Python)
- **Entry point**: `backend/server.py`
- **Port**: 8000 (localhost)
- **Database**: MongoDB (local instance via `mongod`)
- **Startup script**: `start_backend.sh` (starts MongoDB, then the FastAPI server)

### Frontend (React + CRACO + Tailwind CSS)
- **Entry point**: `frontend/src/index.js`
- **Port**: 5000 (0.0.0.0)
- **Build tool**: CRACO (Create React App Configuration Override)
- **API proxy**: Requests to `/api/*` are proxied to `http://localhost:8000`

## Workflows
- **Start application**: Runs the React frontend dev server on port 5000
- **Backend API**: Starts MongoDB and the FastAPI backend on port 8000

## Key Configuration Files
- `frontend/.env`: Frontend environment (PORT=5000, HOST=0.0.0.0, proxy to backend)
- `frontend/craco.config.js`: Webpack/dev server config (allowedHosts: "all" for Replit proxy)
- `backend/server.py`: Main API server with CORS, auth, MongoDB configuration

## Environment Variables Needed
- `OPENAI_API_KEY`: For GPT-4o Vision ID scanning
- `MONGO_URL`: MongoDB connection (defaults to `mongodb://localhost:27017`)
- `JWT_SECRET`: Secret for JWT token signing
- `CORS_ORIGINS`: Comma-separated allowed origins (defaults to localhost + Replit domain)

## Default Credentials
- Admin: `admin@quickid.com` / `admin123`
- Receptionist: `resepsiyon@quickid.com` / `resepsiyon123`

## Key Features
- AI-powered ID document scanning (Turkish and international)
- Guest check-in/check-out management
- KVKK (Turkish Data Protection Law) compliance
- Multi-property support
- Biometric face matching
- TC Kimlik validation
- Offline/kiosk mode support
- PDF report generation
- Audit trail

## Dependency Notes
- `emergentintegrations` package is used for AI scanning but is not on PyPI - AI scanning will use the OpenAI SDK directly as fallback
- The frontend has complex ajv versioning requirements - some packages need ajv@6, others ajv@8. Manually patched nested `node_modules` structure to resolve conflicts.
- MongoDB is installed via Nix and started locally via `start_backend.sh`
