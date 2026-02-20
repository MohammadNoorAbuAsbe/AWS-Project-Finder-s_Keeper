"""
Lambda Function: Get User Messages
Retrieves contact messages for the authenticated user

INTERFACE DOCUMENTATION:
=======================

Endpoint: GET /messages
Method: GET
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Query String Parameters: None
Request Headers:
  - Authorization (string, required): Cognito JWT token
    Format: Bearer token from Cognito authentication
Request Body: None

User Information (extracted from Cognito token):
  - sub: User's unique identifier
  - email: User's email address

RESPONSE FORMAT:
----------------
Success Response (200):
{
  "success": true,
  "threads": [
    {
      "threadId": "itemId#userId1#userId2",
      "itemId": "uuid-string",
      "itemTitle": "Item title",
      "itemStatus": "lost" | "found",
      "otherUserId": "other-user-cognito-id",
      "otherUserName": "Other User Name",
      "otherUserEmail": "other@example.com",
      "lastMessageTime": "2026-01-22T10:30:00.000Z",
      "unreadCount": 3,
      "messages": [
        {
          "id": "message-uuid",
          "itemId": "item-uuid",
          "itemTitle": "Item title",
          "itemStatus": "lost" | "found",
          "senderUserId": "sender-cognito-id",
          "senderName": "Sender Name",
          "senderEmail": "sender@example.com",
          "recipientUserId": "recipient-cognito-id",
          "recipientName": "Recipient Name",
          "recipientEmail": "recipient@example.com",
          "message": "Message text content",
          "createdAt": "2026-01-22T10:30:00.000Z",
          "read": false
        }
      ]
    }
  ],
  "totalThreads": 5,
  "totalMessages": 23,
  "unreadCount": 7
}

Error Responses:
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 500 Internal Server Error:
    {"error": "Database error: [error message]"}

BEHAVIOR:
---------
  - Retrieves all messages where user is sender OR recipient
  - Groups messages into conversation threads by itemId and user pair
  - Sorts messages within threads chronologically (oldest first)
  - Sorts threads by most recent message (newest first)
  - Calculates unread count per thread

AWS Academy Learner Lab Pattern (Standard Lambda Integration):
- Returns CLEAN JSON data (no statusCode or headers)
- API Gateway wraps the response using mapping templates
- Cognito authentication handled by API Gateway authorizer
- Queries messages by recipient user ID
- Returns messages sorted by date (newest first)
"""

import json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
import os

class DynamoDBDecimalToJSONEncoder(json.JSONEncoder):
    def default(self, decimal_object):
        if isinstance(decimal_object, Decimal):
            return int(decimal_object) if decimal_object % 1 == 0 else float(decimal_object)
        return super(DynamoDBDecimalToJSONEncoder, self).default(decimal_object)

dynamodb_resource = boto3.resource('dynamodb')
user_to_user_messages_table_name = os.environ.get('MESSAGES_TABLE', 'FindersKeeper-Messages')
user_to_user_messages_table = dynamodb_resource.Table(user_to_user_messages_table_name)

def lambda_handler(event, context):
    """
    GET /messages
    
    Returns all messages for the authenticated user.
    API Gateway handles response wrapping - this returns CLEAN data only.
    """
    
    try:
        # Debug: Print the incoming event structure
        print(f"DEBUG - Event received: {json.dumps(event)}")
        
        # Get user info from Cognito authorizer
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims['sub']
        user_email = claims['email']
        
        print(f"Fetching messages for user: {user_email} ({user_id})")
        
        # Query messages where user is the recipient
        response_recipient = user_to_user_messages_table.query(
            IndexName='RecipientIndex',
            KeyConditionExpression='recipientUserId = :uid',
            ExpressionAttributeValues={
                ':uid': user_id
            },
            ScanIndexForward=False  # Sort descending (newest first)
        )
        
        # Query messages where user is the sender (need a SenderIndex for this)
        # For now, we'll scan and filter - not ideal but works for AWS Academy
        response_sender = user_to_user_messages_table.scan(
            FilterExpression='senderUserId = :uid',
            ExpressionAttributeValues={
                ':uid': user_id
            }
        )
        
        # Combine messages from both queries
        messages_received = response_recipient.get('Items', [])
        messages_sent = response_sender.get('Items', [])
        messages = messages_received + messages_sent
        
        print(f"Found {len(messages_received)} received messages and {len(messages_sent)} sent messages")
        
        # Convert Decimal types to JSON-serializable types
        messages = json.loads(json.dumps(messages, cls=DynamoDBDecimalToJSONEncoder))
        
        # Group messages into conversation threads
        # Each thread is between two users about a specific item
        threads = {}
        for msg in messages:
            # Create unique thread ID: itemId + sorted user IDs
            sender_id = msg.get('senderUserId', '')
            recipient_id = msg.get('recipientUserId', '')
            item_id = msg.get('itemId', '')
            
            # Sort user IDs to ensure consistency regardless of who sent first
            user_ids = sorted([sender_id, recipient_id])
            thread_id = f"{item_id}#{user_ids[0]}#{user_ids[1]}"
            
            if thread_id not in threads:
                # Determine the "other user" in this conversation
                other_user_id = sender_id if sender_id != user_id else recipient_id
                other_user_name = msg.get('senderName') if sender_id != user_id else msg.get('recipientName', 'Unknown')
                other_user_email = msg.get('senderEmail') if sender_id != user_id else msg.get('recipientEmail', '')
                
                threads[thread_id] = {
                    'threadId': thread_id,
                    'itemId': item_id,
                    'itemTitle': msg.get('itemTitle', 'Unknown Item'),
                    'itemStatus': msg.get('itemStatus', 'unknown'),
                    'otherUserId': other_user_id,
                    'otherUserName': other_user_name,
                    'otherUserEmail': other_user_email,
                    'messages': [],
                    'lastMessageTime': msg.get('createdAt', ''),
                    'unreadCount': 0
                }
            
            # Add message to thread
            threads[thread_id]['messages'].append(msg)
            
            # Update last message time
            if msg.get('createdAt', '') > threads[thread_id]['lastMessageTime']:
                threads[thread_id]['lastMessageTime'] = msg.get('createdAt', '')
            
            # Count unread messages (messages sent TO the current user that are unread)
            if msg.get('recipientUserId') == user_id and not msg.get('read', False):
                threads[thread_id]['unreadCount'] += 1
        
        # Sort messages within each thread by time (oldest first for chat display)
        for thread in threads.values():
            thread['messages'].sort(key=lambda x: x.get('createdAt', ''))
        
        # Convert to list and sort threads by last message time (newest first)
        thread_list = list(threads.values())
        thread_list.sort(key=lambda x: x['lastMessageTime'], reverse=True)
        
        total_unread = sum(thread['unreadCount'] for thread in thread_list)
        
        print(f"✓ Found {len(thread_list)} conversation threads with {len(messages)} total messages ({total_unread} unread)")
        
        # Return CLEAN data - API Gateway wraps this in statusCode/headers
        return {
            'success': True,
            'threads': thread_list,
            'totalThreads': len(thread_list),
            'totalMessages': len(messages),
            'unreadCount': total_unread
        }
        
    except KeyError as e:
        print(f"Missing required field: {str(e)}")
        raise Exception("Unauthorized: Valid authentication required")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"DynamoDB Error [{error_code}]: {error_msg}")
        raise Exception(f"Database error: {error_msg}")
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise Exception(f"Internal server error: {str(e)}")
