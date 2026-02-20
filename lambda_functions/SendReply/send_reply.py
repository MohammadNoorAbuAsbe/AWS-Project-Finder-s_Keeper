"""
Lambda Function: Send Reply in Conversation Thread
Sends a reply message in an existing conversation about an item

INTERFACE DOCUMENTATION:
=======================

Endpoint: POST /messages/reply
Method: POST
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Request Headers:
  - Authorization (string, required): Cognito JWT token
  - Content-Type: application/json

Request Body (JSON):
{
  "threadId": "itemId#userId1#userId2" (optional),
  "itemId": "uuid-string" (required),
  "recipientUserId": "cognito-user-id" (required),
  "message": "string" (required, max 1000 characters)
}

Field Validations:
  - itemId: Required, must be a valid item UUID
  - recipientUserId: Required, Cognito user ID of recipient
  - message: Required, max 1000 characters

User Information (extracted from Cognito token):
  - sub: Sender's unique identifier
  - email: Sender's email address
  - name: Sender's display name

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "success": true,
  "message": "Reply sent successfully",
  "details": {
    "messageId": "uuid-string",
    "threadId": "itemId#userId1#userId2",
    "itemId": "uuid-string",
    "recipientUserId": "cognito-user-id"
  }
}

Error Responses:
  - 400 Bad Request (Validation):
    {"error": "Validation error: [specific error]"}
    Examples:
      - "Missing required field: itemId"
      - "Missing required field: recipientUserId"
      - "Missing required field: message"
      - "Message must be less than 1000 characters"
      - "You cannot send a message to yourself"
      - "Conversation thread not found - please wait a few seconds and try again (GSI sync delay)"
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 500 Internal Server Error:
    {"error": "Database error: [error message]"}

EXAMPLE REQUEST:
----------------
POST /messages/reply
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "itemId": "123e4567-e89b-12d3-a456-426614174000",
  "recipientUserId": "abc123-cognito-user-id",
  "message": "Great! I can meet you tomorrow at 2pm. Does that work for you?"
}

BEHAVIOR:
---------
  - Finds existing conversation thread between users
  - Creates new message in the thread
  - Stores message in DynamoDB Messages table
  - Marks message as unread for recipient
  - Preserves item and user context from original message
  - May have slight delay due to DynamoDB GSI eventual consistency

AWS Academy Learner Lab Pattern (Standard Lambda Integration):
- Returns CLEAN JSON data (no statusCode or headers)
- API Gateway wraps the response using mapping templates
- Cognito authentication handled by API Gateway authorizer
"""

import json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
import os
from datetime import datetime
import uuid

dynamodb_resource = boto3.resource('dynamodb')
user_to_user_messages_table_name = os.environ.get('MESSAGES_TABLE', 'FindersKeeper-Messages')
user_to_user_messages_table = dynamodb_resource.Table(user_to_user_messages_table_name)

def send_reply_message_in_existing_conversation_thread(api_gateway_event, lambda_context):
    """
    POST /messages/reply
    
    Request body:
    {
        "threadId": "itemId#userId1#userId2",
        "itemId": "uuid",
        "recipientUserId": "uuid",
        "message": "Reply text"
    }
    
    Returns clean JSON - API Gateway handles response wrapping
    """
    
    try:
        print(f"DEBUG - Event received: {json.dumps(api_gateway_event)}")
        
        # Get user info from Cognito authorizer
        claims = api_gateway_event['requestContext']['authorizer']['claims']
        user_id = claims['sub']
        user_email = claims['email']
        user_name = claims.get('name', user_email.split('@')[0])
        
        # Parse request body
        body = api_gateway_event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        print(f"Reply from user: {user_email} ({user_id})")
        
        # Validate input
        required_fields = ['itemId', 'recipientUserId', 'message']
        for field in required_fields:
            if field not in body or not body[field]:
                raise ValueError(f"Missing required field: {field}")
        
        item_id = body['itemId']
        recipient_user_id = body['recipientUserId']
        message_text = body['message']
        
        # Validate message length
        if len(message_text) > 1000:
            raise ValueError("Message must be less than 1000 characters")
        
        # Don't allow messaging yourself
        if recipient_user_id == user_id:
            raise ValueError('You cannot send a message to yourself')
        
        # Get item details and recipient info from any existing message in the thread
        # Search for messages between these two users about this item
        print(f"Searching for conversation: itemId={item_id}, currentUser={user_id}, otherUser={recipient_user_id}")
        
        # Try finding where current user is recipient
        # Query without filter, then filter in Python (more reliable)
        response = user_to_user_messages_table.query(
            IndexName='RecipientIndex',
            KeyConditionExpression='recipientUserId = :uid',
            ExpressionAttributeValues={
                ':uid': user_id
            }
        )
        
        print(f"Query 1 response: Count={response.get('Count', 0)}, ScannedCount={response.get('ScannedCount', 0)}")
        existing_message = None
        
        # Filter in Python to find matching conversation
        for msg in response.get('Items', []):
            if msg.get('itemId') == item_id and msg.get('senderUserId') == recipient_user_id:
                existing_message = msg
                print(f"Found message in query 1: {existing_message.get('id')}")
                break
        
        # If no message found, try where other user is recipient
        if not existing_message:
            response = user_to_user_messages_table.query(
                IndexName='RecipientIndex',
                KeyConditionExpression='recipientUserId = :uid',
                ExpressionAttributeValues={
                    ':uid': recipient_user_id
                }
            )
            print(f"Query 2 response: Count={response.get('Count', 0)}, ScannedCount={response.get('ScannedCount', 0)}")
            
            # Filter in Python to find matching conversation
            for msg in response.get('Items', []):
                if msg.get('itemId') == item_id and msg.get('senderUserId') == user_id:
                    existing_message = msg
                    print(f"Found message in query 2: {existing_message.get('id')}")
                    break
        
        # If still not found, try a scan as last resort (for the first reply in a thread)
        if not existing_message:
            print("Trying scan as last resort...")
            response = user_to_user_messages_table.scan(
                FilterExpression='itemId = :iid AND ((senderUserId = :uid1 AND recipientUserId = :uid2) OR (senderUserId = :uid2 AND recipientUserId = :uid1))',
                ExpressionAttributeValues={
                    ':iid': item_id,
                    ':uid1': user_id,
                    ':uid2': recipient_user_id
                },
                Limit=10  # Increase limit to scan more items
            )
            if response.get('Items'):
                existing_message = response['Items'][0]
                print(f"Found message in scan: {existing_message.get('id')}")
            else:
                print(f"Scan returned {len(response.get('Items', []))} items")
                print(f"Scan response details: Count={response.get('Count', 0)}, ScannedCount={response.get('ScannedCount', 0)}")
        
        # If still not found, check the main table by ID (if we have one)
        # This is a workaround for GSI eventual consistency
        if not existing_message:
            print("Final attempt: Fetching item details directly from Items table...")
            # Try to get the item to at least get the title and status
            items_table = dynamodb.Table(os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items'))
            try:
                item_response = items_table.get_item(Key={'id': item_id})
                if 'Item' in item_response:
                    item_data = item_response['Item']
                    print(f"Found item in Items table: {item_data.get('title', 'Unknown')}")
                    # Create a minimal message context
                    existing_message = {
                        'itemTitle': item_data.get('title', 'Unknown Item'),
                        'itemStatus': item_data.get('status', 'unknown'),
                        'recipientName': 'User',  # Will be updated with actual recipient
                        'recipientEmail': ''  # Will be updated with actual recipient
                    }
            except Exception as e:
                print(f"Could not fetch item: {str(e)}")
        
        if not existing_message:
            print(f"ERROR: No conversation found between users {user_id} and {recipient_user_id} for item {item_id}")
            raise ValueError('Conversation thread not found - please wait a few seconds and try again (GSI sync delay)')
        
        # Extract details from existing message
        item_title = existing_message.get('itemTitle', 'Unknown Item')
        item_status = existing_message.get('itemStatus', 'unknown')
        
        # Determine recipient name and email
        # Try to get from existing message first
        if existing_message.get('senderUserId') == recipient_user_id:
            recipient_name = existing_message.get('senderName', 'Unknown')
            recipient_email = existing_message.get('senderEmail', '')
        elif existing_message.get('recipientUserId') == recipient_user_id:
            recipient_name = existing_message.get('recipientName', 'Unknown')
            recipient_email = existing_message.get('recipientEmail', '')
        else:
            # Fallback: get recipient from Cognito or use a default
            print(f"Warning: Could not determine recipient details, using defaults")
            recipient_name = 'User'
            recipient_email = ''
        
        # Create new message record
        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        message_record = {
            'id': message_id,
            'itemId': item_id,
            'itemTitle': item_title,
            'itemStatus': item_status,
            'recipientUserId': recipient_user_id,
            'recipientEmail': recipient_email,
            'recipientName': recipient_name,
            'senderUserId': user_id,
            'senderEmail': user_email,
            'senderName': user_name,
            'message': message_text,
            'createdAt': timestamp,
            'read': False
        }
        
        # Store message in DynamoDB
        user_to_user_messages_table.put_item(Item=message_record)
        
        print(f"✓ Reply sent successfully (ID: {message_id})")
        print(f"  From: {user_email} → To: {recipient_email}")
        print(f"  Item: {item_title}")
        
        # Return clean data
        return {
            'success': True,
            'messageId': message_id,
            'message': 'Reply sent successfully',
            'sentAt': timestamp
        }
        
    except KeyError as e:
        print(f"Missing required field: {str(e)}")
        raise Exception("Unauthorized: Valid authentication required")
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        raise Exception(str(e))
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"DynamoDB Error [{error_code}]: {error_msg}")
        raise Exception(f"Database error: {error_msg}")
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise Exception(f"Internal server error: {str(e)}")
