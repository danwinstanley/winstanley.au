# S3 Website Deployment with Cloudfront CDN

This stack will deploy a website to S3 with a Cloudfront CDN.

The initial steps are a little awkward as you need to create a certificate in `us-east-1` for Cloudfront, but it isn't too bad.

## Steps

- This assumes you already have a hosted zone set up in Route 53.  

- Manually add your hosted zone ID to SSM parameter store in _all regions_ you are using plus `us-east-1`

- Add the parameter name to `hosted_zone_id_parameter` in `cdk.json` along with the hosted zone name and certificate details.  
 
- Deploy the ACM stack first and save the certificate ARN to Parameter Store manually.  
  - `cdk deploy acm-stack-name`  

- Populate the `cert_arn_parameter` parameter in `cdk.json` with the name of your cert ARN parameter.  

- Fill in the rest of the details in `cdk.json` using the existing values as a guide.  

- Deploy your the website stack and you are done!
  - `cdk deploy website-stack-name`
