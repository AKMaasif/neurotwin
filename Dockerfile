# One-container NeuroTwin: the backend serves the built web app. Matches start-imaging.ps1
# (imaging packages installed, imaging enabled for demo-dr-layla, six months of synthetic demo history).
# Provider keys are never baked in: set them as secrets on the host (see deploy/huggingface/DEPLOY.md).

FROM node:22-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY backend/requirements.txt backend/requirements-imaging.txt backend/
RUN pip install -r backend/requirements.txt -r backend/requirements-imaging.txt

COPY --chown=user backend/ backend/
COPY --chown=user --from=web /src/frontend/dist frontend/dist
RUN mkdir -p data backend/imaging_data/native backend/activity_runs \
 && chown -R user data backend/imaging_data/native backend/activity_runs

USER user
# Settings from start-imaging.ps1, plus hosting settings. Anything here can be overridden by the host's variables.
ENV NEUROTWIN_DATABASE_URL=sqlite:////home/user/app/data/neurotwin.db \
    NEUROTWIN_IMAGING_USERS=demo-dr-layla \
    NEUROTWIN_SEED_HISTORY=1 \
    NEUROTWIN_SECURE_COOKIES=1 \
    PORT=7860

WORKDIR /home/user/app/backend
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
