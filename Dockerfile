FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY .streamlit ./.streamlit

# the parquet cache is written at runtime; a volume keeps it across restarts
RUN mkdir -p data/cache && useradd -u 10001 -m app && chown -R app /app
USER app

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health',timeout=4).status==200 else 1)"

# keys come from the environment at run time, never baked into the image
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
