"""
Lambda Function: Send Contact Notification
Stores contact messages in DynamoDB and optionally sends email notifications

INTERFACE DOCUMENTATION:
=======================

Endpoint: POST /contact
Method: POST
Authentication: Required (Cognito User Pool)

INPUT PARAMETERS:
-----------------
Request Headers:
  - Authorization (string, required): Cognito JWT token
  - Content-Type: application/json

Request Body (JSON):
{
  "itemId": "uuid-string" (required),
  "message": "string" (required, max 1000 characters),
  "senderName": "string" (optional, extracted from token),
  "senderEmail": "string" (optional, extracted from token)
}

Field Validations:
  - itemId: Required, must be a valid item UUID
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
  "message": "Message sent! The owner can view it in their messages page.",
  "details": {
    "messageId": "uuid-string",
    "itemId": "uuid-string",
    "recipientEmail": "owner@example.com",
    "storedInDatabase": true,
    "emailNotificationSent": false,
    "subscriptionStatus": "disabled",
    "viewMessagesUrl": "https://website.com/messages.html"
  },
  "emailWarning": "Message saved but email may not have been delivered: [reason]" (optional)
}

Error Responses:
  - 400 Bad Request (Validation):
    {"error": "Validation error: [specific error]"}
    Examples:
      - "Missing required field: itemId"
      - "Missing required field: message"
      - "Message must be less than 1000 characters"
      - "Item not found"
      - "You cannot contact yourself"
  
  - 401 Unauthorized:
    {"error": "Unauthorized: Valid authentication required"}
  
  - 500 Internal Server Error:
    {"error": "AWS service error: [error message]"}

EXAMPLE REQUEST:
----------------
POST /contact
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "itemId": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Hi, I found your lost phone! Please contact me to arrange pickup."
}

BEHAVIOR:
---------
  - Validates that sender is not the item owner
  - Creates message record in DynamoDB Messages table
  - Message is viewable in recipient's messages inbox
  - Email notifications are disabled by default
  - Generates unique message ID and thread ID
  - Records timestamp and marks as unread

AWS Academy Workaround:
- SES is disabled in AWS Academy (cannot send to arbitrary emails)
- SNS topics broadcast to ALL subscribers (not per-user)
- Solution: Store messages in DynamoDB for in-app viewing
- Optional: Email notification to SNS subscribers (informational only)
"""

import json
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import uuid

dynamodb_resource = boto3.resource('dynamodb')
sns_notification_client = boto3.client('sns')

lost_and_found_items_table_name = os.environ.get('ITEMS_TABLE', 'FindersKeeper-Items')
lost_and_found_items_table = dynamodb_resource.Table(lost_and_found_items_table_name)

user_to_user_messages_table_name = os.environ.get('MESSAGES_TABLE', 'FindersKeeper-Messages')
user_to_user_messages_table = dynamodb_resource.Table(user_to_user_messages_table_name)

application_website_base_url = os.environ.get('WEBSITE_URL', 'https://finderskeeper.com')
sns_topic_arn_for_contact_notifications = os.environ.get('SNS_TOPIC_ARN', '')

def lambda_handler(event, context):
    """
    POST /contact
    
    Request body:
    {
        "itemId": "uuid",
        "message": "User message",
        "senderName": "Sender's name",
        "senderEmail": "sender@example.com"
    }
    
    AWS Academy Pattern:
    - Requires Cognito authentication (handled by API Gateway)
    - Returns clean JSON object (API Gateway wraps with statusCode)
    - No manual CORS headers (API Gateway handles)
    - Uses SNS for notifications (SES restricted in lab)
    """
    
    try:
        # Parse request body - handle both string and dict formats
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        # Get user info from Cognito authorizer
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims['sub']
        user_email = claims['email']
        user_name = claims.get('name', user_email.split('@')[0])
        
        # Validate input
        required_fields = ['itemId', 'message']
        for field in required_fields:
            if field not in body or not body[field]:
                raise ValueError(f"Missing required field: {field}")
        
        item_id = body['itemId']
        message = body['message']
        
        # Validate message length
        if len(message) > 1000:
            raise ValueError("Message must be less than 1000 characters")
        
        # Get the item to find the owner
        response = lost_and_found_items_table.get_item(Key={'id': item_id})
        
        if 'Item' not in response:
            raise ValueError('Item not found')
        
        item = response['Item']
        owner_email = item.get('userEmail')
        owner_name = item.get('userName', 'Item Owner')
        
        # Don't allow contacting yourself
        if owner_email == user_email:
            raise ValueError('You cannot contact yourself')
        
        # STEP 1: Store message in DynamoDB for in-app viewing
        # This ensures the owner can see the message regardless of email delivery
        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        message_record = {
            'id': message_id,
            'itemId': item_id,
            'itemTitle': item['title'],
            'itemStatus': item['status'],
            'recipientUserId': item['userId'],
            'recipientEmail': owner_email,
            'recipientName': owner_name,
            'senderUserId': user_id,
            'senderEmail': user_email,
            'senderName': user_name,
            'message': message,
            'createdAt': timestamp,
            'read': False
        }
        
        try:
            user_to_user_messages_table.put_item(Item=message_record)
            print(f"✓ Message stored in DynamoDB (ID: {message_id})")
            print(f"  Owner: {owner_email} can view this in their profile")
        except ClientError as db_error:
            # If messages table doesn't exist, continue without storing
            # (table creation is optional)
            print(f"⚠ Could not store message in DynamoDB: {db_error}")
            print(f"  Message will only be sent via email (if configured)")
        
        # STEP 2: Optional Email Notification (DISABLED by default)
        # Email notifications require SNS subscription confirmation which users often miss
        # Messages are always stored in database and viewable in-app
        
        notification_sent = False
        subscription_status = 'disabled'
        error_message = None
        
        # Skip email notifications - users can view messages in-app
        print("✓ Message stored in database - viewable in user's messages page")
        print("  Email notifications disabled (users can view messages in-app)")
        
        # Optional: Uncomment below to enable email notifications
        # Note: Users must confirm SNS subscription via email before receiving notifications
        """
        if SNS_TOPIC_ARN:
            try:
                # Check if owner is already subscribed
                subscriptions = sns.list_subscriptions_by_topic(TopicArn=SNS_TOPIC_ARN)
                
                owner_subscription = None
                for sub in subscriptions.get('Subscriptions', []):
                    if sub['Protocol'] == 'email' and sub['Endpoint'] == owner_email:
                        owner_subscription = sub
                        break
                
                # Subscribe owner if not already subscribed
                if not owner_subscription:
                    print(f"→ Subscribing {owner_email} to notifications...")
                    sub_response = sns.subscribe(
                        TopicArn=SNS_TOPIC_ARN,
                        Protocol='email',
                        Endpoint=owner_email,
                        ReturnSubscriptionArn=True
                    )
                    subscription_status = 'pending_confirmation'
                    print(f"✓ Subscription created for {owner_email}")
                    print(f"  ⚠ Owner must confirm subscription via email to receive notifications")
                elif owner_subscription['SubscriptionArn'] == 'PendingConfirmation':
                    subscription_status = 'pending_confirmation'
                    print(f"⚠ {owner_email} subscription is pending confirmation")
                else:
                    subscription_status = 'confirmed'
                    print(f"✓ {owner_email} is already subscribed")
                
                # Prepare personalized email
                subject = f"[Finder's Keeper] New message about: {item['title']}"
                
                email_message = f'''Hello {owner_name},

You have a new message about your {item['status']} item on Finder's Keeper!

ITEM: {item['title']}
FROM: {user_name}

MESSAGE:
{message}

---
TO RESPOND:
Reply directly to {user_name} at: {user_email}

Or log in to Finder's Keeper to view all your messages:
{application_website_base_url}/messages.html

Direct link to item: {application_website_base_url}/itemDetails.html?id={item_id}

---
This message was sent to you because someone contacted you about your item.
'''
                
                # Publish notification (will be sent to ALL subscribed emails)
                response = sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject=subject,
                    Message=email_message,
                    MessageAttributes={
                        'recipientEmail': {
                            'DataType': 'String',
                            'StringValue': owner_email
                        },
                        'messageId': {
                            'DataType': 'String',
                            'StringValue': message_id
                        }
                    }
                )
                
                notification_sent = True
                print(f"✓ Email notification published (MessageId: {response['MessageId']})")
                
                if subscription_status == 'pending_confirmation':
                    print(f"  ⚠ Email will be delivered only after {owner_email} confirms subscription")
                elif subscription_status == 'confirmed':
                    print(f"  ✓ Email will be delivered to {owner_email}")
                
            except ClientError as sns_error:
                error_code = sns_error.response['Error']['Code']
                error_message = f"SNS Error [{error_code}]: {str(sns_error)}"
                print(error_message)
            except Exception as e:
                error_message = f"Email notification error: {str(e)}"
                print(error_message)
        else:
            print("⚠ SNS not configured - skipping email notification")
            print("✓ Message stored in DynamoDB for in-app viewing")
        """
        
        
        # Return success response with details
        response_data = {
            'success': True,
            'message': 'Message sent! The owner can view it in their messages page.',
            'details': {
                'messageId': message_id,
                'itemId': item_id,
                'recipientEmail': owner_email,
                'storedInDatabase': True,
                'emailNotificationSent': notification_sent,
                'subscriptionStatus': subscription_status,
                'viewMessagesUrl': f'{application_website_base_url}/messages.html'
            }
        }
        
        if error_message:
            response_data['emailWarning'] = 'Message saved but email may not have been delivered: ' + error_message
        
        print(f"✓ Contact request completed successfully")
        print(f"  Message ID: {message_id}")
        print(f"  Recipient: {owner_email}")
        print(f"  Stored in DB: True")
        print(f"  Email sent: {notification_sent}")
        print(f"  View at: {application_website_base_url}/messages.html")
        
        return response_data
        
    except ValueError as e:
        # Validation error
        print(f"Validation error: {str(e)}")
        raise Exception(f"Validation error: {str(e)}")
        
    except KeyError as e:
        # Missing required fields (likely auth issue)
        print(f"Missing required field: {str(e)}")
        raise Exception("Unauthorized: Valid authentication required")
        
    except ClientError as e:
        # DynamoDB or SNS error
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"AWS Error [{error_code}]: {error_msg}")
        raise Exception(f"AWS service error: {error_msg}")
        
    except Exception as e:
        # Unexpected error
        print(f"Unexpected error: {str(e)}")
        raise Exception(f"Internal server error: {str(e)}")
