FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY data-gen/requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY data-gen /opt/rtrbench/data-gen
COPY perception/03.srec /opt/rtrbench/perception/03.srec
# Download both inputs during the build; failure or changed data fails the image build.
RUN python /opt/rtrbench/data-gen/download.py --out /inputs
ENV MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /opt/rtrbench
ENTRYPOINT ["python", "/opt/rtrbench/data-gen/prepare.py"]
CMD ["--out", "/output/scene"]
