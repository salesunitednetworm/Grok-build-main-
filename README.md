# Grok Build

This is the isolated builder workspace. It is not Presite. Agents started here scaffold new apps and extend existing ones.

## What this environment is for

- Start Cloud Agents on this repo when you want Grok Build to do the work
- Ask it to create a new app, or to attach to another app you are already building
- Keep Presite, billing, and other products out of this thread unless you explicitly bring them in

## Chief of Staff

Yes — this workspace is meant to sit under a future Chief of Staff.

Chief of Staff is the orchestrator you will build later. Grok Build is a specialist it can assign work to. When that layer exists, it should:

1. Open or reuse a Cloud Agent on this environment
2. Hand over a job that matches `grok-build.contract.json`
3. Collect the result (usually a branch or pull request)

You do not need Chief of Staff running today. The contract is already here so that layer can plug in without rebuilding this environment.

## Attach another app

This environment currently includes only this repository. To have Grok Build work on another app:

- Start a Cloud Agent on that app’s repo, or
- Add that repo to this environment’s repository list in the [environment dashboard](https://cursor.com/dashboard/cloud-agents/environments/e/2764959e-baa2-11f1-977f-f6b8f2fcf9b2)

## Local / Cloud Agent bootstrap

The Cloud Agent install script refreshes the builder toolchain and writes a ready marker. It is safe to run more than once.
