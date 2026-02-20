"""
AWS Lambda Function: List Cognito Users
Retrieves all users from Cognito User Pool (Admin only)

INTERFACE DOCUMENTATION:
=======================

Endpoint: GET /users
Method: GET
Authentication: Required (Cognito User Pool - Admin only)

INPUT PARAMETERS:
-----------------
Query String Parameters: None
Request Headers:
  - Authorization (string, required): Cognito JWT token
    Format: Bearer token from Cognito authentication
Request Body: None

Authorization Requirements:
  - User must be member of 'Admins' group in Cognito User Pool

RESPONSE FORMAT:
----------------
Success Response (200):
[
  {
    "username": "user@example.com",
    "email": "user@example.com",
    "name": "User Full Name",
    "created": "2026-01-15T08:45:00.000Z",
    "status": "CONFIRMED" | "FORCE_CHANGE_PASSWORD" | "RESET_REQUIRED",
    "enabled": true | false,
    "emailVerified": true | false,
    "groups": ["Users", "Admins"]
  }
]

Field Descriptions:
  - username: User's Cognito username (typically email)
  - email: User's verified email address
  - name: User's display name
  - created: ISO 8601 timestamp of account creation
  - status: Account status in Cognito
  - enabled: Whether account is active (false if blocked)
  - emailVerified: Whether email has been verified
  - groups: Array of Cognito group names user belongs to

Error Responses:
  - 403 Forbidden:
    {"error": "Admin privileges required"}
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 500 Internal Server Error:
    {"error": "[error message]"}

PAGINATION:
-----------
  - Automatically handles pagination for large user pools
  - Returns all users in a single response
  - Max 60 users per Cognito API call (handled internally)

API Gateway Integration:
- Method: GET /users
- Authorization: Cognito User Pool Authorizer
- CORS: Enabled

Returns:
- 200: Array of user objects
- 403: User is not admin
"""

import json
import boto3
import os
from datetime import datetime

cognito_identity_provider_client = boto3.client('cognito-idp')
cognito_user_pool_identifier = os.environ.get('USER_POOL_ID', 'us-east-1_kfNTDWsQD')

def retrieve_all_cognito_users_for_admin_panel(api_gateway_event, lambda_context):
    """
    GET /users
    
    List all users from Cognito User Pool (Admin only).
    Returns: Clean JSON list (API Gateway handles response wrapping).
    """
    
    try:
        print(f"Event: {json.dumps(api_gateway_event)}")
        
        cognito_user_claims_from_authorizer = {}
        if 'requestContext' in api_gateway_event and 'authorizer' in api_gateway_event['requestContext']:
            cognito_user_claims_from_authorizer = api_gateway_event['requestContext'].get('authorizer', {}).get('claims', {})
        
        authenticated_user_group_memberships = cognito_user_claims_from_authorizer.get('cognito:groups', '')
        
        if isinstance(authenticated_user_group_memberships, str):
            authenticated_user_group_memberships = authenticated_user_group_memberships.split(',') if authenticated_user_group_memberships else []
        current_user_has_admin_role = 'Admins' in authenticated_user_group_memberships
        
        if not current_user_has_admin_role:
            raise Exception('Admin privileges required')
        
        all_cognito_users_list = []
        cognito_pagination_token = None
        
        while True:
            cognito_list_users_parameters = {
                'UserPoolId': cognito_user_pool_identifier,
                'Limit': 60
            }
            
            if cognito_pagination_token:
                cognito_list_users_parameters['PaginationToken'] = cognito_pagination_token
            
            cognito_list_users_response = cognito_identity_provider_client.list_users(**cognito_list_users_parameters)
            
            for user_record_from_cognito in cognito_list_users_response.get('Users', []):
                formatted_user_data = {
                    'username': user_record_from_cognito['Username'],
                    'created': user_record_from_cognito['UserCreateDate'].isoformat(),
                    'status': user_record_from_cognito['UserStatus'],
                    'enabled': user_record_from_cognito['Enabled']
                }
                
                for user_attribute in user_record_from_cognito.get('Attributes', []):
                    if user_attribute['Name'] == 'email':
                        formatted_user_data['email'] = user_attribute['Value']
                    elif user_attribute['Name'] == 'name':
                        formatted_user_data['name'] = user_attribute['Value']
                    elif user_attribute['Name'] == 'email_verified':
                        formatted_user_data['emailVerified'] = user_attribute['Value'] == 'true'
                
                # Get user groups
                try:
                    groups_response = cognito_identity_provider_client.admin_list_groups_for_user(
                        UserPoolId=cognito_user_pool_identifier,
                        Username=user_record_from_cognito['Username']
                    )
                    user_groups = [group['GroupName'] for group in groups_response.get('Groups', [])]
                    formatted_user_data['groups'] = user_groups
                except Exception as group_error:
                    print(f"Could not get groups for user {user_record_from_cognito['Username']}: {group_error}")
                    formatted_user_data['groups'] = []
                
                all_cognito_users_list.append(formatted_user_data)
            
            cognito_pagination_token = cognito_list_users_response.get('PaginationToken')
            if not cognito_pagination_token:
                break
        
        print(f"✅ Retrieved {len(all_cognito_users_list)} users")
        
        return all_cognito_users_list
        
    except Exception as error_during_user_retrieval:
        print(f"Error: {str(error_during_user_retrieval)}")
        raise

lambda_handler = retrieve_all_cognito_users_for_admin_panel
