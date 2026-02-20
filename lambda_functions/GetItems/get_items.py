"""
Lambda Function: Get Recent Items
Retrieves the most recent 25 lost/found items from DynamoDB
Supports filtering and pagination

INTERFACE DOCUMENTATION:
=======================

Endpoint: GET /items
Method: GET
Authentication: Not required (public endpoint)

INPUT PARAMETERS:
-----------------
Query String Parameters (all optional):
  - limit (integer, optional): Number of items to return
    Format: Integer between 1 and 50
    Default: 25
    Example: ?limit=10
  
  - status (string, optional): Filter by item status
    Format: "lost" or "found"
    Example: ?status=lost
  
  - category (string, optional): Filter by category
    Format: String (e.g., "Pets", "Electronics", "Documents")
    Example: ?category=Electronics
  
  - lastKey (string, optional): Pagination token for next page
    Format: JSON-encoded DynamoDB LastEvaluatedKey
    Example: ?lastKey={"id":"abc123"}

Request Headers: None required
Request Body: None

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "items": [
    {
      "id": "uuid-string",
      "title": "Item title",
      "status": "lost" | "found",
      "category": "Category name",
      "location": "Location description",
      "date": "YYYY-MM-DD",
      "description": "Item description",
      "img": "https://bucket.s3.amazonaws.com/image.jpg",
      "color": "Color (optional)",
      "userId": "cognito-user-id",
      "userEmail": "user@example.com",
      "userName": "User Name",
      "createdAt": "2026-01-22T10:30:00.000Z",
      "updatedAt": "2026-01-22T10:30:00.000Z"
    }
  ],
  "count": 10,
  "lastKey": "pagination-token" (optional, only if more results available)
}

Error Response (500):
{"error": "Database error: [error message]"}

USAGE EXAMPLES:
---------------
  - Get latest 25 items: GET /items
  - Get 10 lost items: GET /items?limit=10&status=lost
  - Filter by category: GET /items?category=Electronics
  - Next page: GET /items?lastKey={...}

AWS Academy Learner Lab Pattern:
- API Gateway handles CORS and status codes (no manual headers)
- Returns clean JSON-serializable objects
- Uses botocore.exceptions.ClientError for error handling
"""

import json
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import os
from datetime import datetime

dynamodb_resource = boto3.resource('dynamodb')
items_table_name = os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items')
lost_and_found_items_table = dynamodb_resource.Table(items_table_name)

class DynamoDBDecimalToJSONEncoder(json.JSONEncoder):
    def default(self, decimal_object):
        if isinstance(decimal_object, Decimal):
            return int(decimal_object) if decimal_object % 1 == 0 else float(decimal_object)
        return super(DynamoDBDecimalToJSONEncoder, self).default(decimal_object)


def fetch_paginated_lost_and_found_items_with_filters(api_gateway_event, lambda_context):
    """
    GET /items?limit=25&status=lost&category=Pets
    
    Query Parameters:
    - limit: Number of items to return (default 25, max 50)
    - status: Filter by 'lost' or 'found'
    - category: Filter by category
    - lastKey: For pagination
    
    AWS Academy Pattern:
    - Returns clean JSON array/object (API Gateway wraps with statusCode)
    - No manual CORS headers (API Gateway handles)
    - Public endpoint (no auth required for browsing)
    """
    
    try:
        query_string_parameters = api_gateway_event.get('queryStringParameters') or {}
        maximum_items_to_return = min(int(query_string_parameters.get('limit', 25)), 50)
        item_status_filter_value = query_string_parameters.get('status')
        category_filter_value = query_string_parameters.get('category')
        pagination_last_evaluated_key = query_string_parameters.get('lastKey')
        
        dynamodb_scan_parameters = {
            'Limit': maximum_items_to_return * 2
        }
        
        filter_expression_conditions = []
        
        if item_status_filter_value:
            filter_expression_conditions.append(Attr('status').eq(item_status_filter_value))
        
        if category_filter_value:
            filter_expression_conditions.append(Attr('category').eq(category_filter_value))
        
        if filter_expression_conditions:
            combined_filter_expression = filter_expression_conditions[0]
            for expression_condition in filter_expression_conditions[1:]:
                combined_filter_expression = combined_filter_expression & expression_condition
            dynamodb_scan_parameters['FilterExpression'] = combined_filter_expression
        
        if pagination_last_evaluated_key:
            dynamodb_scan_parameters['ExclusiveStartKey'] = json.loads(pagination_last_evaluated_key)
        
        dynamodb_scan_response = lost_and_found_items_table.scan(**dynamodb_scan_parameters)
        
        items_sorted_by_creation_date = sorted(
            dynamodb_scan_response.get('Items', []),
            key=lambda item_record: item_record.get('createdAt', ''),
            reverse=True
        )
        
        response_data_with_pagination = {
            'items': items_sorted_by_creation_date[:maximum_items_to_return],
            'count': len(items_sorted_by_creation_date)
        }
        
        if 'LastEvaluatedKey' in dynamodb_scan_response:
            response_data_with_pagination['lastKey'] = json.dumps(
                dynamodb_scan_response['LastEvaluatedKey'], 
                cls=DynamoDBDecimalToJSONEncoder
            )
        
        return response_data_with_pagination
        
    except ClientError as dynamodb_client_error:
        error_code_from_dynamodb = dynamodb_client_error.response['Error']['Code']
        error_message_from_dynamodb = dynamodb_client_error.response['Error']['Message']
        print(f"DynamoDB Error [{error_code_from_dynamodb}]: {error_message_from_dynamodb}")
        raise Exception(f"Database error: {error_message_from_dynamodb}")
        
    except Exception as unexpected_exception:
        print(f"Error: {str(unexpected_exception)}")
        raise Exception(f"Internal server error: {str(unexpected_exception)}")

lambda_handler = fetch_paginated_lost_and_found_items_with_filters

