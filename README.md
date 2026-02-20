# FindersKeeper - AWS Deployment Guide

## Project Overview

FindersKeeper is a serverless lost and found application built on AWS. Users can post lost or found items, browse listings, and contact item owners through a secure messaging system. The application features user authentication, image uploads, and an admin panel for user management.

## Architecture

- **Frontend**: Static website hosted on Amazon S3
- **Authentication**: Amazon Cognito User Pools with email verification
- **API**: Amazon API Gateway REST API with Cognito authorizers
- **Compute**: AWS Lambda functions (Python 3.9+)
- **Database**: Amazon DynamoDB with Global Secondary Indexes
- **Storage**: Amazon S3 for image uploads
- **Notifications**: Amazon SNS for email notifications

## Prerequisites

Before starting the installation, ensure you have:

1. **AWS Account**: A clean AWS account with administrative privileges
2. **AWS CLI**: Installed and configured with your credentials
3. **Python 3.9+**: For testing Lambda functions locally (optional)
4. **Basic AWS Knowledge**: Understanding of AWS services and console navigation

## Installation Steps
###Step 0: Sign In to AWS Management Console 
1. Open the AWS Management Console. 
2. Log in with your AWS credentials.
### Step 1: Create DynamoDB Tables

#### 1.1 Create Items Table

1. Navigate to **DynamoDB** in the AWS Console
2. Click **Create table**
3. Configure the table:
   - **Table name**: `FindersKeeper-Items`
   - **Partition key**: `id` (String)
   - **Table settings**: Use default settings (On-demand billing)
4. Click **Create table**

#### 1.2 Create Messages Table

1. Click **Create table** again
2. Configure the table:
   - **Table name**: `FindersKeeper-Messages`
   - **Partition key**: `id` (String)
      - **Table settings**: Use default settings (On-demand billing)
3. Click **Create table**

4. After creation, add a Global Secondary Index:
     click on the table FindersKeeper-Messages
   - Go to the **Indexes** tab
   - Click **Create index**
   - **Index name**: `RecipientIndex`
   - **Partition key**: `recipientUserId` (String)
   - **Sort key**: `createdAt` (String)
   - **Projected attributes**: All attributes
   - Click **Create index**
   - Wait until the index finishes the creation

### Step 2: Create S3 Buckets

#### 2.1 Create Image Storage Bucket

1. Navigate to **S3** in the AWS Console
2. Click **Create bucket**
3. Configure the bucket:
   - **Bucket name**: give the bucket a unique name for example:`finders-keeper-images-(the first two letters from your name)`
   - **Region**: `us-east-1` (or your preferred region)
   - **Block Public Access**: Uncheck "Block all public access" (we need public read access for images)
   -a warning shows up saying 'Turning off block all public access might result in this bucket and the objects within becoming public', check the acknowledgemnet box
   - **Bucket Versioning**: Disable
   - **Default encryption**: Server-side encryption with Amazon S3 managed keys (SSE-S3)
4. Click **Create bucket**

#### 2.2 Configure Image Bucket Policy

1. Select your image bucket
2. Go to **Permissions** tab
3. Click **Edit** in **Bucket policy**
4. Add this policy (replace `YOUR-BUCKET-NAME` with your actual bucket name):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        }
    ]
}
```
5.Click Save changes

#### 2.3 Create Frontend Hosting Bucket
 Navigate to **S3** in the AWS Console
1. Create another bucket for the frontend:
   - **Click *Create bucket*
   - **Bucket name**: `finders-keeper-frontend-[YOUR-UNIQUE-SUFFIX]`
   - **Region**: us-east-1
   - **Block Public Access**: Uncheck "Block all public access" (we need public read access for images)
   -a warning shows up saying 'Turning off block all public access might result in this bucket and the objects within becoming public', check the acknowledgemnet box
    Click **Create bucket**

2. After creation, enable static website hosting:
    Select your frontend bucket
   - Go to **Properties** tab
   - Scroll to **Static website hosting**
   - Click **Edit**
   - **Static website hosting**: Enable
   - **Index document**: `index.html`
   - **Error document**: `index.html`
   - Click **Save changes**

#### 2.4 Configure Frontend Bucket Policy
1. Go to **Permissions** tab
2. Click **Edit** in **Bucket policy**

Add this policy to your frontend bucket (replace `YOUR-FRONTEND-BUCKET-NAME`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::YOUR-FRONTEND-BUCKET-NAME/*"
        }
    ]
}
```
Click Save changes

### Step 3: Create Cognito User Pool

#### 3.1 Create User Pool

1. Navigate to **Amazon Cognito** in the AWS Console
click in the left side bar on *User pools*
2. Click **Create user pool**
   scroll to the tap "Define your application" and select *Single-page application (SPA)*
   - **Name your application**: `FindersKeeper-WebApp`
3.In the Configure options tab choose *Email* for the *Options for sign-in identifiers*
for the *Required attributes for sign-up* choose *email* and *name*
Click Create user directory
Scroll down and click Go to overview

Click Rename button and write "FindersKeeper-UserPool"
Click Save changes

in the left bar in Authentication tab select sign-in
click *Edit* in User account recovery tab
choose Email only in *Delivery method for user account recovery messages*
Click *Save Changes*



**Step 4 - Configure message delivery**: 
   - **Email provider**: Send email with Cognito
   - Click **Next**
in the left bar in Branding Choose managed login 
in Styles tap Delete the existing style

#### 3.2 Create User Groups

1. In your User Pool, go to **Groups** tab
2. Click **Create group**
3. Create two groups:
   - **Group 1**: Name: `Users`, Description: `Regular users` ,IAM role 'LabRole'
   Click Create group
   - **Group 2**: Name: `Admins`, Description: `Administrator users` ,IAM role 'LabRole'
   Click Create group


### Step 4: Deploy Lambda Functions

#### 4.1 Create Lambda Functions

For each Lambda function in the `lambda_functions` directory, follow these steps:

1. Navigate to **AWS Lambda** in the console
2. Click **Create function**
3. **Function name**: Use the names from the table below
4. **Runtime**: Python 3.14 
5. **Execution role** select *Use an existing role* and choose `LabRole`
6. Click Create function
**Lambda Functions to Create:**

| Directory | Function Name | Description |
|-----------|---------------|-------------|
| `PostConfirmation` | `FindersKeeper-PostConfirmation` | Adds new users to Users group |
| `GetItems` | `FindersKeeper-GetItems` | Retrieves items from DynamoDB |
| `PostItem` | `FindersKeeper-CreateItem` | Creates new items |
| `DeleteItem` | `FindersKeeper-DeleteItem` | Deletes items |
| `UpdateItem` | `update_item` | Updates item status |
| `GetMessages` | `FindersKeeper-GetMessages` | Retrieves user messages |
| `SendNotification` | `FindersKeeper-SendContact` | Sends contact notifications |
| `SendReply` | `FindersKeeper-SendReply` | Sends message replies |
| `ListUsers` | `FindersKeeper-ListUsers` | Lists users (admin only) |
| `UpdateUserStatus` | `UpdateUserStatus` | Updates user status (admin only) |

edit the userpool id inside list_users 
#### 4.2 Upload Function Code
Go to the list of Functions
For each function:
Click on the function name
go to the Code source tab 
Click Upload from 
Click .zip file 
Click Upload
Locate the project files that we provided, open the folder Lambda_functions, for each function open the directory that matches the function from the table and then select the .zip file 
Click save button

#### 4.2.1 Configure Lambda Timeout

**IMPORTANT**: Some functions need more time to process (especially image uploads). Configure timeouts:

1. For **FindersKeeper-CreateItem** function:
   - Go to **Configuration** tab
   - Click **General configuration** → **Edit**
   - Change **Timeout** from 3 seconds to **30 seconds**
   - Click **Save**

2. For **FindersKeeper-SendContact** and **FindersKeeper-SendReply** functions:
   - Repeat the same process
   - Change **Timeout** to **30 seconds**
   - Click **Save**

3. Other functions can keep the default 3 second timeout 

#### 4.3 Configure Environment Variables

For functions that need them, add these environment variables in the **Configuration** → **Environment variables** section
Click Edit and then click *Add environment variable*
   key            Value
- `ITEMS_TABLE`: `FindersKeeper-Items`
- `MESSAGES_TABLE`: `FindersKeeper-Messages`
- `IMAGE_BUCKET`: `your-image-bucket-name` (replace with your actuall bucket name)

**Functions needing environment variables:**
- `FindersKeeper-GetItems`: ITEMS_TABLE
- `FindersKeeper-CreateItem`: ITEMS_TABLE, IMAGE_BUCKET
- `FindersKeeper-DeleteItem`: ITEMS_TABLE
- `update_item`: ITEMS_TABLE
- `FindersKeeper-GetMessages`: MESSAGES_TABLE
- `FindersKeeper-SendContact`: ITEMS_TABLE, MESSAGES_TABLE
- `FindersKeeper-SendReply`: MESSAGES_TABLE, ITEMS_TABLE

#### 4.4 Configure Post Confirmation Trigger

1. Go back to your Cognito User Pool
   in the left side bar Click on *Extentions* in *Authentication*
2. Click **Add Lambda trigger**
3. **Trigger type**: Sign-up
4. **Sign-up**: Post confirmation trigger
5. **Lambda function**: Select `FindersKeeper-PostConfirmation`
6. Click **Add Lambda trigger**






### Step 5: Create API Gateway

#### 5.1 Create REST API

1. Navigate to **API Gateway** in the AWS Console
2. Click **Create API**
3. Choose **REST API** (not private)
4. Click **Build**
5. **API name**: `FindersKeeper-API`
6. **Description**: `API for Finder's Keeper application`
7. **Endpoint Type**: Regional
8. Click **Create API**

#### 5.2 Create Cognito Authorizer

1. In your API, click **Authorizers**
2. Click **Create a Authorizer**
3. Configure:
   - **Name**: `FindersKeeper-CognitoAuth`
   - **Type**: Cognito
   - **Cognito User Pool**: Select your user pool
   - **Token Source**: Authorization
4. Click **Create authorizer**

#### 5.3 Import API from Swagger
 **Important**: Before importing, update these values in the JSON:      *FindersKeeper-API-prod-swagger-apigateway.json* that you can find in our project directory
   - Replace all the strings `arn:aws:lambda:us-east-1:258707291570:function:` with your account's Lambda ARN prefix
   'arn:aws:lambda:us-east-1:{Your Account ID}:function:'
   You can find your account id on the top right corner of the AWS console (without dashes)

   - Replace `arn:aws:cognito-idp:us-east-1:258707291570:userpool/us-east-1_kfNTDWsQD` with your User Pool ARN
   You can get the Userpool ARN :
   Navigate to Amazon Cognito select User Pools then select you user pool (FindersKeeper-UserPool) you can find the ARN in the *User pool information* 
   go back to API Gateway 
   in the left side bar click APIs 
   Click on FindersKeeper-API 

1. click **API Actions** → **Import API**
   select Overwrite in Import mode
   Click on Choose file and then select *FindersKeeper-API-prod-swagger-apigateway.json* inside our project folder 
5. Click **Import**

#### 5.4 Update Lambda Handlers

**Before deploying the API**, update the Lambda handlers:

Navigate to lambda on your Console
in left side bar click on Functions
For each Function do:
click in the function
Click on Code
Scroll down Click Edit in Runtime settings tap 
change the Handler for each function from the list below:

| Function Name | Handler |
|-----------|--------------|
| `FindersKeeper-PostConfirmation` | post_confirmation.lambda_handler |
| `FindersKeeper-GetItems` | get_items.fetch_paginated_lost_and_found_items_with_filters |
| `FindersKeeper-CreateItem` | create_item.create_new_lost_or_found_item_with_image_upload |
| `FindersKeeper-DeleteItem` | delete_item.delete_lost_or_found_item_with_ownership_validation |
| `update_item` | update_item.mark_item_as_resolved_or_active_with_ownership_check |
| `FindersKeeper-GetMessages` | get_messages.lambda_handler |
| `FindersKeeper-SendContact` | send_contact.lambda_handler |
| `FindersKeeper-SendReply` | send_reply.send_reply_message_in_existing_conversation_thread |
| `FindersKeeper-ListUsers` | list_users.retrieve_all_cognito_users_for_admin_panel |
| `UpdateUserStatus` | update_user_status.block_or_unblock_cognito_user_account |

#### 5.5 Deploy API

1. Go back to **API Gateway** in the AWS Console
2. Select your **FindersKeeper-API**
3. Click **Deploy API** button (not Actions → Deploy)
4. **Deployment stage**: Select `prod` from dropdown
5. Click **Deploy**
6. **IMPORTANT: Copy the Invoke URL** - you'll need this for frontend configuration
   - It looks like: `https://xxxxxx.execute-api.us-east-1.amazonaws.com/prod`

#### 5.6 Configure Lambda Permissions (CRITICAL STEP)

**This step is required for API Gateway to invoke your Lambda functions. Skipping this will cause 500 errors.**

For **EACH** of the following Lambda functions, add API Gateway invoke permission:

**Functions to configure:**
- FindersKeeper-CreateItem
- FindersKeeper-GetItems
- FindersKeeper-DeleteItem
- update_item
- FindersKeeper-GetMessages
- FindersKeeper-SendContact
- FindersKeeper-SendReply
- FindersKeeper-ListUsers
- UpdateUserStatus

**For each function, do the following:**

1. Navigate to **Lambda** in the AWS Console
2. Click on the function name
3. Go to **Configuration** tab → **Permissions**
4. Scroll down to **Resource-based policy statements**
5. Click **Add permissions**
6. Configure the permission:
   - **Select**: AWS service
   - **Service**: API Gateway
   - **Statement ID**: `apigateway-invoke-[functionname]` (make it unique for each function)
     - Example: `apigateway-invoke-createitem` for FindersKeeper-CreateItem
   - **Principal**: `apigateway.amazonaws.com`
   - **Action**: `lambda:InvokeFunction`
   - **Source ARN**: `arn:aws:execute-api:us-east-1:YOUR-ACCOUNT-ID:YOUR-API-ID/*/*`
     - Replace `YOUR-ACCOUNT-ID` with your AWS account ID (find it in top-right corner)
     - Replace `YOUR-API-ID` with your API Gateway ID (from the Invoke URL, e.g., `f4xkprb6xe`)
     - Example: `arn:aws:execute-api:us-east-1:123456789012:abc123xyz/*/*/*`
7. Click **Save**

**Repeat this process for all 9 functions listed above.**

**Note**: If you skip this step, you'll get "500 Internal Server Error" when trying to use the application.



### Step 6: Configure Frontend

#### 6.1 Update Configuration

1. Open `frontend/aws-config.js` in our project directory
2. Update these values with your actual AWS resources:

```javascript
const AWS_CONFIG = {
    region: 'us-east-1', // Your AWS region
    
    // Replace with your API Gateway invoke URL
    API_GW_BASE_URL_STR: 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod', //That we noted in step 5.4
    
    // Replace with your Cognito domain
    COGNITO_LOGIN_BASE_URL_STR: 'https://YOUR-USER-POOL-ID.auth.us-east-1.amazoncognito.com',
    //You can get the Userpool ID :
   //Navigate to Amazon Cognito select User Pools then select you user pool (FindersKeeper-UserPool) you can find the ARN in the *User pool information* 
    cognito: {
        userPoolId: 'YOUR-USER-POOL-ID',           // e.g., 'us-east-1_XXXXXXXXX'
        clientId: 'YOUR-CLIENT-ID',                 // client ID you can find in Coginto -> App clients under App client information tab
        identityPoolId: null     // Keep as null for AWS Academy
    },
    
    s3: {
        bucketName: 'YOUR-IMAGE-BUCKET-NAME', //Your images bucket name
        region: 'us-east-1'
    },
    
    api: {
        endpoint: 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod',//That we noted in step 5.4
        // ... rest of the configuration
    }
};
```

#### 6.2 Upload Frontend Files

1. Upload all files from the `frontend` directory to your frontend S3 bucket

Navigate to s3 
select your fronend bucket
Click Upload button
Click Add files
and select all the frontend files from our project directory
Click Upload 

note:if you want an admin in your project, he have to be added manually.

### Step 7: Create Admin User

#### 7.1 Register Admin User

1. Visit your frontend website URL (S3 static website endpoint)
2. Register a new account with your email
3. Verify your email address

#### 7.2 Add User to Admins Group

1. Go to **Cognito User Pools** → Your User Pool → **Users**
2. Find your user and click on it
3. **Group memberships** → **Add user to group**
4. Select **Admins** group
5. Click **Add**

## Configuration Reference

### Environment Variables

**Lambda Functions:**
- `ITEMS_TABLE`: DynamoDB table name for items
- `MESSAGES_TABLE`: DynamoDB table name for messages  
- `IMAGE_BUCKET`: S3 bucket name for image storage

**Frontend Configuration:**
- `API_GW_BASE_URL_STR`: API Gateway base URL
- `COGNITO_LOGIN_BASE_URL_STR`: Cognito hosted UI URL
- `userPoolId`: Cognito User Pool ID
- `clientId`: Cognito App Client ID
- `bucketName`: S3 bucket for images

### AWS Resources Created

1. **DynamoDB Tables:**
   - `FindersKeeper-Items`
   - `FindersKeeper-Messages` (with RecipientIndex GSI)

2. **S3 Buckets:**
   - Image storage bucket (public read)
   - Frontend hosting bucket (public read)

3. **Cognito User Pool:**
   - User pool with email verification
   - Two groups: Users, Admins
   - App client for web application

4. **Lambda Functions:**
   - 10 functions for various API operations
   - Post-confirmation trigger for user group assignment

5. **API Gateway:**
   - REST API with Cognito authorization
   - Multiple endpoints for CRUD operations

6. **IAM Role:**
   - Lambda execution role with necessary permissions

## Troubleshooting

### Common Issues

1. **500 Internal Server Error - "Invalid permissions on Lambda function"**
   - **Cause**: API Gateway doesn't have permission to invoke Lambda
   - **Solution**: Go to Step 5.6 and add permissions for ALL Lambda functions
   - **How to verify**: Check Lambda → Configuration → Permissions → Resource-based policy statements should show apigateway.amazonaws.com

2. **500 Internal Server Error - Lambda timeout**
   - **Cause**: Lambda function runs out of time (default 3 seconds)
   - **Solution**: Increase timeout to 30 seconds for CreateItem, SendContact, and SendReply functions
   - **How to fix**: Lambda → Configuration → General configuration → Edit → Change Timeout to 30 seconds

3. **API returns 500 but no Lambda logs appear**
   - **Cause**: API Gateway can't invoke Lambda (permission issue)
   - **Solution**: Complete Step 5.6 for all functions
   
4. **CORS Errors**: Ensure API Gateway has proper CORS configuration and is deployed to prod stage

5. **Cognito Issues**: Check user pool configuration and triggers

6. **S3 Access**: Ensure bucket policies allow public read access

### Monitoring

- **CloudWatch Logs**: Monitor Lambda function execution
- **API Gateway Logs**: Enable logging for API requests
- **DynamoDB Metrics**: Monitor read/write capacity
- **S3 Access Logs**: Track file access patterns

### Security Considerations

1. **API Security**: All sensitive endpoints require Cognito authentication
2. **Data Validation**: Lambda functions validate all input data
3. **Image Upload**: Files are validated and stored securely in S3
4. **User Management**: Admin functions are restricted to Admins group
5. **HTTPS Only**: All API calls use HTTPS encryption

## Support

For issues or questions:
1. Check AWS CloudWatch logs for error details
2. Verify all configuration values are correct
3. Ensure all AWS resources are in the same region
4. Test individual components (Lambda, API Gateway, Cognito) separately

## Cost Optimization

- Use DynamoDB On-Demand billing for variable workloads
- Enable S3 Intelligent Tiering for cost optimization
- Monitor Lambda execution time and memory usage
- Consider API Gateway caching for frequently accessed endpoints

---

**Note**: This installation guide assumes you're using AWS Academy Learner Lab or a similar environment. Some features like SES (Simple Email Service) may be restricted, so the application uses SNS for notifications instead.