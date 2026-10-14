# dotnet SDK is required at runtime to compile the trusted C# overlay template.
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder
WORKDIR /src
COPY dotnet/AssemblyWorker/ ./
RUN dotnet publish AssemblyWorker.csproj -c Release -o /opt/assembly-worker --nologo

FROM mcr.microsoft.com/dotnet/sdk:8.0
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY --from=builder /opt/assembly-worker/ /opt/assembly-worker/
COPY satanabe_builder/ ./satanabe_builder/
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 DATA_DIR=/data ASSEMBLY_WORKER=/opt/assembly-worker/AssemblyWorker.dll DOTNET_CLI_TELEMETRY_OPTOUT=1
CMD ["python", "-m", "satanabe_builder.bot"]
