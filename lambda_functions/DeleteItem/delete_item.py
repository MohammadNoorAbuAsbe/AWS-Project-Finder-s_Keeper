"""
Lambda Function: Delete Item
Allows authenticated users to delete their own items
Admin users can delete any item

INTERFACE DOCUMENTATION:
=======================

Endpoint: DELETE /items/id?id={itemId}
Method: DELETE
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Query String Parameters:
  - id (string, required): The unique identifier (UUID) of the item to delete
    Format: UUID v4 (e.g., "123e4567-e89b-12d3-a456-426614174000")

Request Headers:
  - Authorization (string, required): Cognito JWT token
    Format: Bearer token from Cognito authentication

Request Body: None

AUTHORIZATION RULES:
--------------------
  - Regular users: Can only delete items they created (userId match required)
  - Admin users: Can delete any item (Admins group membership)

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "success": true,
  "message": "Item deleted successfully"
}

Error Responses:
  - 400 Bad Request:
    {"error": "Missing required parameter: id"}
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 403 Forbidden:
    {"error": "Forbidden: You can only delete your own items"}
  
  - 404 Not Found:
    {"error": "Item not found"}
  
  - 500 Internal Server Error:
    {"error": "Database error: [error message]"}

AWS Academy Learner Lab Pattern:
- API Gateway handles CORS and status codes (no manual headers)
- Returns clean JSON-serializable objects
- Uses botocore.exceptions.ClientError for error handling
"""

import json
import boto3
from botocore.exceptions import ClientError
import os

dynamodb_resource = boto3.resource('dynamodb')
lost_and_found_items_table_name = os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items')
lost_and_found_items_table = dynamodb_resource.Table(lost_and_found_items_table_name)

def delete_lost_or_found_item_with_ownership_validation(api_gateway_event, lambda_context):
    """
    DELETE /items/{itemId}
    
    Path Parameters:
    - itemId: The ID of the item to delete
    
    AWS Academy Pattern:
    - Requires Cognito authentication (handled by API Gateway)
    - Returns clean JSON object (API Gateway wraps with statusCode)
    - No manual CORS headers (API Gateway handles)
    - Users can only delete their own items unless they are admin
    """
    
    try:
        item_id_to_delete = api_gateway_event.get('queryStringParameters', {}).get('id')
        
        if not item_id_to_delete:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameter: id'})
            }
        
        cognito_user_claims = api_gateway_event['requestContext']['authorizer']['claims']
        authenticated_user_unique_id = cognito_user_claims['sub']
        authenticated_user_email_address = cognito_user_claims['email']
        
        cognito_user_group_memberships = cognito_user_claims.get('cognito:groups', '')
        if isinstance(cognito_user_group_memberships, str):
            cognito_user_group_memberships = cognito_user_group_memberships.split(',') if cognito_user_group_memberships else []
        user_has_admin_privileges = 'Admins' in cognito_user_group_memberships
        
        dynamodb_get_response = lost_and_found_items_table.get_item(Key={'id': item_id_to_delete})
        
        if 'Item' not in dynamodb_get_response:
            raise ValueError('Item not found')
        
        existing_item_record = dynamodb_get_response['Item']
        
        if existing_item_record.get('userId') != authenticated_user_unique_id and not user_has_admin_privileges:
            raise ValueError('Forbidden: You can only delete your own items')
        
        lost_and_found_items_table.delete_item(Key={'id': item_id_to_delete})
        
        return {
            'success': True,
            'message': 'Item deleted successfully'
        }
        
    except ValueError as validation_or_permission_error:
        print(f"Validation error: {str(validation_or_permission_error)}")
        raise Exception(str(validation_or_permission_error))
        
    except KeyError as missing_required_field_error:
        print(f"Missing required field: {str(missing_required_field_error)}")
        raise Exception("Unauthorized: Valid authentication required")
        
    except ClientError as aws_dynamodb_error:
        error_code_from_dynamodb = aws_dynamodb_error.response['Error']['Code']
        error_message_from_dynamodb = aws_dynamodb_error.response['Error']['Message']
        print(f"DynamoDB Error [{error_code_from_dynamodb}]: {error_message_from_dynamodb}")
        raise Exception(f"Database error: {error_message_from_dynamodb}")
        
    except Exception as unexpected_exception:
        print(f"Unexpected error: {str(unexpected_exception)}")
        raise Exception(f"Internal server error: {str(unexpected_exception)}")

lambda_handler = delete_lost_or_found_item_with_ownership_validation
