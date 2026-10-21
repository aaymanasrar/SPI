# The craft engines service.
#
# LibreOffice is in the image because word.to_pdf shells out to it (MPL-2.0,
# separate process, which is the condition the licence policy attaches to MPL).
# Without it that one tool refuses with a message naming the program; everything
# else works.
#
# Note on scope: scripts/check-licenses covers the Python and npm trees. It does
# not inspect apt packages, so the two licence notes below are by inspection,
# not by the gate.

FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/engines

# libreoffice-writer      MPL-2.0, run as a separate process
# fonts-crosextra-carlito SIL OFL 1.1 — metric-compatible with Calibri, which is
#                         what craft/word/style.py asks for. Without it
#                         LibreOffice substitutes a font with different metrics
#                         and every generated PDF reflows.
# fonts-liberation        SIL OFL 1.1 — Arial/Times/Courier metric equivalents,
#                         for templates supplied by SmartPage later.
# --no-install-recommends keeps the java stack and the whole desktop out.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui \
      fonts-crosextra-carlito \
      fonts-liberation \
 && fc-cache -f \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 engines

WORKDIR /app
COPY pyproject.toml ./
COPY craft ./craft
RUN pip install --no-cache-dir .

USER engines

# soffice writes a profile on first run. word.to_pdf points it at a per-call
# temp directory, but set this so nothing lands in /.
ENV SOFFICE_PATH=/usr/bin/soffice \
    XDG_CONFIG_HOME=/home/engines/.config \
    XDG_CACHE_HOME=/home/engines/.cache

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["uvicorn", "craft.api:app", "--host", "0.0.0.0", "--port", "8000"]
