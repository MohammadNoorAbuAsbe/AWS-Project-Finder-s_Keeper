"""
Lambda Function: Update Item Status
Allows authenticated users to mark their items as resolved

INTERFACE DOCUMENTATION:
=======================

Endpoint: PATCH /items/id?id={itemId}
Method: PATCH
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Query String Parameters:
  - id (string, required): The unique identifier (UUID) of the item to update
    Format: UUID v4 (e.g., "123e4567-e89b-12d3-a456-426614174000")

Request Headers:
  - Authorization (string, required): Cognito JWT token
  - Content-Type: application/json

Request Body (JSON):
{
  "resolved": boolean (required)
}

Field Descriptions:
  - resolved: true to mark item as resolved/found, false to mark as active

Authorization Rules:
  - Users can only update their own items (userId match required)

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "success": true,
  "message": "Item updated successfully",
  "item": {
    "id": "uuid-string",
    "resolved": true | false
  }
}

Error Responses:
  - 400 Bad Request:
    {"error": "Missing required parameter: id"}
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 403 Forbidden:
    {"error": "Forbidden: You can only update your own items"}
  
  - 404 Not Found:
    {"error": "Item not found"}
  
  - 500 Internal Server Error:
    {"error": "Database error: [error message]"}

EXAMPLE REQUEST:
----------------
PATCH /items/id?id=123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "resolved": true
}

BEHAVIOR:
---------
  - Validates item ownership (userId must match)
  - Updates item's resolved status
  - Sets resolvedAt timestamp when marking as resolved
  - Clears resolvedAt timestamp when marking as active
  - Item remains in database (not deleted)

AWS Academy Learner Lab Pattern:
- API Gateway handles CORS and status codes (no manual headers)
- Returns clean JSON-serializable objects
- Uses botocore.exceptions.ClientError for error handling
"""

import json
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime

dynamodb_resource = boto3.resource('dynamodb')
lost_and_found_items_table_name = os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items')
lost_and_found_items_table = dynamodb_resource.Table(lost_and_found_items_table_name)

def mark_item_as_resolved_or_active_with_ownership_check(api_gateway_event, lambda_context):
    """
    PATCH /items/{itemId}
    
    Path Parameters:
    - itemId: The ID of the item to update
    
    Body:
    - resolved: boolean (mark as resolved/active)
    
    AWS Academy Pattern:
    - Requires Cognito authentication (handled by API Gateway)
    - Returns clean JSON object (API Gateway wraps with statusCode)
    - No manual CORS headers (API Gateway handles)
    - Users can only update their own items
    """
    
    try:
        item_id_to_update = api_gateway_event.get('queryStringParameters', {}).get('id')
        
        if not item_id_to_update:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameter: id'})
            }
        
        cognito_user_claims = api_gateway_event['requestContext']['authorizer']['claims']
        authenticated_user_unique_id = cognito_user_claims['sub']
        
        request_body_data = api_gateway_event.get('body', {})
        if isinstance(request_body_data, str):
            request_body_data = json.loads(request_body_data)
        item_resolved_status_boolean = request_body_data.get('resolved', False)
        
        dynamodb_get_item_response = lost_and_found_items_table.get_item(Key={'id': item_id_to_update})
        
        if 'Item' not in dynamodb_get_item_response:
            raise ValueError('Item not found')
        
        existing_item_record = dynamodb_get_item_response['Item']
        
        if existing_item_record.get('userId') != authenticated_user_unique_id:
            raise ValueError('Forbidden: You can only update your own items')
        
        dynamodb_update_item_response = lost_and_found_items_table.update_item(
            Key={'id': item_id_to_update},
            UpdateExpression='SET resolved = :resolved, resolvedAt = :resolvedAt',
            ExpressionAttributeValues={
                ':resolved': item_resolved_status_boolean,
                ':resolvedAt': datetime.utcnow().isoformat() if item_resolved_status_boolean else None
            },
            ReturnValues='ALL_NEW'
        )
        
        return {
            'success': True,
            'message': 'Item updated successfully',
            'item': {
                'id': item_id_to_update,
                'resolved': item_resolved_status_boolean
            }
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

lambda_handler = mark_item_as_resolved_or_active_with_ownership_check
