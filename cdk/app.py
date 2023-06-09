#!/usr/bin/env python3

import os
import aws_cdk as cdk
from aws_cdk import (
    RemovalPolicy,
    aws_s3 as s3,
    aws_ssm as ssm,
    aws_route53 as route53,
    aws_cloudfront as cloudfront,
    aws_certificatemanager as acm,
    aws_cloudfront_origins as origins,
    aws_route53_targets as targets,
    aws_s3_deployment as s3deploy,
)


class WebsiteStack(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack_vars = self.node.try_get_context("stacks")[cdk.Stack.of(self).stack_name]

        # Buckets
        apex_bucket_name = stack_vars["apex_bucket_name"]
        apex_bucket = s3.Bucket(
            self,
            "ApexBucket",
            bucket_name=apex_bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Not needed due to CloudFront but reserving the bucket name
        www_bucket_name = stack_vars["www_bucket_name"]
        s3.Bucket(
            self,
            "WwwBucket",
            bucket_name=www_bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            website_redirect=s3.RedirectTarget(host_name="winstanley.au"),
        )

        # DNS
        hosted_zone_id_parameter = stack_vars["hosted_zone_id_parameter"]
        hosted_zone_id = ssm.StringParameter.value_for_string_parameter(
            self, hosted_zone_id_parameter
        )
        hosted_zone_name = stack_vars["hosted_zone_name"]

        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
            self,
            "HostedZone",
            zone_name=hosted_zone_name,
            hosted_zone_id=hosted_zone_id,
        )

        # Cloudfront
        cert_arn_parameter = stack_vars["cert_arn_parameter"]
        cert_arn = ssm.StringParameter.value_for_string_parameter(
            self, cert_arn_parameter
        )
        certificate = acm.Certificate.from_certificate_arn(
            self, "Certificate", certificate_arn=cert_arn
        )

        cloudfront_domain_names = stack_vars["cloudfront_domain_names"]

        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, "OriginAccessIdentity"
        )

        apex_bucket.grant_read(origin_access_identity)

        index_function_code = cloudfront.FunctionCode.from_file(
            file_path="cloudfront/index_function.js"
        )
        index_function = cloudfront.Function(
            self, "IndexFunction", code=index_function_code
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    bucket=apex_bucket, origin_access_identity=origin_access_identity
                ),
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=index_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            domain_names=cloudfront_domain_names,
            certificate=certificate,
            default_root_object="index.html",
        )

        # DNS
        route53.RecordSet(
            self,
            "AliasRecordApex",
            record_type=route53.RecordType.A,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution=distribution)
            ),
            zone=hosted_zone,
        )

        route53.RecordSet(
            self,
            "AliasRecordWww",
            record_type=route53.RecordType.A,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution=distribution)
            ),
            zone=hosted_zone,
            record_name="www",
        )

        # Bucket Deployment
        website_content_directory = stack_vars["website_content_directory"]
        s3deploy.BucketDeployment(
            self,
            "BucketDeployment",
            destination_bucket=apex_bucket,
            sources=[s3deploy.Source.asset(website_content_directory)],
        )


# Creates a certificate in us-east-1 for Cloudfront to use
class AcmStack(cdk.Stack):
    def __init__(self, scope: cdk.App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack_vars = self.node.try_get_context("stacks")[cdk.Stack.of(self).stack_name]

        # DNS
        hosted_zone_id_parameter = stack_vars["hosted_zone_id_parameter"]
        hosted_zone_id = ssm.StringParameter.value_for_string_parameter(
            self, hosted_zone_id_parameter
        )

        hosted_zone = route53.HostedZone.from_hosted_zone_id(
            self, "HostedZone", hosted_zone_id=hosted_zone_id
        )

        # ACM
        cert_domain_name = stack_vars["cert_domain_name"]
        cert_alternative_names = stack_vars["cert_alternative_names"]

        acm.Certificate(
            self,
            "WinAuCert",
            domain_name=cert_domain_name,
            subject_alternative_names=cert_alternative_names,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )


app = cdk.App()

syd_env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"], region="ap-southeast-2"
)

usa_env = cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region="us-east-1")

AcmStack(app, "winstanley-au-prod-usa", env=usa_env)
WebsiteStack(app, "winstanley-au-prod", env=syd_env)

app.synth()
