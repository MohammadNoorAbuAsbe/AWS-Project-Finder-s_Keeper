import boto3
import json

def lambda_handler(event, context):
    """
    Cognito Post Confirmation Trigger
    Automatically adds new users to the 'Users' group after account confirmation
    
    INTERFACE DOCUMENTATION:
    =======================
    
    Trigger: Cognito User Pool Post Confirmation
    Invocation: Automatic (triggered by Cognito)
    Authentication: Not applicable (internal AWS service trigger)
    
    INPUT PARAMETERS:
    -----------------
    Event Structure (provided by Cognito):
    {
      "version": "1",
      "region": "us-east-1",
      "userPoolId": "us-east-1_XXXXXXXXX",
      "userName": "user@example.com",
      "callerContext": {...},
      "triggerSource": "PostConfirmation_ConfirmSignUp",
      "request": {
        "userAttributes": {
          "sub": "uuid",
          "email": "user@example.com",
          "email_verified": "true",
          "name": "User Name"
        }
      },
      "response": {}
    }
    
    Required Fields:
      - userPoolId (string): The Cognito User Pool ID
      - userName (string): The username of the confirmed user
    
    RESPONSE FORMAT:
    ----------------
    Returns the original event object (Cognito requirement)
    
    Success:
      - Original event is returned unchanged
      - User is added to 'Users' group
      - Console log: "Successfully added user {username} to Users group"
    
    Error Handling:
      - If group assignment fails, still returns event
      - User registration completes even if group assignment fails
      - Console log: "Error adding user to group: {error}"
    
    BEHAVIOR:
    ---------
      - Automatically invoked when user confirms email
      - Adds user to default 'Users' group in Cognito
      - Does not fail registration if group assignment fails
      - 'Users' group must exist in Cognito User Pool
    """
    try:
        # Extract user pool ID and username from the event
        user_pool_id = event['userPoolId']
        username = event['userName']
        
        # Initialize Cognito client
        cognito_client = boto3.client('cognito-idp')
        
        # Add user to 'Users' group
        cognito_client.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=username,
            GroupName='Users'
        )
        
        print(f"Successfully added user {username} to Users group")
        return event
        
    except Exception as e:
        print(f"Error adding user to group: {str(e)}")
        # Still return the event even if group assignment fails
        # User registration should not fail due to this
        return event