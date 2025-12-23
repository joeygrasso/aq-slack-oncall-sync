#!/usr/bin/env python3
"""
Script to parse AllQuiet API response and update Slack user group aliases with on-call personnel.

This script fetches the current on-call schedule from AllQuiet API and updates Slack user groups
(aliases) to reflect who is currently on call for each team.

Requirements:
- ALLQUIET_API_KEY: AllQuiet API key (set as environment variable)
- SLACK_BOT_TOKEN: Slack bot token with usergroups:write scope (set as environment variable)
- ALLQUIET_BASE_URL: AllQuiet API base URL (default: https://allquiet.app)
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllQuietClient:
    """Client for interacting with AllQuiet API."""
    
    def __init__(self, api_key: str, base_url: str = "https://allquiet.app"):
        """
        Initialize AllQuiet client.
        
        Args:
            api_key: AllQuiet API key for authentication
            base_url: Base URL for AllQuiet API
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_oncall(self, team_ids: Optional[List[str]] = None, 
                   user_ids: Optional[List[str]] = None,
                   timestamp: Optional[str] = None) -> Dict:
        """
        Fetch current on-call information from AllQuiet.
        
        Args:
            team_ids: Optional list of team IDs to filter
            user_ids: Optional list of user IDs to filter
            timestamp: Optional timestamp to check on-call at specific time
        
        Returns:
            Dictionary containing on-call information
        """
        url = f"{self.base_url}/api/public/v1/on-call"
        
        params = {}
        if team_ids:
            params['TeamIds'] = team_ids
        if user_ids:
            params['UserIds'] = user_ids
        if timestamp:
            params['Timestamp'] = timestamp
        
        try:
            logger.info(f"Fetching on-call data from AllQuiet API: {url}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully retrieved on-call data for {len(data.get('memberships', []))} memberships")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch on-call data: {e}")
            raise


class SlackClient:
    """Client for interacting with Slack API."""
    
    def __init__(self, bot_token: str):
        """
        Initialize Slack client.
        
        Args:
            bot_token: Slack bot token with usergroups:write scope
        """
        self.bot_token = bot_token
        self.base_url = "https://slack.com/api"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {bot_token}',
            'Content-Type': 'application/json'
        })
    
    def list_usergroups(self, include_users: bool = True) -> List[Dict]:
        """
        List all user groups in the Slack workspace.
        
        Args:
            include_users: Whether to include user list in response
        
        Returns:
            List of user group dictionaries
        """
        url = f"{self.base_url}/usergroups.list"
        
        try:
            logger.info("Fetching user groups from Slack")
            response = self.session.get(url, params={'include_users': include_users})
            response.raise_for_status()
            data = response.json()
            
            if not data.get('ok'):
                error = data.get('error', 'Unknown error')
                logger.error(f"Slack API error: {error}")
                raise Exception(f"Slack API error: {error}")
            
            usergroups = data.get('usergroups', [])
            logger.info(f"Found {len(usergroups)} user groups")
            return usergroups
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list user groups: {e}")
            raise
    
    def update_usergroup_members(self, usergroup_id: str, user_ids: List[str]) -> Dict:
        """
        Update members of a Slack user group.
        
        Args:
            usergroup_id: ID of the user group to update
            user_ids: List of Slack user IDs to add to the group
        
        Returns:
            Updated user group information
        """
        url = f"{self.base_url}/usergroups.users.update"
        
        payload = {
            'usergroup': usergroup_id,
            'users': ','.join(user_ids) if user_ids else ''
        }
        
        try:
            logger.info(f"Updating user group {usergroup_id} with {len(user_ids)} users")
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('ok'):
                error = data.get('error', 'Unknown error')
                logger.error(f"Slack API error: {error}")
                raise Exception(f"Slack API error: {error}")
            
            logger.info(f"Successfully updated user group {usergroup_id}")
            return data.get('usergroup', {})
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update user group: {e}")
            raise
    
    def find_user_by_email(self, email: str) -> Optional[str]:
        """
        Find Slack user ID by email address.
        
        Args:
            email: Email address to search for
        
        Returns:
            Slack user ID if found, None otherwise
        """
        url = f"{self.base_url}/users.lookupByEmail"
        
        try:
            response = self.session.get(url, params={'email': email})
            response.raise_for_status()
            data = response.json()
            
            if data.get('ok'):
                user = data.get('user', {})
                user_id = user.get('id')
                logger.debug(f"Found Slack user {user_id} for email {email}")
                return user_id
            else:
                logger.warning(f"Could not find Slack user with email {email}")
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error looking up user by email {email}: {e}")
            return None


class OnCallSyncManager:
    """Manages synchronization between AllQuiet on-call data and Slack user groups."""
    
    def __init__(self, allquiet_client: AllQuietClient, slack_client: SlackClient,
                 team_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize sync manager.
        
        Args:
            allquiet_client: AllQuiet API client
            slack_client: Slack API client
            team_mapping: Optional mapping of AllQuiet team names to Slack usergroup handles
        """
        self.allquiet = allquiet_client
        self.slack = slack_client
        self.team_mapping = team_mapping or {}
    
    def parse_oncall_response(self, oncall_data: Dict) -> Dict[str, List[str]]:
        """
        Parse AllQuiet on-call response and organize by team.
        
        Args:
            oncall_data: Response from AllQuiet on-call API
        
        Returns:
            Dictionary mapping team names to lists of user emails who are on call
        """
        team_oncall = {}
        
        memberships = oncall_data.get('memberships', [])
        
        for membership in memberships:
            user = membership.get('user', {})
            team = membership.get('team', {})
            availabilities = membership.get('availabilities', [])
            
            user_email = user.get('email')
            team_name = team.get('displayName')
            
            if not user_email or not team_name:
                logger.warning(f"Skipping membership with missing user email or team name")
                continue
            
            # Check if user is currently available (online)
            is_available = any(
                avail.get('isOnline', False) 
                for avail in availabilities
            )
            
            if is_available:
                if team_name not in team_oncall:
                    team_oncall[team_name] = []
                team_oncall[team_name].append(user_email)
                logger.debug(f"User {user_email} is on call for team {team_name}")
        
        return team_oncall
    
    def sync_oncall_to_slack(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Synchronize on-call information from AllQuiet to Slack user groups.
        
        Args:
            dry_run: If True, only log what would be done without making changes
        
        Returns:
            Dictionary with statistics about the sync operation
        """
        logger.info("Starting on-call synchronization")
        
        # Fetch on-call data from AllQuiet
        oncall_data = self.allquiet.get_oncall()
        team_oncall = self.parse_oncall_response(oncall_data)
        
        logger.info(f"Found on-call users for {len(team_oncall)} teams")
        
        # Fetch Slack user groups
        usergroups = self.slack.list_usergroups()
        usergroup_map = {ug['handle']: ug['id'] for ug in usergroups}
        
        stats = {
            'teams_processed': 0,
            'usergroups_updated': 0,
            'users_added': 0,
            'errors': 0
        }
        
        # Update each team's Slack user group
        for team_name, user_emails in team_oncall.items():
            stats['teams_processed'] += 1
            
            # Determine Slack usergroup handle
            usergroup_handle = self.team_mapping.get(team_name, team_name.lower().replace(' ', '-'))
            
            if usergroup_handle not in usergroup_map:
                logger.warning(f"No Slack user group found with handle '@{usergroup_handle}' for team '{team_name}'")
                stats['errors'] += 1
                continue
            
            usergroup_id = usergroup_map[usergroup_handle]
            
            # Convert emails to Slack user IDs
            slack_user_ids = []
            for email in user_emails:
                user_id = self.slack.find_user_by_email(email)
                if user_id:
                    slack_user_ids.append(user_id)
                else:
                    logger.warning(f"Could not find Slack user for email {email}")
            
            if not slack_user_ids:
                logger.warning(f"No valid Slack users found for team {team_name}")
                stats['errors'] += 1
                continue
            
            logger.info(f"Team '{team_name}' -> @{usergroup_handle}: {len(slack_user_ids)} users")
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update @{usergroup_handle} with users: {slack_user_ids}")
            else:
                try:
                    self.slack.update_usergroup_members(usergroup_id, slack_user_ids)
                    stats['usergroups_updated'] += 1
                    stats['users_added'] += len(slack_user_ids)
                except Exception as e:
                    logger.error(f"Failed to update user group @{usergroup_handle}: {e}")
                    stats['errors'] += 1
        
        logger.info(f"Synchronization complete: {stats}")
        return stats


def load_team_mapping(config_file: Optional[str] = None) -> Dict[str, str]:
    """
    Load team mapping from configuration file.
    
    Args:
        config_file: Path to JSON configuration file
    
    Returns:
        Dictionary mapping AllQuiet team names to Slack usergroup handles
    """
    if not config_file or not os.path.exists(config_file):
        logger.info("No team mapping configuration file provided or file not found")
        return {}
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            mapping = config.get('team_mapping', {})
            logger.info(f"Loaded team mapping for {len(mapping)} teams")
            return mapping
    except Exception as e:
        logger.error(f"Failed to load team mapping: {e}")
        return {}


def main():
    """Main entry point for the script."""
    # Load configuration from environment variables
    allquiet_api_key = os.getenv('ALLQUIET_API_KEY')
    allquiet_base_url = os.getenv('ALLQUIET_BASE_URL', 'https://allquiet.app')
    slack_bot_token = os.getenv('SLACK_BOT_TOKEN')
    config_file = os.getenv('TEAM_MAPPING_CONFIG')
    dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    # Validate required environment variables
    if not allquiet_api_key:
        logger.error("ALLQUIET_API_KEY environment variable is required")
        sys.exit(1)
    
    if not slack_bot_token:
        logger.error("SLACK_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    # Initialize clients
    allquiet_client = AllQuietClient(allquiet_api_key, allquiet_base_url)
    slack_client = SlackClient(slack_bot_token)
    
    # Load team mapping
    team_mapping = load_team_mapping(config_file)
    
    # Create sync manager and run synchronization
    sync_manager = OnCallSyncManager(allquiet_client, slack_client, team_mapping)
    
    try:
        stats = sync_manager.sync_oncall_to_slack(dry_run=dry_run)
        
        if stats['errors'] > 0:
            logger.warning(f"Completed with {stats['errors']} errors")
            sys.exit(1)
        else:
            logger.info("Synchronization completed successfully")
            sys.exit(0)
    except Exception as e:
        logger.error(f"Synchronization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
