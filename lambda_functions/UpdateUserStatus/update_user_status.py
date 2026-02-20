"""
AWS Lambda Function: Update User Status (Block/Unblock)
Purpose: Enable/disable Cognito users via admin operations
Method: Invoked by API Gateway PATCH /users/{username}
Response: Clean JSON (no statusCode or headers - API Gateway handles that)

INTERFACE DOCUMENTATION:
=======================

Endpoint: PATCH /users/{username}
Method: PATCH
Authentication: Required (Cognito User Pool - Admin only)

INPUT PARAMETERS:
-----------------
Path Parameters:
  - username (string, required): The Cognito username (typically email)
    Format: Email address or Cognito username
    Example: /users/user@example.com

Request Headers:
  - Authorization (string, required): Cognito JWT token (Admin user)
  - Content-Type: application/json

Request Body (JSON):
{
  "action": "block" | "unblock" (required)
}

Field Descriptions:
  - action: "block" to disable user account, "unblock" to enable

API Gateway Mapping:
  The API Gateway uses a mapping template to transform the request:
  {
    "username": "$input.params('username')",
    "action": "$input.path('$.action')"
  }

Authorization Requirements:
  - Caller must be member of 'Admins' group in Cognito User Pool

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "status": "success",
  "username": "user@example.com",
  "action": "block" | "unblock",
  "message": "User user@example.com has been blocked successfully"
}

Error Responses:
  - 400 Bad Request:
    {
      "status": "error",
      "message": "Username is required"
    }
    OR
    {
      "status": "error",
      "message": "Action must be 'block' or 'unblock'"
    }
  
  - 404 Not Found:
    {
      "status": "error",
      "message": "User user@example.com not found"
    }
  
  - 403 Forbidden:
    {
      "status": "error",
      "message": "Not authorized to perform this operation"
    }
  
  - 500 Internal Server Error:
    {
      "status": "error",
      "message": "Cognito error: [error message]"
    }

EXAMPLE REQUESTS:
-----------------
Block a user:
PATCH /users/user@example.com
Authorization: Bearer eyJhbGc... (Admin token)
Content-Type: application/json

{
  "action": "block"
}

Unblock a user:
PATCH /users/user@example.com
Authorization: Bearer eyJhbGc... (Admin token)
Content-Type: application/json

{
  "action": "unblock"
}

BEHAVIOR:
---------
  - Block: Calls admin_disable_user (user cannot sign in)
  - Unblock: Calls admin_enable_user (user can sign in again)
  - Does not delete user account or data
  - User's items remain in database
  - Admin only operation
"""

import json
import boto3
import os
from botocore.exceptions import ClientError

cognito_identity_provider_client = boto3.client('cognito-idp')
cognito_user_pool_identifier = os.environ.get('USER_POOL_ID')


def block_or_unblock_cognito_user_account(api_gateway_event, lambda_context):
    """
    Handle user status updates (block/unblock)
    
    Expected event structure from API Gateway mapping template:
    {
        "username": "user@example.com",
        "action": "block" or "unblock"
    }
    """
    
    try:
        print(f"Received event: {json.dumps(api_gateway_event)}")
        
        target_username_to_modify = api_gateway_event.get('username')
        requested_account_action = api_gateway_event.get('action', '').lower()
        
        if not target_username_to_modify:
            return {
                "status": "error",
                "message": "Username is required"
            }
        
        if requested_account_action not in ['block', 'unblock']:
            return {
                "status": "error",
                "message": "Action must be 'block' or 'unblock'"
            }
        
        if requested_account_action == 'block':
            cognito_identity_provider_client.admin_disable_user(
                UserPoolId=cognito_user_pool_identifier,
                Username=target_username_to_modify
            )
            operation_success_message = f"User {target_username_to_modify} has been blocked successfully"
            
        else:
            cognito_identity_provider_client.admin_enable_user(
                UserPoolId=cognito_user_pool_identifier,
                Username=target_username_to_modify
            )
            operation_success_message = f"User {target_username_to_modify} has been unblocked successfully"
        
        print(f"✅ {operation_success_message}")
        
        return {
            "status": "success",
            "username": target_username_to_modify,
            "action": requested_account_action,
            "message": operation_success_message
        }
        
    except ClientError as cognito_service_error:
        cognito_error_code = cognito_service_error.response['Error']['Code']
        cognito_error_message = cognito_service_error.response['Error']['Message']
        
        print(f"Cognito error: {cognito_error_code} - {cognito_error_message}")
        
        if cognito_error_code == 'UserNotFoundException':
            return {
                "status": "error",
                "message": f"User {target_username_to_modify} not found"
            }
        elif cognito_error_code == 'NotAuthorizedException':
            return {
                "status": "error",
                "message": "Not authorized to perform this operation"
            }
        else:
            return {
                "status": "error",
                "message": f"Cognito error: {cognito_error_message}"
            }
    
    except Exception as unexpected_exception:
        print(f"Unexpected error: {str(unexpected_exception)}")
        return {
            "status": "error",
            "message": f"Internal error: {str(unexpected_exception)}"
        }

lambda_handler = block_or_unblock_cognito_user_account
