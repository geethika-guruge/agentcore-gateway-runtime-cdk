# ARM64 base image required for AgentCore Runtime
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mcp_server.py .
COPY __init__.py .

# Expose port 8000 for MCP server (AgentCore standard)
EXPOSE 8000

# Run the MCP server
CMD ["python", "mcp_server.py"]
