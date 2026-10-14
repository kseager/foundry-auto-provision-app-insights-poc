# Foundry Auto-Provision Application Insights POC

This public proof of concept demonstrates one Python management SDK call that:

1. Creates or updates a Microsoft Foundry project.
2. Waits for the project backend workspace to finish provisioning.
3. Creates or reuses a Log Analytics workspace.
4. Creates or reuses workspace-based Application Insights.
5. Connects Application Insights to the project.

The POC supports:

- `api_key`: current create-project UI parity. The SDK handles the generated
  Application Insights connection string internally.
- `project_managed_identity`: disables Application Insights local auth, assigns
  Monitoring Metrics Publisher to the project identity, and creates a
  Project Managed Identity connection.

This is an Ignite bridge while AccountRP/GSO takes permanent ownership. It is
not a proposal for long-term Python-only lifecycle management.

## Pinned Prototype

`requirements.txt` installs this exact Azure SDK prototype commit:

```text
d7960c60f8aaffc4def7333c4df42aab8b58fdac
```

The demo imports `CognitiveServicesManagementClient` normally. No provisioning
logic is copied from the SDK branch.

## Prerequisites

- Python 3.10 or later.
- Git, because pip installs the pinned SDK commit from GitHub.
- Azure CLI sign-in or another credential supported by
  `DefaultAzureCredential`.
- An existing resource group.
- Permission to create:
  - `Microsoft.CognitiveServices/accounts` and child projects.
  - `Microsoft.OperationalInsights/workspaces`.
  - `Microsoft.Insights/components`.
  - Project connections.
- PMI mode additionally requires
  `Microsoft.Authorization/roleAssignments/write` at the Application Insights
  scope.

The live POC succeeded in **West US 2**. Region selection matters because
Foundry project provisioning currently has a hidden Azure AI Search serverless
dependency.

## Setup

```powershell
git clone https://github.com/kseager/foundry-auto-provision-app-insights-poc.git
Set-Location foundry-auto-provision-app-insights-poc
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
az login
```

Copy `.env.example` to `.env` as a local reference, then set the variables in
your shell. The scripts intentionally do not load `.env`, so credentials and
environment values are never read from a file implicitly.

```powershell
$env:AZURE_SUBSCRIPTION_ID="<subscription-id>"
$env:AZURE_RESOURCE_GROUP="<resource-group>"
$env:AZURE_LOCATION="westus2"
$env:FOUNDRY_ACCOUNT_NAME="<globally-unique-account-name>"
$env:FOUNDRY_PROJECT_NAME="<project-name>"
$env:APP_INSIGHTS_AUTH="api_key"
$env:LOG_ANALYTICS_WORKSPACE_NAME="<workspace-name>"
$env:APP_INSIGHTS_NAME="<app-insights-name>"
```

## Run API Key Mode

```powershell
.\.venv\Scripts\python.exe .\demo.py
.\.venv\Scripts\python.exe .\verify.py
```

Expected verification:

- `connectionAuthType` is `ApiKey`.
- `disableLocalAuth` is `false`.
- `monitoringMetricsPublisherAssignments` is `0`.

The script never prints or returns the Application Insights connection string.

## Run Project Managed Identity Mode

Use a different project, workspace, and Application Insights component because
`DisableLocalAuth` is an Application Insights resource-level setting.

```powershell
$env:FOUNDRY_PROJECT_NAME="<pmi-project-name>"
$env:APP_INSIGHTS_AUTH="project_managed_identity"
$env:LOG_ANALYTICS_WORKSPACE_NAME="<pmi-workspace-name>"
$env:APP_INSIGHTS_NAME="<pmi-app-insights-name>"

.\.venv\Scripts\python.exe .\demo.py
.\.venv\Scripts\python.exe .\verify.py
```

Expected verification:

- `connectionAuthType` is `ProjectManagedIdentity`.
- `disableLocalAuth` is `true`.
- `monitoringMetricsPublisherAssignments` is `1`.

## Idempotency

Run `demo.py` again with the same values. The POC uses:

- ARM create-or-update for Log Analytics and Application Insights.
- A stable project connection name.
- A deterministic Monitoring Metrics Publisher role-assignment UUID.
- Deterministic or explicitly supplied resource names.

The live POC reran both authentication modes without duplicate resources or
role assignments.

## Live Findings

| Route | Result | Finding |
|---|---|---|
| East US 2 | Failed | The hidden AccountRP/CommonHobo deployment requested Azure AI Search `serverless`, which is not available in that region. The public project API returned only `InternalServerError`. |
| Central US | Failed | Search serverless was offered, but the hidden CommonHobo Search deployment reached terminal `Failed` with a generic ARM `Conflict`. |
| West US 2 API Key | Succeeded | Project, Log Analytics, Application Insights, and API Key connection were created and rerun successfully. |
| West US 2 PMI | Succeeded | Project, observability resources, publisher RBAC, disabled local auth, and PMI connection were created and rerun successfully. |

The generated project LRO can finish before the backend project workspace is
ready. The prototype therefore polls the project provisioning state before it
attempts project connection creation.

## Tradeoffs

### Benefits

- Demonstrates UI-equivalent one-call customer ergonomics now.
- Uses the customer's existing `TokenCredential`; it does not create a hidden
  `DefaultAzureCredential` inside the SDK.
- Supports a safer managed-identity comparison path.
- Is isolated in handwritten `_patch.py` customization code and can be removed
  without changing generated REST operations.

### Costs and Risks

- The caller needs cross-provider permissions that a service-owned
  implementation would not expose.
- Cross-provider operations are not atomic. A retry can be required after a
  partial failure.
- Added management SDK dependencies increase installation size and couple the
  Python SDK to provider-specific orchestration.
- Python-only behavior is inconsistent with REST, CLI, JavaScript, and other
  clients.
- Shared account-level resource ownership, concurrent project creation, and
  deletion when the last project is removed are not solved here.
- Hidden Foundry project dependencies make regional and capacity failures
  difficult to diagnose from the public ARM response.

## No Automatic Cleanup

The POC intentionally does not delete resources. This avoids accidental
removal of account-scoped observability resources that another project might
reuse. Review and delete test resources manually when they are no longer
needed.

## Migration

When AccountRP/GSO owns default observability provisioning:

1. Ordinary generated `projects.begin_create` becomes the supported path.
2. The preview convenience method can temporarily delegate to project creation
   without making auxiliary ARM calls.
3. The orchestration helper and temporary management dependencies can then be
   removed.
