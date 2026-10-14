"""Verify non-secret resources created by the Foundry Application Insights POC."""

import argparse
import json
import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.loganalytics import LogAnalyticsManagementClient

_MONITORING_METRICS_PUBLISHER_ROLE_ID = "3913510d-42f4-4e42-8a64-420c390055eb"


def _value(argument: Optional[str], environment_name: str) -> str:
    value = argument or os.environ.get(environment_name)
    if not value:
        raise SystemExit(
            f"Provide --{environment_name.lower().replace('_', '-')} or set {environment_name}."
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the POC without displaying credentials.")
    parser.add_argument("--subscription-id")
    parser.add_argument("--resource-group")
    parser.add_argument("--account-name")
    parser.add_argument("--project-name")
    parser.add_argument("--workspace-name")
    parser.add_argument("--app-insights-name")
    return parser


def main() -> None:
    args = _parser().parse_args()
    subscription_id = _value(args.subscription_id, "AZURE_SUBSCRIPTION_ID")
    resource_group = _value(args.resource_group, "AZURE_RESOURCE_GROUP")
    account_name = _value(args.account_name, "FOUNDRY_ACCOUNT_NAME")
    project_name = _value(args.project_name, "FOUNDRY_PROJECT_NAME")
    workspace_name = _value(args.workspace_name, "LOG_ANALYTICS_WORKSPACE_NAME")
    app_insights_name = _value(args.app_insights_name, "APP_INSIGHTS_NAME")

    credential = DefaultAzureCredential()
    cognitive_client = CognitiveServicesManagementClient(credential, subscription_id)
    project = cognitive_client.projects.get(resource_group, account_name, project_name)
    connection = cognitive_client.project_connections.get(
        resource_group,
        account_name,
        project_name,
        "appinsights",
    )
    workspace = LogAnalyticsManagementClient(credential, subscription_id).workspaces.get(
        resource_group,
        workspace_name,
    )
    component = ApplicationInsightsManagementClient(credential, subscription_id).components.get(
        resource_group,
        app_insights_name,
    )

    principal_id = getattr(project.identity, "principal_id", None)
    publisher_assignments = 0
    if principal_id:
        assignments = AuthorizationManagementClient(
            credential,
            subscription_id,
        ).role_assignments.list_for_scope(component.id)
        publisher_assignments = sum(
            1
            for assignment in assignments
            if assignment.principal_id == principal_id
            and assignment.role_definition_id
            and assignment.role_definition_id.lower().endswith(
                f"/{_MONITORING_METRICS_PUBLISHER_ROLE_ID}"
            )
        )

    print(
        json.dumps(
            {
                "projectId": project.id,
                "projectProvisioningState": str(project.properties.provisioning_state),
                "projectPrincipalId": principal_id,
                "workspaceId": workspace.id,
                "appInsightsId": component.id,
                "disableLocalAuth": component.disable_local_auth,
                "connectionAuthType": str(connection.properties.auth_type),
                "connectionCategory": str(connection.properties.category),
                "connectionTarget": connection.properties.target,
                "monitoringMetricsPublisherAssignments": publisher_assignments,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
