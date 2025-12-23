# AllQuiet to Slack On-Call Sync

This script fetches the current on-call schedule from AllQuiet API and updates Slack user groups (aliases) to reflect who is currently on call for each team.

## Features

- Fetches real-time on-call information from AllQuiet API
- Maps AllQuiet teams to Slack user groups
- Updates Slack user group memberships based on who is currently on call
- Supports custom team name to Slack handle mapping
- Dry-run mode for testing
- Comprehensive logging

## Prerequisites

1. **AllQuiet API Key**: Generate an API key from your AllQuiet account settings
2. **Slack Bot Token**: Create a Slack app with the following scopes:
   - `usergroups:read` - To list user groups
   - `usergroups:write` - To update user group members
   - `users:read` - To look up users by email
   - `users:read.email` - To access user email addresses

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export ALLQUIET_API_KEY="your-allquiet-api-key"
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
export ALLQUIET_BASE_URL="https://allquiet.app"  # Optional, defaults to https://allquiet.app
```

3. (Optional) Create a team mapping configuration file:
```bash
cp team_mapping.example.json team_mapping.json
# Edit team_mapping.json to map your AllQuiet team names to Slack usergroup handles
```

## Usage

### Basic Usage

```bash
python update_oncall_slack.py
```

### With Team Mapping Configuration

```bash
export TEAM_MAPPING_CONFIG="team_mapping.json"
python update_oncall_slack.py
```

### Dry Run Mode (test without making changes)

```bash
export DRY_RUN="true"
python update_oncall_slack.py
```

### As a Cron Job

Add to your crontab to run every 15 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths as needed)
*/15 * * * * cd /path/to/script && /usr/bin/python3 update_oncall_slack.py >> /var/log/oncall-sync.log 2>&1
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALLQUIET_API_KEY` | Yes | - | Your AllQuiet API key |
| `SLACK_BOT_TOKEN` | Yes | - | Your Slack bot token (starts with `xoxb-`) |
| `ALLQUIET_BASE_URL` | No | `https://allquiet.app` | AllQuiet API base URL |
| `TEAM_MAPPING_CONFIG` | No | - | Path to team mapping JSON file |
| `DRY_RUN` | No | `false` | Set to `true` to test without making changes |

### Team Mapping Configuration

The team mapping configuration file (`team_mapping.json`) allows you to explicitly map AllQuiet team names to Slack user group handles:

```json
{
  "team_mapping": {
    "Platform Engineering": "oncall-platform",
    "Backend Team": "oncall-backend",
    "Frontend Team": "oncall-frontend"
  }
}
```

- **Key**: The exact team name as it appears in AllQuiet
- **Value**: The Slack user group handle (without the `@` symbol)

If a team is not in the mapping, the script will attempt to create a handle by converting the team name to lowercase and replacing spaces with hyphens.

## How It Works

1. **Fetch On-Call Data**: The script calls the AllQuiet `/api/public/v1/on-call` endpoint to get current on-call information
2. **Parse Response**: Extracts user emails and team assignments from the API response
3. **Determine Available Users**: Only includes users who are currently online/available in their on-call schedule
4. **Map to Slack**: Converts user emails to Slack user IDs using the Slack API
5. **Update User Groups**: Updates the corresponding Slack user groups with the on-call users

## API Endpoints Used

### AllQuiet API
- `GET /api/public/v1/on-call` - Fetches current on-call schedule

### Slack API
- `GET /api/usergroups.list` - Lists all user groups
- `POST /api/usergroups.users.update` - Updates user group members
- `GET /api/users.lookupByEmail` - Finds Slack user by email

## Troubleshooting

### "No Slack user group found with handle"
Create a Slack user group with the expected handle, or add a mapping in `team_mapping.json`.

### "Could not find Slack user for email"
Ensure the user's email in AllQuiet matches their primary email in Slack. The Slack bot needs `users:read.email` scope.

### "Slack API error: missing_scope"
Ensure your Slack app has all required scopes (see Prerequisites section).

### Script fails with authentication error
- Verify your `ALLQUIET_API_KEY` is correct
- Verify your `SLACK_BOT_TOKEN` starts with `xoxb-` and is valid
- Check that tokens haven't expired

## Example Output

```
2024-12-23 10:00:00 - __main__ - INFO - Starting on-call synchronization
2024-12-23 10:00:01 - __main__ - INFO - Fetching on-call data from AllQuiet API: https://allquiet.app/api/public/v1/on-call
2024-12-23 10:00:02 - __main__ - INFO - Successfully retrieved on-call data for 5 memberships
2024-12-23 10:00:02 - __main__ - INFO - Found on-call users for 2 teams
2024-12-23 10:00:03 - __main__ - INFO - Fetching user groups from Slack
2024-12-23 10:00:04 - __main__ - INFO - Found 8 user groups
2024-12-23 10:00:04 - __main__ - INFO - Team 'Platform Engineering' -> @oncall-platform: 2 users
2024-12-23 10:00:05 - __main__ - INFO - Updating user group UG123456 with 2 users
2024-12-23 10:00:06 - __main__ - INFO - Successfully updated user group UG123456
2024-12-23 10:00:06 - __main__ - INFO - Team 'Backend Team' -> @oncall-backend: 1 users
2024-12-23 10:00:07 - __main__ - INFO - Updating user group UG789012 with 1 users
2024-12-23 10:00:08 - __main__ - INFO - Successfully updated user group UG789012
2024-12-23 10:00:08 - __main__ - INFO - Synchronization complete: {'teams_processed': 2, 'usergroups_updated': 2, 'users_added': 3, 'errors': 0}
2024-12-23 10:00:08 - __main__ - INFO - Synchronization completed successfully
```

## Docker Usage

You can also run this script in a Docker container:

### Build the Docker image

```bash
docker build -t oncall-sync .
```

### Run the container

```bash
docker run --rm \
  -e ALLQUIET_API_KEY="your-api-key" \
  -e SLACK_BOT_TOKEN="xoxb-your-token" \
  oncall-sync
```

### Example Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY update_oncall_slack.py .
COPY team_mapping.json .

ENV TEAM_MAPPING_CONFIG=/app/team_mapping.json

CMD ["python", "update_oncall_slack.py"]
```

## License

MIT License - feel free to modify and use as needed.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
