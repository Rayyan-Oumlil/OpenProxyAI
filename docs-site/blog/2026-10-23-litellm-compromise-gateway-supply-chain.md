---
slug: litellm-v1107-compromise-gateway-supply-chain
title: "The LiteLLM 1.107.0 compromise: what every AI gateway owner should check"
tags: [security, engineering]
description: On October 21 a malicious litellm 1.107.0 was live on PyPI for about two hours. A gateway holds every provider key you own, so an install-time compromise is the worst case. What happened, and a checklist for any gateway.
---

On October 21, 2026, a malicious `litellm==1.107.0` was on PyPI for about two hours. It stole credentials. LiteLLM is a widely used library for calling model providers, and a gateway is the one place where every provider key and every prompt meet. So an install-time compromise of a gateway is the worst case. This post covers what happened, and what to check on whatever gateway you run.

{/* truncate */}

## What happened

Everything below is from LiteLLM's own incident and root-cause posts.

- **Window.** Malicious wheels for `litellm==1.107.0` were on PyPI from 11:39 to 13:23 UTC. Docker images tagged `v1.107.0`, `latest`, `main-latest` and `main-stable` pointed at a compromised build from 11:46 to as late as 14:20 UTC.
- **Who was exposed.** Anyone who installed or ran 1.107.0, or pulled those image tags, in that window. Previous versions were not affected.
- **What it did.** The package added files that run whenever Python starts in the environment, including `cook.pth` and `sitecustomize.py`, even if the application never imports LiteLLM. It collected credentials and loaded remote-execution tooling.
- **What it was not.** The official `v1.107.0` tag on GitHub did not contain the malicious files. The compromised artifacts were built from an attacker-controlled look-alike repository, so reading the project's source would not have shown a problem.

![A six-step chain: an admin key committed to a public repository on May 27; used on October 10 to read an internal service that returned an organization owner's GitHub token; used to exfiltrate CI secrets; the release workflow repointed on October 21 to a look-alike fork; two stolen identities trigger and approve the release; malicious wheels live on PyPI for about two hours.](/img/blog/litellm-attack-chain.svg)

### How it happened

LiteLLM's root-cause write-up traces it to ordinary operational gaps rather than a flaw in the gateway's code:

1. On May 27 an administrative key for an internal, experimental service was committed to a public repository. A follow-up commit deleted the file, but the key was never revoked, so it still worked more than four months later.
2. On October 10 that key was used to read the service's API, which returned the GitHub CLI token of an organization owner. Those tokens are not scoped to a repository.
3. With it, the attacker ran throwaway CI workflows that posted repository secrets to an outside endpoint, picking up two more maintainers' tokens.
4. On October 21 the release workflow was changed to accept a different source repository, overriding branch protection with the owner's token. A release was triggered and approved with two other stolen identities, which kept the audit log looking routine.

The lesson LiteLLM draws is plain: a leaked key that is not rotated stays dangerous, and protections that one token can override are not protections. A March 2026 incident, in which versions 1.82.7 and 1.82.8 were published after a compromised scanner in CI, makes this the second this year.

## Why a gateway is the worst place for this

A gateway is a credential concentrator. By design it holds the provider keys for every model your company pays for, sits in front of every application, and can read every prompt. LiteLLM's guidance for affected hosts shows the scale: rotate the instance's cloud role, every provider key stored in the proxy's database, the master and virtual keys, the database password, and anything in the environment of any process on the host. An install-time compromise of the gateway is everything at once.

## How a gateway can limit the damage

No gateway can promise that a compromised host exposes nothing. The goal is a smaller blast radius, and that comes from design choices made before an incident. These are the ones OpenProxyAI makes:

- **Keys do not have to live in the gateway at all.** A provider key can point at a secret in HashiCorp Vault or AWS Secrets Manager. The gateway then holds no stored copy: it reads the key when a request needs it and keeps it in memory briefly. See [provider keys from Vault](/guides/secrets-from-vault).
- **Keys are never shown back.** The console lists a key by its prefix only, and application keys are stored as hashes.
- **Replacing a key is a short, practiced path.** Create the new provider key, check it serves traffic, then switch the old one off. A leaked application key is revoked with one call.
- **Outbound requests that an admin or an identity provider can steer only go to public addresses**, so a stolen admin session cannot be used to point the gateway at your internal network.
- **Self-hosted means you choose the supply chain.** You decide which release to run, when to adopt it, and from which registry. There is no vendor update that lands on your gateway without you.

![The OpenProxyAI provider keys page: one OpenAI key listed with its alias, region, maximum data class, a key prefix, weight, circuit state and status. The full key is not shown.](/img/blog/console-provider-keys.png)

## A checklist for any gateway

Use this on whatever you run today.

1. **Pin exactly, and pin the hash.** `pip install --require-hashes -r requirements.txt` refuses anything whose hash differs. In containers, pin the image by digest, not by tag. A tag like `latest` is a pointer that someone else moves, and it was one of the compromised pointers.
2. **Add a cooling-off period for new releases.** Most malicious releases are caught within hours. Tools such as `uv` can refuse packages published after a chosen date (`--exclude-newer`), so you adopt a release a few days after it ships, not minutes.
3. **Build from source you have read, in a pipeline you control.** The compromised wheels did not match the official source tag. Compare what you install with what you reviewed.
4. **Limit what a compromised process can reach.** Give the gateway's cloud role only the secrets it needs. Restrict its outbound network to the provider endpoints you use, so stolen data has nowhere to go.
5. **Keep provider keys out of the gateway's database if you can.** Use Vault or a cloud secrets manager, scoped per organization.
6. **Rehearse replacing keys.** Know which of your keys the gateway can reach, how long it takes to rotate each, and who does it. LiteLLM's own incident started with a key nobody rotated.
7. **If you ran an affected version, do not start with `pip install`.** Any Python start in the environment runs the malicious startup files again, including pip. Delete them first, then reinstall a known-good pinned version, ideally in a rebuilt environment.

## Sources

- [LiteLLM: Contained, October 21, 2026 release v1.107.0 compromised](https://docs.litellm.ai/blog/security-incident-oct-21-2026), including affected artifacts, windows and remediation steps.
- [LiteLLM: The attack chain behind the v1.107.0 release](https://docs.litellm.ai/blog/security-incident-oct-21-2026-attack-chain), the root-cause write-up and timeline (October 23).
- [Datadog Security Labs: LiteLLM supply chain compromise](https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-docker/), independent analysis of the PyPI and Docker artifacts.
- [Help Net Security: LiteLLM hit by second supply chain attack this year](https://www.helpnetsecurity.com/2026/10/22/litellm-compromised-supply-chain-attack-pypi-docker/), coverage of the incident and the earlier one.
- [BerriAI/litellm issue 24518](https://github.com/BerriAI/litellm/issues/24518), the timeline for the March 2026 incident.

Facts about LiteLLM's incident come from LiteLLM's own posts as of October 30, 2026; details can still be updated. Statements about OpenProxyAI describe its shipped behavior.
