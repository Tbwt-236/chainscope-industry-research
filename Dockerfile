FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY backend ./backend
COPY data ./data
COPY dist ./dist
RUN useradd -m researcher && mkdir runtime && chown researcher runtime
USER researcher
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
