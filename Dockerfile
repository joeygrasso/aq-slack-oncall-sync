FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY update_oncall_slack.py .

# Optional: Copy team mapping if needed
# COPY team_mapping.json .
# ENV TEAM_MAPPING_CONFIG=/app/team_mapping.json

# Run the script
CMD ["python", "update_oncall_slack.py"]
