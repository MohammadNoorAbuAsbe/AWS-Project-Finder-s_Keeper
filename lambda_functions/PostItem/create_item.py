"""
Lambda Function: Create Item
Allows authenticated users to post a new lost/found item
Validates input and stores in DynamoDB
Handles base64-encoded image uploads to S3 (AWS Academy compatible)

INTERFACE DOCUMENTATION:
=======================

Endpoint: POST /items
Method: POST
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Request Headers:
  - Authorization (string, required): Cognito JWT token
  - Content-Type: application/json

Request Body (JSON):
{
  "title": "string" (required, 3-100 characters),
  "status": "lost" | "found" (required),
  "location": "string" (required, 3-100 characters),
  "date": "YYYY-MM-DD" (required),
  "category": "string" (required, e.g., "Pets", "Electronics"),
  "description": "string" (required, max 500 characters),
  "imageBase64": "data:image/jpeg;base64,..." (optional),
  "color": "string" (optional)
}

Field Validations:
  - title: Required, 3-100 characters
  - status: Required, must be "lost" or "found"
  - location: Required, 3-100 characters
  - date: Required, string format YYYY-MM-DD
  - category: Required, any string
  - description: Required, max 500 characters
  - imageBase64: Optional, base64-encoded image with data URI
    Supported formats: JPEG, PNG, GIF, WebP
  - color: Optional, string

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "success": true,
  "id": "uuid-string",
  "imageUrl": "https://bucket.s3.amazonaws.com/items/uuid-timestamp.jpg",
  "message": "Item created successfully"
}

Error Responses:
  - 400 Bad Request (Validation):
    {"error": "Validation error: [specific error]"}
    Examples:
      - "Missing required field: title"
      - "Status must be 'lost' or 'found'"
      - "Title must be between 3 and 100 characters"
      - "Description must be less than 500 characters"
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 500 Internal Server Error:
    {"error": "Database error: [error message]"}
    {"error": "Failed to upload image: [error message]"}

EXAMPLE REQUEST:
----------------
POST /items
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "title": "Black iPhone 14 Pro",
  "status": "lost",
  "location": "Central Park near Bethesda Fountain",
  "date": "2026-01-20",
  "category": "Electronics",
  "description": "Lost black iPhone 14 Pro with cracked screen protector",
  "color": "Black",
  "imageBase64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}

BEHAVIOR:
---------
  - Generates unique UUID for item
  - Uploads image to S3 if provided
  - Stores item in DynamoDB Items table
  - Associates item with authenticated user
  - Records creation timestamp

AWS Academy Learner Lab Pattern:
- API Gateway handles CORS and status codes (no manual headers)
- Returns clean JSON-serializable objects
- Uses botocore.exceptions.ClientError for error handling
"""

import json
import boto3
from botocore.exceptions import ClientError
import uuid
import base64
from datetime import datetime
import os

dynamodb_resource = boto3.resource('dynamodb')
s3_client_for_image_uploads = boto3.client('s3')
lost_and_found_items_table_name = os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items')
public_image_storage_bucket_name = os.environ.get('IMAGE_BUCKET', 'finders-keeper-images')
lost_and_found_items_table = dynamodb_resource.Table(lost_and_found_items_table_name)

def validate_required_item_fields_and_constraints(item_data_from_request):
    required_field_names = ['title', 'status', 'location', 'date', 'category', 'description']
    
    for field_name in required_field_names:
        if field_name not in item_data_from_request or not item_data_from_request[field_name]:
            raise ValueError(f"Missing required field: {field_name}")
    
    if item_data_from_request['status'] not in ['lost', 'found']:
        raise ValueError("Status must be 'lost' or 'found'")
    
    title_text_length = len(item_data_from_request['title'])
    if title_text_length < 3 or title_text_length > 100:
        raise ValueError("Title must be between 3 and 100 characters")
    
    location_text_length = len(item_data_from_request['location'])
    if location_text_length < 3 or location_text_length > 100:
        raise ValueError("Location must be between 3 and 100 characters")
    
    if len(item_data_from_request['description']) > 500:
        raise ValueError("Description must be less than 500 characters")
    
    return True

def upload_base64_encoded_image_to_s3_and_return_public_url(base64_image_string, unique_item_identifier, authenticated_user_id):
    try:
        if ',' in base64_image_string:
            data_uri_header, base64_encoded_data = base64_image_string.split(',', 1)
            
            if 'image/jpeg' in data_uri_header or 'image/jpg' in data_uri_header:
                http_content_type = 'image/jpeg'
                file_extension = 'jpg'
            elif 'image/png' in data_uri_header:
                http_content_type = 'image/png'
                file_extension = 'png'
            elif 'image/gif' in data_uri_header:
                http_content_type = 'image/gif'
                file_extension = 'gif'
            elif 'image/webp' in data_uri_header:
                http_content_type = 'image/webp'
                file_extension = 'webp'
            else:
                http_content_type = 'image/jpeg'
                file_extension = 'jpg'
        else:
            base64_encoded_data = base64_image_string
            http_content_type = 'image/jpeg'
            file_extension = 'jpg'
        
        decoded_image_binary_data = base64.b64decode(base64_encoded_data)
        
        utc_timestamp_for_filename = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        s3_object_key_for_image = f"items/{unique_item_identifier}-{utc_timestamp_for_filename}.{file_extension}"
        
        s3_client_for_image_uploads.put_object(
            Bucket=public_image_storage_bucket_name,
            Key=s3_object_key_for_image,
            Body=decoded_image_binary_data,
            ContentType=http_content_type,
            Metadata={
                'uploaded-by': authenticated_user_id,
                'upload-date': datetime.utcnow().isoformat()
            }
        )
        
        publicly_accessible_image_url = f"https://{public_image_storage_bucket_name}.s3.amazonaws.com/{s3_object_key_for_image}"
        return publicly_accessible_image_url
        
    except Exception as image_upload_exception:
        print(f"Error uploading image to S3: {str(image_upload_exception)}")
        raise ValueError(f"Failed to upload image: {str(image_upload_exception)}")


def create_new_lost_or_found_item_with_image_upload(api_gateway_event, lambda_context):
    """
    POST /items
    
    Request body:
    {
        "title": "Item title",
        "status": "lost" or "found",
        "location": "Location",
        "date": "YYYY-MM-DD",
        "category": "Category",
        "description": "Description",
        "imageBase64": "base64-encoded image data",
        "color": "Color (optional)"
    }
    
    AWS Academy Pattern:
    - Requires Cognito authentication (handled by API Gateway)
    - Returns clean JSON object (API Gateway wraps with statusCode)
    - No manual CORS headers (API Gateway handles)
    """
    
    try:
        request_body_data = api_gateway_event.get('body', {})
        if isinstance(request_body_data, str):
            request_body_data = json.loads(request_body_data)
        
        cognito_user_claims = api_gateway_event['requestContext']['authorizer']['claims']
        authenticated_user_unique_id = cognito_user_claims['sub']
        authenticated_user_email_address = cognito_user_claims['email']
        authenticated_user_display_name = cognito_user_claims.get('name', authenticated_user_email_address.split('@')[0])
        
        validate_required_item_fields_and_constraints(request_body_data)
        
        generated_unique_item_id = str(uuid.uuid4())
        
        publicly_accessible_image_url = ''
        if 'imageBase64' in request_body_data and request_body_data['imageBase64']:
            print(f"Uploading image for item {generated_unique_item_id}...")
            publicly_accessible_image_url = upload_base64_encoded_image_to_s3_and_return_public_url(
                request_body_data['imageBase64'], 
                generated_unique_item_id, 
                authenticated_user_unique_id
            )
            print(f"Image uploaded successfully: {publicly_accessible_image_url}")
        elif 'img' in request_body_data and request_body_data['img']:
            publicly_accessible_image_url = request_body_data['img']
        
        current_utc_timestamp_iso_format = datetime.utcnow().isoformat() + 'Z'
        
        new_item_record_for_database = {
            'id': generated_unique_item_id,
            'title': request_body_data['title'],
            'status': request_body_data['status'],
            'location': request_body_data['location'],
            'date': request_body_data['date'],
            'category': request_body_data['category'],
            'description': request_body_data['description'],
            'img': publicly_accessible_image_url,
            'color': request_body_data.get('color', ''),
            'userId': authenticated_user_unique_id,
            'userEmail': authenticated_user_email_address,
            'userName': authenticated_user_display_name,
            'createdAt': current_utc_timestamp_iso_format,
            'updatedAt': current_utc_timestamp_iso_format
        }
        
        lost_and_found_items_table.put_item(Item=new_item_record_for_database)
        
        return {
            'success': True,
            'id': generated_unique_item_id,
            'imageUrl': publicly_accessible_image_url,
            'message': 'Item created successfully'
        }
        
    except ValueError as validation_error:
        print(f"Validation error: {str(validation_error)}")
        raise Exception(f"Validation error: {str(validation_error)}")
        
    except KeyError as missing_field_error:
        print(f"Missing required field: {str(missing_field_error)}")
        raise Exception("Unauthorized: Valid authentication required")
        
    except ClientError as aws_service_error:
        error_code_from_aws = aws_service_error.response['Error']['Code']
        error_message_from_aws = aws_service_error.response['Error']['Message']
        print(f"AWS Error [{error_code_from_aws}]: {error_message_from_aws}")
        raise Exception(f"Database error: {error_message_from_aws}")
        
    except Exception as unexpected_exception:
        print(f"Unexpected error: {str(unexpected_exception)}")
        raise Exception(f"Internal server error: {str(unexpected_exception)}")

lambda_handler = create_new_lost_or_found_item_with_image_upload

