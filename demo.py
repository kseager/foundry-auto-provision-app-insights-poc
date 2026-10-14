"""Create a Foundry project with default Application Insights."""

import argparse
import json
import os
from typing import Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient


def _value(argument: Optional[str], environment_name: str) -> str:
    value = argument or os.environ.get(environment_name)
    if not value:
        raise SystemExit(
            f"Provide --{environment_name.lower().replace('_', '-')} or set {environment_name}."
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a Foundry project and automatically provision its Application Insights connection."
    )
    parser.add_argument("--subscription-id")
    parser.add_argument("--resource-group")
    parser.add_argument("--location")
    parser.add_argument("--account-name")
    parser.add_argument("--project-name")
    parser.add_argument(
        "--auth",
        choices=("api_key", "project_managed_identity"),
        help="Defaults to APP_INSIGHTS_AUTH or api_key.",
    )
    parser.add_argument("--workspace-name")
    parser.add_argument("--app-insights-name")
    return parser


def main() -> None:
    args = _parser().parse_args()
    subscription_id = _value(args.subscription_id, "AZURE_SUBSCRIPTION_ID")
    resource_group = _value(args.resource_group, "AZURE_RESOURCE_GROUP")
    location = _value(args.location, "AZURE_LOCATION")
    account_name = _value(args.account_name, "FOUNDRY_ACCOUNT_NAME")
    project_name = _value(args.project_name, "FOUNDRY_PROJECT_NAME")
    workspace_name = _value(args.workspace_name, "LOG_ANALYTICS_WORKSPACE_NAME")
    app_insights_name = _value(args.app_insights_name, "APP_INSIGHTS_NAME")
    auth_mode = args.auth or os.environ.get("APP_INSIGHTS_AUTH", "api_key")

    credential = DefaultAzureCredential()
    client = CognitiveServicesManagementClient(credential, subscription_id)

    try:
        account = client.accounts.get(resource_group, account_name)
        account_status = "reused"
    except ResourceNotFoundError:
        account = client.accounts.begin_create(
            resource_group_name=resource_group,
            account_name=account_name,
            account={
                "identity": {"type": "SystemAssigned"},
                "kind": "AIServices",
                "location": location,
                "properties": {
                    "allowProjectManagement": True,
                    "customSubDomainName": account_name,
                },
                "sku": {"name": "S0"},
            },
        ).result()
        account_status = "created"

    print(json.dumps({"stage": "account", "status": account_status, "id": account.id}))

    project = client.projects.create_with_default_app_insights(
        resource_group_name=resource_group,
        account_name=account_name,
        project_name=project_name,
        project={
            "identity": {"type": "SystemAssigned"},
            "location": location,
            "properties": {
                "description": f"Application Insights SDK POC ({auth_mode})",
                "displayName": project_name,
            },
        },
        app_insights_auth=auth_mode,
        log_analytics_workspace_name=workspace_name,
        app_insights_name=app_insights_name,
    )

    print(
        json.dumps(
            {
                "stage": "project",
                "authMode": auth_mode,
                "projectId": project.id,
                "projectPrincipalId": getattr(project.identity, "principal_id", None),
                "workspaceName": workspace_name,
                "appInsightsName": app_insights_name,
            },
            indent=2,
        )
    )
    print("Run verify.py with the same arguments or environment variables for non-secret verification.")


if __name__ == "__main__":
    main()
