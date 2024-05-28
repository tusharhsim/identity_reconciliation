#Identity Reconciliation Service

## Description
A web service to identify and keep track of a customer's identity across multiple purchases with different contact information.

## Endpoint
### POST /identify
#### Request Body
```json
{
  "email": "example@example.com",
  "phoneNumber": "1234567890"
}
