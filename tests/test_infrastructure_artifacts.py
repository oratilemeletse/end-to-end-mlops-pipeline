"""Offline contracts for deployment bundle generation with a stub Azure CLI."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_deployment.ps1"
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell 7 is required")


def prepare_bundle(
    output: Path, *, fail_build: bool = False, parameter_environment: str = "dev"
) -> subprocess.CompletedProcess[str]:
    harness = r"""
$ErrorActionPreference = 'Stop'
function global:az {
    $global:LASTEXITCODE = 0
    if ($env:TEST_FAIL_BUILD -eq '1') {
        $global:LASTEXITCODE = 7
        return
    }
    if ($args[1] -eq 'build') {
        $index = [Array]::IndexOf($args, '--outfile')
        Set-Content -LiteralPath $args[$index + 1] -Value '{}'
    } elseif ($args[1] -eq 'build-params') {
        $parameters = @{
            parameters = @{
                environmentName = @{ value = $env:TEST_PARAMETER_ENVIRONMENT }
                location = @{ value = 'southafricanorth' }
                maxComputeNodes = @{ value = 2 }
                computeVmSize = @{ value = 'Standard_DS3_v2' }
            }
        } | ConvertTo-Json -Depth 10
        @{ parametersJson = $parameters } | ConvertTo-Json -Depth 10
    } else {
        throw "Unexpected Azure operation: $args"
    }
}
& $env:TEST_SCRIPT -GitHubRepository 'owner/repository' `
    -GitHubFederatedSubject 'repo:owner/repository:environment:dev' `
    -OutputDirectory $env:TEST_OUTPUT
"""
    assert PWSH is not None
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", harness],
        env={
            **os.environ,
            "TEST_SCRIPT": str(SCRIPT),
            "TEST_OUTPUT": str(output),
            "TEST_FAIL_BUILD": "1" if fail_build else "0",
            "TEST_PARAMETER_ENVIRONMENT": parameter_environment,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_bundle_preserves_environment_and_oidc_inputs(tmp_path: Path) -> None:
    result = prepare_bundle(tmp_path)
    assert result.returncode == 0, result.stderr
    assert {path.name for path in tmp_path.iterdir()} == {
        "subscription.template.json",
        "resource-group.template.json",
        "subscription.parameters.json",
        "resource-group.parameters.json",
    }
    subscription = json.loads(
        (tmp_path / "subscription.parameters.json").read_text(encoding="utf-8-sig")
    )
    group = json.loads(
        (tmp_path / "resource-group.parameters.json").read_text(encoding="utf-8-sig")
    )
    assert subscription == group
    assert subscription["parameters"] == {
        "environmentName": {"value": "dev"},
        "location": {"value": "southafricanorth"},
        "maxComputeNodes": {"value": 2},
        "computeVmSize": {"value": "Standard_DS3_v2"},
        "githubRepository": {"value": "owner/repository"},
        "githubEnvironment": {"value": "dev"},
        "githubFederatedSubject": {"value": "repo:owner/repository:environment:dev"},
    }
    assert "No Azure resources were provisioned" in result.stdout


def test_bundle_fails_explicitly_when_compilation_fails(tmp_path: Path) -> None:
    result = prepare_bundle(tmp_path, fail_build=True)
    assert result.returncode != 0
    assert "Azure CLI failed with exit code 7" in result.stderr
    assert not (tmp_path / "subscription.parameters.json").exists()


def test_bundle_rejects_environment_mismatch(tmp_path: Path) -> None:
    result = prepare_bundle(tmp_path, parameter_environment="production")
    assert result.returncode != 0
    assert "does not match the requested environment" in result.stderr
    assert not (tmp_path / "subscription.parameters.json").exists()
