# Voice Prompt Integration

> This guide covers enabling end users to submit AI prompts via voice — mobile apps, push-to-talk hardware, smart speakers, speech-to-text engines, and wearable handsets — while routing all voice-derived text through your OpenProxyAI gateway for security, compliance, and observability.
>
> **All code samples are consolidated in [Appendix C](#appendix-c-code-reference) at the end of this document.**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
   - [Full-Stack Architecture — All Three Phases Combined](#full-stack-architecture--all-three-phases-combined)
   - [The Voice Prompt Pipeline](#the-voice-prompt-pipeline)
2. [Category A: Software-Based Solutions](#2-category-a-software-based-solutions)
   - [A.1 — Commercial Solutions (Easiest)](#a1--commercial-solutions-easiest)
     - [A.1.1 — Smart Speaker & Voice Assistant Integration](#a11--smart-speaker--voice-assistant-integration)
     - [A.1.2 — Commercial Smartphone PTT Apps](#a12--commercial-smartphone-ptt-apps)
     - [A.1.3 — Top Commercial Dictation Systems](#a13--top-commercial-dictation-systems)
     - [A.1.4 — Built-in Mobile Dictation (Zero Development)](#a14--built-in-mobile-dictation-zero-development)
   - [A.2 — Open Source Solutions](#a2--open-source-solutions)
     - [A.2.1 — Open Source Dictation Apps & Whisper-Powered Mobile Apps](#a21--open-source-dictation-apps--whisper-powered-mobile-apps)
     - [A.2.2 — Open Source PTT Communication Servers](#a22--open-source-ptt-communication-servers)
     - [A.2.3 — Open Source Speech-to-Text Engines](#a23--open-source-speech-to-text-engines)
   - [A.3 — Native Platform Development (Android & Apple)](#a3--native-platform-development-android--apple)
     - [A.3.1 — Android Native Voice Integration](#a31--android-native-voice-integration)
     - [A.3.2 — Apple iOS Native Voice Integration](#a32--apple-ios-native-voice-integration)
   - [A.4 — Custom Development from Scratch (SDK & Frameworks)](#a4--custom-development-from-scratch-sdk--frameworks)
3. [Category B: Hardware-Based Solutions](#3-category-b-hardware-based-solutions)
   - [B.1 — LTE / Wi-Fi PTT Radios (Hybrid Devices)](#b1--lte--wi-fi-ptt-radios-hybrid-devices)
   - [B.2 — Ruggedized Android PTT Devices](#b2--ruggedized-android-ptt-devices)
   - [B.3 — Wearable Voice Badges (Hands-Free)](#b3--wearable-voice-badges-hands-free)
4. [Speech-to-Text Engine Options](#4-speech-to-text-engine-options)
   - [4.1 — Cloud-Based STT Engines](#41--cloud-based-stt-engines)
   - [4.2 — On-Premise / Open Source STT Engines](#42--on-premise--open-source-stt-engines)
5. [On-Premise vs. Cloud Deployment](#5-on-premise-vs-cloud-deployment)
6. [Decision Matrix](#6-decision-matrix)
7. [Suggested Implementation: Phased Go-to-Market Plan](#7-suggested-implementation-phased-go-to-market-plan)
   - [Phase 1 — Push to Talk (PTT): Controlled Voice Input](#phase-1--push-to-talk-ptt-controlled-voice-input)
   - [Phase 2 — Always Listening Android Assistant: Hands-Free Secure Mobile Voice](#phase-2--always-listening-android-assistant-hands-free-secure-mobile-voice)
   - [Phase 3 — Mobile + Wearables: Eyes-Free, Device-Neutral Voice Platform](#phase-3--mobile--wearables-eyes-free-device-neutral-voice-platform)
8. [Appendix A — Voice API Domain Reference](#appendix-a-voice-api-domain-reference)
9. [Appendix B — Recommended Hardware Vendors](#appendix-b-recommended-hardware-vendors)
10. [Appendix C — Code Reference](#appendix-c-code-reference)

---

## 1. Architecture Overview

### Full-Stack Architecture — All Three Phases Combined

The diagram below shows the complete OpenProxyAI Voice Module as it exists when all three phases are deployed. Each layer is labelled with the phase that introduces it, making it easy to identify what is live at any given point in the rollout.

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                   OPENPROXYAI — VOICE MODULE FULL STACK (3 PHASES)                  ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 1 — VOICE CAPTURE ENDPOINTS                                                   ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────────────┐ ║
║  │   PHASE 1       │  │   PHASE 2       │  │   PHASE 3                            │ ║
║  │ PTT (Mobile)    │  │ Always Listening │  │ Wearables + Ruggedized               │ ║
║  │                 │  │ (Managed Android)│  │                                      │ ║
║  │ • Any Android   │  │ • MDM-enrolled   │  │ Smart Badges    AR Glasses           │ ║
║  │ • Any iOS       │  │   Android phone  │  │  Vocera         RealWear             │ ║
║  │ • PTT button    │  │ • Wake phrase    │  │  Theatro        Vuzix                │ ║
║  │   (soft or HW)  │  │   "OK OpenProxy" │  │                                      │ ║
║  │ • Voice + Photo │  │ • VAD gated      │  │ Rugged Android  PTT Radios           │ ║
║  │                 │  │   recording      │  │  Zebra          Motorola WAVE        │ ║
║  │                 │  │ • Voice + Photo  │  │  Honeywell      Hytera / Inrico      │ ║
║  │                 │  │                  │  │  Sonim                               │ ║
║  │                 │  │                  │  │                                      │ ║
║  │                 │  │                  │  │ Body-Worn       AI Voice Badges      │ ║
║  │                 │  │                  │  │  Huawei EC310   Speakly / VoxAI      │ ║
║  └─────────────────┘  └─────────────────┘  └──────────────────────────────────────┘ ║
║           │                    │                           │                         ║
║           │    PTT press       │   Wake word detected      │  PTT key / wake phrase  ║
║           │    → record        │   → VAD → record          │  → audio via Bluetooth  ║
║           ▼                    ▼                           ▼                         ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 2 — ACTIVATION & AUDIO PIPELINE                                               ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐ ║
║  │  Phase 1: MediaRecorder / AVAudioRecorder (Android / iOS)                       │ ║
║  │           ACTION_DOWN → record │ ACTION_UP → stop                                │ ║
║  │                                                                                   │ ║
║  │  Phase 2: Android Foreground Service                                              │ ║
║  │           Keyword spotting (Porcupine / openWakeWord) → VAD (Silero / WebRTC)    │ ║
║  │           → AudioRecord                                                           │ ║
║  │                                                                                   │ ║
║  │  Phase 3: Wearable mic → Bluetooth A2DP / BLE → Paired Android phone             │ ║
║  │           Phone acts as compute hub and trust anchor                              │ ║
║  └─────────────────────────────────────────────────────────────────────────────────┘ ║
║                                         │                                            ║
║                                         ▼                                            ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 3 — SPEECH-TO-TEXT (STT) ENGINE                                               ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌────────────────────────────┐    ┌─────────────────────────────────────────────┐  ║
║  │  CLOUD STT                 │    │  ON-DEVICE / ON-PREMISE STT                 │  ║
║  │                            │    │                                             │  ║
║  │  • OpenAI Whisper API      │    │  • Whisper.cpp  (offline, on Android)       │  ║
║  │  • Google Cloud STT        │    │  • Vosk         (lightweight, offline)      │  ║
║  │  • Azure Speech Services   │    │  • Faster-Whisper (GPU server)              │  ║
║  │  • Amazon Transcribe       │    │  • NVIDIA Riva  (on-prem GPU cluster)       │  ║
║  │  • Deepgram / AssemblyAI   │    │  • Kaldi / SpeechBrain                     │  ║
║  └────────────────────────────┘    └─────────────────────────────────────────────┘  ║
║                    │                                  │                             ║
║                    └──────────────┬───────────────────┘                             ║
║                                   ▼                                                 ║
║                          Transcript (text)                                           ║
║                                   │                                                 ║
║                                   ▼                                                 ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 4 — PROMPT CONSTRUCTION & CONTEXT                                             ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐ ║
║  │  Phase 1:  Transcript only                                                       │ ║
║  │  Phase 2:  Transcript + user role + device context + multi-turn session history  │ ║
║  │  Phase 3:  Transcript + image (multimodal) + role + device type + location       │ ║
║  │                                                                                   │ ║
║  │  Optional (Phase 3+):  Contextual enrichment — shift, location, wearable type    │ ║
║  └─────────────────────────────────────────────────────────────────────────────────┘ ║
║                                         │                                            ║
║                                         ▼                                            ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 5 — OPENPROXYAI GATEWAY                                                       ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐ ║
║  │                                                                                   │ ║
║  │  AUTHENTICATION (per phase)                                                       │ ║
║  │   Phase 1:  Username / PIN / session token (app-level)                            │ ║
║  │   Phase 2:  Device certificate (MDM-issued) + mTLS                                │ ║
║  │   Phase 3:  Phone cert (trust anchor) + SSO / OIDC + device posture check         │ ║
║  │                                                                                   │ ║
║  │  SECURITY & COMPLIANCE                                                             │ ║
║  │   • PII / DLP scanning    (Microsoft Presidio / AWS Comprehend)                   │ ║
║  │   • Certificate pinning   (prevents MITM)                                         │ ║
║  │   • Role-based routing    (nurse / technician / manager → different AI persona)    │ ║
║  │   • Prompt audit logging  (Langfuse — full trace per interaction)                  │ ║
║  │   • Policy enforcement    (per device type, per user role)                         │ ║
║  │                                                                                   │ ║
║  │  ROUTING                                                                           │ ║
║  │   • Cloud LLM:    OpenAI / Anthropic / Mistral / Google Gemini                    │ ║
║  │   • On-premise:   vLLM / Ollama / LM Studio (air-gapped)                          │ ║
║  └─────────────────────────────────────────────────────────────────────────────────┘ ║
║                                         │                                            ║
║                                         ▼                                            ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 6 — RESPONSE & DELIVERY                                                       ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐ ║
║  │  TEXT response → displayed in app UI                                              │ ║
║  │                                                                                   │ ║
║  │  TTS (Text-to-Speech) → spoken response                                           │ ║
║  │   Phase 1:  Optional     Android TextToSpeech / AVSpeechSynthesizer               │ ║
║  │   Phase 2:  Standard     Google Cloud TTS / Azure Neural TTS / Piper              │ ║
║  │   Phase 3:  Distributed  TTS audio routed to wearable speaker via Bluetooth       │ ║
║  │                          Short text cue pushed to wearable display                │ ║
║  │                                                                                   │ ║
║  │  BARGE-IN (Phase 2+):  User speaks → playback interrupted → new input captured    │ ║
║  └─────────────────────────────────────────────────────────────────────────────────┘ ║
║                                         │                                            ║
║                                         ▼                                            ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  LAYER 7 — OBSERVABILITY & GOVERNANCE                                                ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║                                                                                      ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐ ║
║  │  • Prompt & response audit  →  Langfuse (full trace, all phases)                  │ ║
║  │  • Metrics & alerting       →  Prometheus + Grafana (per device type)             │ ║
║  │  • Cost tracking            →  OpenProxyAI dashboard (per user / team / device)   │ ║
║  │  • SIEM export              →  SOC 2 / HIPAA compliance reporting                 │ ║
║  └─────────────────────────────────────────────────────────────────────────────────┘ ║
║                                                                                      ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║  DEPLOYMENT MODEL (selectable per organisation)                                      ║
║  ─────────────────────────────────────────────────────────────────────────────────   ║
║  Cloud:       STT + Gateway + LLM all cloud-hosted (fastest to deploy)               ║
║  Hybrid:      On-device STT + Cloud gateway + Cloud LLM (Phase 2 default)            ║
║  On-Premise:  Faster-Whisper + OpenProxyAI on-prem + Ollama/vLLM (air-gapped)        ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

**Reading the diagram — what each phase adds:**

| Layer | Phase 1 (PTT) | Phase 2 (Always Listening) | Phase 3 (Mobile + Wearables) |
|---|---|---|---|
| Capture endpoints | Any phone (PTT button) | MDM Android (wake word) | + Wearables, ruggedized, badges, radios |
| Activation | Manual button press | Keyword spotting + VAD | Wake phrase / PTT key → Bluetooth → phone |
| STT | Cloud (Whisper API / Google) | Cloud or on-device | Cloud + on-device offline fallback |
| Prompt | Transcript only | Transcript + session context | Transcript + image + device context |
| Auth | App-level (username / PIN) | Device certificate + mTLS | Phone cert + SSO + posture check |
| TTS response | Optional | Standard + barge-in | Routed to wearable speaker + display |
| Observability | Basic | Session logging | Full audit + per-device metrics |

---

### The Voice Prompt Pipeline

Regardless of the input method, all voice prompts follow the same pipeline before reaching the AI model:

```
Voice Input (microphone / PTT button / smart speaker)
         │
         ▼
Speech-to-Text Engine
  (Whisper / Google STT / Azure Speech / Vosk / etc.)
         │
         ▼
Text Prompt
         │
         ▼
OpenProxyAI Gateway (openproxai.yourdomain.com)
  ├── Security & PII filtering
  ├── Compliance logging
  ├── Policy enforcement
  └── Prompt routing
         │
         ▼
LLM Backend (OpenAI / Anthropic / Mistral / etc.)
         │
         ▼
Text Response → Text-to-Speech (optional)
         │
         ▼
Audio Playback to User
```

### Two Deployment Models

| Model | STT Engine Location | Best For |
|---|---|---|
| **Cloud-based** | Vendor API (OpenAI Whisper API, Google STT, Azure) | Fastest setup, managed scaling |
| **On-premise** | Self-hosted (Whisper, Vosk, Coqui, Kaldi) | Air-gapped, regulated environments |

---

## 2. Category A: Software-Based Solutions

Software-based solutions run entirely on existing devices — smartphones, tablets, desktops, or smart speakers — with no specialized hardware purchase required. They are ordered below **from easiest to hardest** to implement.

| Sub-Category | Methods | Complexity | Deployment | Best For |
|---|---|---|---|---|
| **A.1 — Commercial** | Smart Speakers, Commercial PTT Apps, Built-in Dictation | ⭐ Easiest | Cloud | Fastest time-to-value, no code |
| **A.2 — Open Source** | Mumble, Vosk, Faster-Whisper, Whisper-to-Input | ⭐⭐ Low–Medium | On-premise / Cloud | No licensing cost, self-hosted control |
| **A.3 — Native Platform** | Android Voice APIs, Apple SpeechKit | ⭐⭐⭐ Medium | Cloud / On-premise | Org-branded apps, OS-native experience |
| **A.4 — Custom SDK/Framework** | Full-stack from scratch | ⭐⭐⭐⭐ Hardest | Cloud / On-premise | Maximum control, proprietary pipeline |

---

### A.1 — Commercial Solutions (Easiest)

> **Complexity:** ⭐ Easiest — no development required. Configure an account, point to OpenProxyAI, done.

Commercial solutions come fully built and managed. Integration with OpenProxyAI is limited to a webhook URL or a PAC/DNS redirect. No engineering team is needed for initial deployment.

---

#### A.1.1 — Smart Speaker & Voice Assistant Integration

Route voice queries from Alexa, Google Home, or Siri through OpenProxyAI with minimal configuration.

**Effort:** Register a developer account → deploy a serverless function → point to your OpenProxyAI URL.

**Alexa Skill Flow:**
```
User: "Alexa, ask my AI [prompt]"
         │
         ▼
Alexa STT (Amazon Transcribe — fully managed)
         │
         ▼
Alexa Skill Lambda (Node.js or Python — ~30 lines)
         │
         ▼
POST https://openproxai.yourdomain.com/v1/chat/completions
         │
         ▼
Response text → Alexa TTS → Speaker
```

**Google Home Flow:**
```
User speaks to Google Nest device
         │
         ▼
Google STT (fully managed)
         │
         ▼
Google Cloud Function (~20 lines)
         │
         ▼
POST https://openproxai.yourdomain.com/v1/chat/completions
         │
         ▼
Response → Google TTS → Speaker
```

| Vendor | Product | STT | Setup Time | Code Reference |
|---|---|---|---|---|
| **Amazon** | Echo + Alexa Skills Kit | Amazon Transcribe | ~2 hours | [Appendix C.6](#c6--amazon-alexa-custom-skill-handler-nodejs) |
| **Google** | Nest + Actions on Google | Google STT | ~2 hours | [Appendix C.7](#c7--google-home-conversational-action-pythoncloud-functions) |
| **Apple** | HomePod + App Intents (iOS 17+) | Apple Speech | ~1 day | [Appendix C.13](#c13--apple-siri-app-intents-swift) |

---

#### A.1.2 — Commercial Smartphone PTT Apps

Fully managed PTT apps that run on any Android or iOS device. No server infrastructure required for cloud-hosted tiers. Audio is transcribed and the resulting text is bridged to OpenProxyAI via a webhook.

| App | Platform | Cloud Tier | Self-Hosted Option | Notes |
|---|---|---|---|---|
| **Zello Work** | Android / iOS | Yes (SaaS) | Yes (Zello Work Server) | 150M+ users, enterprise MDM support |
| **Voxer for Business** | Android / iOS | Yes (SaaS) | No | Async voice + live PTT, message history |
| **Microsoft Teams PTT** | Android / iOS | Yes (M365) | No | Built-in if org uses Teams |
| **Motorola WAVE OnCloud** | Android / iOS | Yes (SaaS) | On-prem gateway available | Carrier-grade, used by public safety |
| **RealWear Companion** | Android | Yes | No | Optimized for head-mounted displays |

> See **[Appendix C.11](#c11--zello-work-webhook-bridge-pythonflask)** for the Zello Work → OpenProxyAI webhook bridge.

---

#### A.1.3 — Top Commercial Dictation Systems

Well-known dictation platforms that serve as the STT front-end before forwarding transcribed text to OpenProxyAI.

**1. Google Speech-to-Text (Google Dictation)**

The most widely deployed STT engine in the world — powers Gboard, Android voice input, Google Docs Voice Typing, and the Google Cloud STT API.

| Attribute | Detail |
|---|---|
| Who uses it | Android, Google Docs, Gboard, Chrome, Google Cloud customers |
| Languages | 125+ |
| Streaming | Yes — real-time streaming recognition |
| Mobile | Native on Android via `SpeechRecognizer` API |
| Enterprise API | Google Cloud Speech-to-Text v2 |
| Reference | [cloud.google.com/speech-to-text](https://cloud.google.com/speech-to-text) |

> See **[Appendix C.14](#c14--google-cloud-stt--openproxyai-python)** for the Python integration sample.

**2. Apple Dictation (Siri Dictation)**

Built into every iPhone, iPad, and Mac. On-device model since iOS 15 for English — no audio leaves the device.

| Attribute | Detail |
|---|---|
| Who uses it | iPhone, iPad, Mac users worldwide |
| On-device | Yes (iOS 15+ English, expanding) |
| Privacy | Audio processed locally when on-device model active |
| Integration | Via `SFSpeechRecognizer` — see A.3.2 |
| Reference | [Apple Dictation Documentation](https://support.apple.com/en-us/HT202584) |

**3. Microsoft Dictate / Windows Voice Typing (Azure Speech)**

Built into Microsoft Word, Outlook, OneNote, and Windows 11. Backed by Azure Cognitive Services Speech.

| Attribute | Detail |
|---|---|
| Who uses it | Windows, Microsoft 365, enterprise professionals |
| Products | Word, Outlook, OneNote, Windows Voice Typing |
| API | Azure Cognitive Services Speech |
| Streaming | Yes — real-time + batch |
| Compliance | HIPAA BAA, SOC 2, ISO 27001 available |

> See **[Appendix C.15](#c15--azure-speech--openproxyai-python)** for the Azure Speech integration sample.

**4. Dragon NaturallySpeaking (Nuance / Microsoft)**

The gold standard for professional dictation — especially in healthcare and legal. Highest accuracy after voice training, with industry-specific vocabulary models.

| Attribute | Detail |
|---|---|
| Who uses it | Healthcare, legal, law enforcement, enterprise |
| Accuracy | Highest after voice profile training |
| Domain models | Medical, Legal, Law Enforcement vocabularies |
| On-premise | Dragon Medical One (cloud), Dragon Professional (desktop) |
| Reference | [dragon.nuance.com](https://dragon.nuance.com) |

> **Integration note:** Dragon outputs transcribed text via SDK or clipboard. A lightweight bridge agent intercepts Dragon output and POSTs it to OpenProxyAI — enabling legacy Dragon workflows to benefit from modern LLM responses.

---

#### A.1.4 — Built-in Mobile Dictation (Zero Development)

> **Complexity:** ⭐ Easiest — no app, no server, no code. Uses the dictation already present on every smartphone.

Every Android and iOS device ships with a high-quality dictation engine built into the OS keyboard. The transcribed text is forwarded to OpenProxyAI via a simple submit-button pattern in any app.

##### A.1.4.1 — Android Built-in Dictation

| Method | How to Activate | STT Engine | Online / Offline |
|---|---|---|---|
| **Google Voice Typing** | Tap microphone on any keyboard | Google STT | Online (offline packs available) |
| **Gboard Microphone** | Tap mic icon in Gboard | Google STT | Online (offline packs available) |

**Modes supported:**
- **Press-to-talk:** Tap mic → speak → tap again to stop
- **Continuous dictation:** Speak freely; text inserts in real-time

**Strengths:**
- Zero development — works on every Android device out of the box
- High accuracy — powered by the same Google STT engine as the Cloud API
- Deep OS integration — works in every app, every text field
- Supports 70+ languages with online connectivity

**Limitations:**
- No control over the STT pipeline — limited customization
- Cloud-dependent by default — offline language packs must be installed manually
- No programmatic hook — output goes to the focused text field, not an API directly

**Enable offline language packs:**
```
Settings → General Management → Language → On-device language preferences
  → Download your language for offline dictation
```

> See **[Appendix C.16](#c16--android-built-in-dictation-bridge-kotlin)** for the submit-button bridge pattern (Kotlin).

##### A.1.4.2 — iOS Built-in Dictation (Apple Dictation / Siri Dictation)

| Method | How to Activate | STT Engine | Online / Offline |
|---|---|---|---|
| **Apple Dictation** | Tap mic on iOS keyboard | Apple Speech (Siri) | On-device (iOS 15+ English) |
| **Voice Control** | Settings → Accessibility → Voice Control | Apple Speech | On-device |

**Strengths:**
- Low latency — on-device model eliminates round-trip network time
- Strong privacy controls — audio stays on device for supported languages
- Excellent accessibility support — integrated with VoiceOver and Switch Control
- Works system-wide — any text field in any app

**Limitations:**
- No low-level control — STT pipeline is fully managed by Apple
- Not extensible beyond OS APIs without `SFSpeechRecognizer`
- On-device offline limited to select languages (English, Spanish, French, German, Japanese, Mandarin)

**Enable offline dictation:**
```
Settings → General → Dictation → Enable Dictation
  → "On-Device Dictation" toggle — enables fully offline processing
```

> See **[Appendix C.17](#c17--ios-built-in-dictation-bridge-swiftui)** for the submit-button bridge pattern (SwiftUI).

**Built-in Dictation: Comparison Summary**

| Feature | Android (Google Voice Typing) | iOS (Apple Dictation) |
|---|---|---|
| Setup required | None | None |
| Development required | None | None |
| STT accuracy | ★★★★☆ | ★★★★☆ |
| On-device / offline | Optional (download packs) | Yes (iOS 15+, select languages) |
| Privacy | Audio sent to Google by default | On-device by default (iOS 15+) |
| PTT style | Yes (tap to start/stop) | Yes (tap mic to start/stop) |
| Continuous dictation | Yes | Yes |
| Custom vocabulary | No | No |
| API/webhook output | No (text field only) | No (text field only) |
| Bridge to OpenProxyAI | Via submit button in app | Via submit button in app |

---

### A.2 — Open Source Solutions

> **Complexity:** ⭐⭐ Low–Medium — requires self-hosting a server but minimal or no custom app development.

Open source solutions give full control over your data with no licensing fees. You manage the infrastructure; the community manages the code.

---

#### A.2.1 — Open Source Dictation Apps & Whisper-Powered Mobile Apps

Purpose-built open source Android apps that implement the full PTT → Whisper → OpenProxyAI pipeline with zero custom development.

**1. Whisper-to-Input** ⭐ Most Direct Match
- **GitHub:** [j3soon/whisper-to-input](https://github.com/j3soon/whisper-to-input)
- **Type:** Android IME (keyboard replacement) + standalone app
- **License:** Open Source

**How it works:**
```
PTT tap → Record audio locally
       → POST to OpenAI Whisper API (or self-hosted Whisper endpoint)
       → Transcribed text → Keyboard injection OR programmatic API forwarding
       → POST https://openproxai.yourdomain.com/v1/chat/completions
```

**Configuration (self-hosted Whisper):**
```
App Settings → API Endpoint → http://whisper.internal:9000/asr
App Settings → API Key      → (leave blank for self-hosted)
```

**Strengths:** Zero custom development, supports both cloud and self-hosted Whisper, works as a system keyboard in any app, actively maintained.

**Limitations:** Android only; cloud STT by default; no built-in TTS response playback.

---

**2. FUTO Voice Input**
- **Platform:** Android | **License:** Open Source (FUTO)
- Fully **offline** Whisper-based STT — audio never leaves the device
- Runs Whisper model on-device (tiny/base/small)
- System voice input replacement — replaces Google Voice Typing at OS level
- Press-to-talk UX

**Strengths:** Privacy-first, no cloud dependency, works in air-gapped environments.

**Limitations:** On-device model (tiny/base) is less accurate than cloud Whisper large; Android only.

---

**3. Whisper IME (F-Droid)**
- **Platform:** Android | **Source:** F-Droid open app store
- Press-and-hold recording (true PTT UX)
- Offline Whisper STT — no internet required
- No Google Play dependency — suitable for de-Googled or privacy-hardened devices

**Strengths:** True PTT hold-to-record UX, fully offline, works on hardened/classified devices.

**Limitations:** Smaller community, limited configuration options, Android only.

---

**4. Home Assistant Companion App + Whisper Cloud**
- **GitHub:** [fabio-garavini/ha-openai-whisper-stt-api](https://github.com/fabio-garavini/ha-openai-whisper-stt-api)
- **Type:** Platform solution (mobile app + server pipeline) | **License:** Open Source

**Flow:**
```
Home Assistant Companion App (Android / iOS)
  └── Push-to-talk button
         │
         ▼
Home Assistant Assist Pipeline (self-hosted)
  └── STT: OpenAI Whisper API / Groq / Mistral / self-hosted Whisper (pluggable)
         │
         ▼
OpenProxyAI Gateway (via HA webhook or REST action)
         │
         ▼
LLM response → TTS → Mobile speaker
```

Pluggable STT providers (no app change needed): OpenAI Whisper, Groq, Mistral, Azure, self-hosted Whisper.

> See **[Appendix C.8](#c8--home-assistant--google-cloud-stt-configuration-yaml)** for the Home Assistant YAML configuration.

---

**5. OpenWhispr** *(Reference Architecture)*
- **Website:** [openwhispr.com](https://openwhispr.com)
- Desktop-first (mobile support evolving), open source core
- Hotkey/PTT paradigm, bring your own API keys, routes text to any downstream system
- Best used as a reference design for mobile PTT → Whisper → API architectures

**Quick Selection Guide — Whisper Mobile Apps:**

| Goal | Best Option |
|---|---|
| PTT → Whisper API → text → OpenProxyAI | Whisper-to-Input |
| Offline PTT (audio never leaves device) | FUTO Voice Input |
| Advanced routing + automation pipeline | Home Assistant + Whisper Cloud |
| Press-and-hold, F-Droid privacy-first | Whisper IME (F-Droid) |
| Reference architecture study | OpenWhispr |

---

#### A.2.2 — Open Source PTT Communication Servers

Self-host the PTT channel server; users connect with the free client app on any existing device.

| App | Server | Client | License | Latency | Notes |
|---|---|---|---|---|---|
| **Mumble** | Murmur (C++) | Mumble (all platforms) | BSD | <50ms | Industry standard for low-latency PTT |
| **TeamSpeak** | TeamSpeak Server | TS Client | Proprietary (free tier) | <80ms | Widely adopted, free for <512 users |
| **Jitsi Meet** | Jitsi Server (Docker) | Web / Mobile | Apache 2.0 | ~100ms | WebRTC-based, open video+audio |
| **FreeSWITCH** | FreeSWITCH (C) | SIP client | MPL 2.0 | <50ms | Enterprise telephony + PTT |
| **Asterisk** | Asterisk PBX | Any SIP client | GPL | <50ms | Most flexible open PBX, huge community |

**Integration pattern:** On PTT release, audio is captured from the server, transcribed via Whisper (cloud or self-hosted), and the transcript POSTed to OpenProxyAI.

> See **[Appendix C.13](#c13--mumble--openproxyai-bridge-python--docker-compose)** for the Mumble → OpenProxyAI bridge and Docker Compose configuration.

---

#### A.2.3 — Open Source Speech-to-Text Engines

Self-hosted STT engines that replace commercial APIs — audio stays entirely within your infrastructure.

| Project | License | Accuracy | GPU Required | Streaming | Mobile SDK | Best For |
|---|---|---|---|---|---|---|
| **OpenAI Whisper** | MIT | ★★★★★ | Optional | No (batch) | Via API | Highest open source accuracy |
| **Faster-Whisper** | MIT | ★★★★★ | Optional | No (batch) | Via API | 4× faster than Whisper, same accuracy |
| **WhisperX** | MIT | ★★★★★ | Optional | No | Via API | Speaker diarization (who said what) |
| **Whisper.cpp** | MIT | ★★★★★ | No (CPU/Metal) | No | ✅ Android/iOS | On-device, zero network for STT |
| **Vosk** | Apache 2.0 | ★★★☆☆ | No | ✅ Yes | ✅ Android/iOS | Streaming, mobile-native, CPU-only |
| **Kaldi** | Apache 2.0 | ★★★★☆ | No | ✅ Yes | Partial | Custom vocabulary / domain models |
| **Coqui STT** | MPL 2.0 | ★★★☆☆ | No | ✅ Yes | Via API | CPU-friendly streaming |
| **SpeechBrain** | Apache 2.0 | ★★★★☆ | Optional | Partial | Via API | Research-grade, highly configurable |

**Spotlight: OpenAI Whisper**
> [openai/whisper](https://github.com/openai/whisper) — MIT — 70K+ stars

The open source model behind the commercial Whisper API. Robust to accents and noise, 99 languages. Deploy via Python server, Docker, or on-device via **Whisper.cpp**.

| Model | Parameters | VRAM | CPU-only | Recommended For |
|---|---|---|---|---|
| `tiny` / `tiny.en` | 39M | ~1 GB | ✅ | Edge devices, fast response |
| `base` / `base.en` | 74M | ~1 GB | ✅ | FUTO Voice Input default |
| `small` | 244M | ~2 GB | ✅ | Balance of speed + accuracy |
| `medium` | 769M | ~5 GB | Slow | Dedicated server with GPU |
| `large-v3` | 1.5B | ~10 GB | ❌ | Maximum accuracy (GPU required) |

**Spotlight: Vosk**
> [alphacep/vosk-api](https://github.com/alphacep/vosk-api) — Apache 2.0

Most **mobile-friendly** open source STT engine. Ships with native Android (Java/Kotlin) and iOS (Swift) SDKs. Streaming word-by-word results, CPU-only, runs on low-end devices.

**Spotlight: Kaldi**
> [kaldi-asr/kaldi](https://github.com/kaldi-asr/kaldi) — Apache 2.0

Foundation of many modern ASR systems. Highly customizable for domain-specific acoustic model training (medical, legal, manufacturing). Best for organizations needing custom vocabulary.

> See **[Appendix C.4](#c4--self-hosted-faster-whisper-stt-service-docker--python)** for Docker deployment of Faster-Whisper and the FastAPI gateway microservice.
> See **[Appendix C.5](#c5--vosk-android-sdk--on-device-streaming-stt-kotlin)** for the Vosk Android SDK streaming integration.

---

### A.3 — Native Platform Development (Android & Apple)

> **Complexity:** ⭐⭐⭐ Medium — requires mobile development skills (Kotlin or Swift) but leverages built-in OS voice APIs, minimizing third-party dependencies.

Build directly on the platform's first-party audio and speech frameworks for an org-branded, fully controlled voice-to-OpenProxyAI experience.

**When to choose native SDK development:**
- You need a custom-branded app (your org's name, UI, branding)
- You need to combine voice input with other features (auth, logging, user profiles)
- You want to control exactly which STT engine is used
- You need to integrate with internal systems (LDAP, SSO, ticketing, ERP)

**SDK layers available on each platform:**

| Layer | Android | iOS |
|---|---|---|
| **Audio capture** | `MediaRecorder`, `AudioRecord` | `AVAudioRecorder`, `AVAudioEngine` |
| **Built-in STT** | `SpeechRecognizer` (Google) | `SFSpeechRecognizer` (Apple) |
| **External STT** | Whisper API, Google Cloud STT, Vosk | Whisper API, Azure Speech, on-device |
| **TTS playback** | `TextToSpeech` | `AVSpeechSynthesizer` |
| **UI framework** | Jetpack Compose / XML | SwiftUI / UIKit |
| **Language** | Kotlin | Swift |

---

#### A.3.1 — Android Native Voice Integration

Android provides two recording approaches and four STT options:

**Audio capture:**
- `MediaRecorder` — simple file-based recording, best for PTT (record → send on release)
- `AudioRecord` — low-level PCM stream, best for real-time streaming STT

**STT options:**
- `SpeechRecognizer` — zero setup, Google-powered, online by default
- Whisper API — highest accuracy, cloud-based
- Vosk Android SDK — on-device streaming, no network required
- Whisper.cpp via JNI — fully on-device, MIT license

| Tool / API | Purpose | Online / Offline |
|---|---|---|
| `SpeechRecognizer` | Real-time STT via Google | Online |
| `MediaRecorder` | Capture audio to file | Both |
| `AudioRecord` | Low-level PCM capture | Both |
| `TextToSpeech` | Play AI response as audio | Both |
| `AssistantAppSession` | Register as default assistant | Online |

> See **[Appendix C.9](#c9--android-speechrecognizer--openproxyai-kotlin)** for the `SpeechRecognizer` integration.
> See **[Appendix C.10](#c10--android-mediarecorder-ptt--whisper-api-kotlin)** for the `MediaRecorder` PTT pattern.

---

#### A.3.2 — Apple iOS Native Voice Integration

Apple provides first-party, zero-dependency audio and speech frameworks tightly integrated with iOS privacy and accessibility.

**Audio capture:**
- `AVAudioRecorder` — simple file-based recording, best for PTT
- `AVAudioEngine` — low-level PCM buffer streaming, best for real-time STT

**STT options:**
- `SFSpeechRecognizer` — zero setup, Apple-powered, on-device for iOS 17+
- Whisper API — highest accuracy, compatible with `AVAudioRecorder` output
- Azure Cognitive Services Speech — streaming, HIPAA BAA available
- Whisper.cpp via Swift bindings — fully on-device, no network

| Tool / API | Purpose | Online / Offline |
|---|---|---|
| `SFSpeechRecognizer` | Real-time STT (Apple / Siri) | Both (on-device iOS 17+) |
| `AVAudioEngine` | Low-level audio capture + streaming | Both |
| `AVAudioRecorder` | Simple file-based recording | Both |
| `AVSpeechSynthesizer` | TTS for AI response playback | Offline |
| `App Intents` | Register voice shortcut with Siri | Online |

> See **[Appendix C.18](#c18--ios-sfspeechrecognizer--openproxyai-swift)** for the `SFSpeechRecognizer` real-time integration.
> See **[Appendix C.10b](#c10b--ios-avaudiorecorder-ptt--whisper-api-swift)** for the `AVAudioRecorder` PTT pattern.

---

### A.4 — Custom Development from Scratch (SDK & Frameworks)

> **Complexity:** ⭐⭐⭐⭐ Hardest — full-stack audio engineering. Requires expertise in audio DSP, streaming protocols, STT engine integration, and mobile/backend development.

Build a fully proprietary voice pipeline with no dependency on commercial or OS-native STT.

**When to choose this path:**
- You need a custom wake word (e.g., "Hey OpenProxy")
- You require on-device STT with zero network calls
- You are building for a specialized domain (medical, legal, manufacturing jargon)
- You want to fine-tune an STT model on your organization's vocabulary

**Full custom stack components:**

| Layer | Technology Options |
|---|---|
| **Audio capture** | Android `AudioRecord`, iOS `AVAudioEngine`, PortAudio (cross-platform) |
| **Wake word detection** | Picovoice Porcupine, openWakeWord (open source), Snowboy |
| **STT engine** | Whisper.cpp (on-device), NVIDIA Riva, Kaldi, fine-tuned Whisper |
| **Language model** | OpenProxyAI gateway → any LLM backend |
| **TTS engine** | Piper TTS, Coqui TTS, ElevenLabs API, Azure Neural TTS |
| **Transport** | WebSocket (streaming), HTTP/2, gRPC |
| **Frameworks** | React Native + native modules, Flutter + FFI, Kotlin Multiplatform |

**Complexity vs. Control Summary:**

| Approach | Dev Effort | Dependencies | Data Control | Customizability |
|---|---|---|---|---|
| A.1 Commercial | Hours | High (vendor) | Low | Low |
| A.2 Open Source | Days | Medium (self-hosted) | High | Medium |
| A.3 Native Platform | Weeks | Low (OS APIs) | High | High |
| A.4 Custom SDK/Framework | Months | Minimal | Full | Maximum |

> See **[Appendix C.19](#c19--react-native-ptt-button-javascript)** for the React Native PTT bridge.
> See **[Appendix C.20](#c20--on-device-whispercpp-android-kotlin)** for Whisper.cpp on-device (Android via JNI).
> See **[Appendix C.21](#c21--custom-wake-word-with-openwakeword-python)** for the openWakeWord "Hey OpenProxy" detection.
> See **[Appendix C.12](#c12--custom-grpc-streaming-voice-pipeline-python)** for the gRPC streaming pipeline.

---

## 3. Category B: Hardware-Based Solutions

Hardware-based solutions require purpose-built physical devices — PTT radios, ruggedized handsets, or wearable badges. They deliver superior durability, dedicated PTT keys, and purpose-fit form factors for demanding environments such as field operations, manufacturing, and healthcare. Hardware devices are procurement decisions — chosen for their physical characteristics as much as their software capabilities.

| Sub-Category | Method | Deployment | Best For |
|---|---|---|---|
| LTE / Wi-Fi PTT Radios | B.1 | Cloud / On-premise | Field workers, public safety, logistics |
| Ruggedized Android Handsets | B.2 | Cloud / On-premise | Warehouse, industrial, RFID workflows |
| Wearable Voice Badges | B.3 | On-premise + Cloud | Healthcare, retail, hospitality |

---

### B.1 — LTE / Wi-Fi PTT Radios (Hybrid Devices)

These devices combine the **walkie-talkie form factor** — familiar to field workers, public safety teams, and logistics operators — with LTE and Wi-Fi connectivity and Android internals. Unlike traditional radios, they transmit voice over IP networks, enabling full integration with OpenProxyAI.

**Key characteristics:**
- Walkie-talkie body with a large, tactile PTT side button
- LTE (4G/5G) and Wi-Fi connectivity — works anywhere with mobile coverage
- Android internals — runs any Android app or custom integration
- Long battery life (12–24 hours typical)
- Purpose-built for push-to-talk, mission-critical communications

**How it connects to OpenProxyAI:**
```
PTT button pressed → audio recorded on device
         │
         ▼
PTT button released → audio sent via LTE/Wi-Fi
         │
         ▼
Voice Gateway (Whisper STT — cloud or on-prem)
         │
         ▼
OpenProxyAI Gateway → LLM Backend
         │
         ▼
Text/audio response to device speaker
```

**Vendor Reference:**

| Vendor | Device Series | Connectivity | Integration Path | Notes |
|---|---|---|---|---|
| **Motorola Solutions** | WAVE PTX, TLK 150 | LTE + Wi-Fi | WAVE API + custom Android app | Market leader, public safety grade |
| **Hytera** | PNC380, BP515 | LTE + Wi-Fi | OpenMDM + REST API | Strong in APAC and Europe |
| **Kenwood** | NX-5400, ProTalk LTE | LTE + Wi-Fi | KWD-NT3000 middleware | Trusted brand in field comms |
| **Sonim Technologies** | XP10 | LTE + Wi-Fi | Native PTT SDK | Ruggedized, MIL-SPEC drop rating |
| **Zebra Technologies** | TC58 / EC50 | LTE + Wi-Fi | Zebra PTT Pro SDK | Android Enterprise, barcode capable |

> See **[Appendix C.1](#c1--motorola-wave-ptx--openproxyai-bridge-python)** for the Motorola WAVE PTX integration code.

---

### B.2 — Ruggedized Android PTT Devices

Ruggedized Android PTT devices are **full Android smartphones hardened for industrial use** — equipped with dedicated PTT keys, IP67/68 ingress protection, drop resistance (MIL-STD-810), and often barcode scanners or RFID readers.

**Key characteristics:**
- Dedicated **hardware PTT key** — side-mounted, large, glove-operable
- **IP67 / IP68** waterproof and dustproof rating
- **MIL-STD-810** drop and vibration resistance
- Android Enterprise — MDM-manageable (VMware, Intune, SOTI)
- Long battery life with hot-swap capability on some models
- Optional: barcode scanner, RFID reader, thermal camera

**Best for:** Warehousing, manufacturing, field service, utilities — environments where standard smartphones fail within weeks.

**Integration approach:** These devices run standard Android Enterprise. Deploy any software solution from Category A directly onto them:
- Install **Zello Work** or **Mumble** (A.1.2 / A.2.2) for a PTT channel solution
- Deploy the **custom Kotlin SDK app** (A.3.1) with the hardware PTT key mapped via OEM SDK
- Use **Zebra DataWedge** or **Honeywell Device Configuration Utility** to map the hardware PTT key to `onPttPress()` / `onPttRelease()` in your app

**Vendor Reference:**

| Vendor | Device | IP Rating | Notable Feature | Price Range |
|---|---|---|---|---|
| **Zebra Technologies** | TC58, EC50 | IP67 | Barcode scanner, Zebra PTT Pro SDK | $600–$900 |
| **Honeywell** | CT45, CT60 XP | IP67 | Barcode scanner + PTT | $700–$1,000 |
| **Sonim Technologies** | XP10 | IP68 | MIL-SPEC, loudest speaker class | $400–$600 |
| **Datalogic** | Skorpio X5 | IP65 | Pistol-grip, hazardous area certified | $700–$1,100 |
| **Bluebird** | EF501R | IP67 | RFID + PTT, military-grade | $500–$800 |
| **Point Mobile** | PM90 | IP67 | 5G, Android 13, PTT dedicated key | $550–$850 |
| **Urovo** | DT50S | IP67 | Sub-$300, entry-level rugged | $250–$350 |

---

### B.3 — Wearable Voice Badges (Hands-Free)

Wearable voice badge systems are **enterprise wearables designed for always-available, hands-free voice capture** — pioneered in healthcare and now expanding to retail, hospitality, and manufacturing. They clip to a uniform or lanyard and allow staff to communicate and query AI systems without holding or looking at a device.

**Purpose-built for environments where:**
- Staff wear gloves, PPE, or have their hands constantly occupied
- Heads-up, eyes-free operation is required for patient safety or operational focus
- Instant voice-to-colleague and voice-to-AI access must co-exist
- High-compliance data handling (HIPAA, GDPR) is mandatory

**Key characteristics:**
- Worn on the body — badge clip, lanyard, or shirt mount
- Always-on microphone with wake word or button activation
- Operates over existing Wi-Fi (802.11) or LTE infrastructure
- Speaker and optional screen for alerts and AI responses
- Integrates with clinical systems (EHR, nurse call), workforce management, or ERP

**Vendor Reference:**

| Vendor | Product | Form Factor | Connectivity | Best For |
|---|---|---|---|---|
| **Vocera (Stryker)** | Smartbadge, Minibadge | Badge clip | Wi-Fi 802.11 a/b/g/n | Healthcare — clinical comms + AI |
| **Spectralink** | Versity 97 Series | Handset + badge | Wi-Fi / DECT | Hospitality, manufacturing |
| **Ascom** | Myco 4 | Smartphone badge | Wi-Fi / DECT | Hospital and industrial |
| **Cisco** | 8821 Wireless IP Phone | Handset | Wi-Fi | Enterprise Wi-Fi voice |
| **Theatro** | Communicator Gen 3 | Earpiece + collar clip | LTE / Wi-Fi | Retail, frontline workers |

#### Vocera (Stryker) — Clinical AI Integration

Vocera devices are the market leader in healthcare voice communication. The **Smartbadge** provides a touchscreen for visual alerts; the **Minibadge** is compact and PPE-compatible. Both operate over the hospital's existing Wi-Fi and integrate with the **Vocera Engage** middleware platform (150+ clinical system integrations).

**Voice pipeline:**
```
Clinician: "OK Vocera, ask the AI: what is the maximum dose of metformin?"
         │
         ▼
Vocera Minibadge / Smartbadge (Wi-Fi 802.11)
         │
         ▼
Vocera Engage Platform (on-premise)
  └── Custom Voice App (Vocera Platform SDK)
         │
         ▼
OpenProxyAI Gateway → LLM Backend
         │
         ▼
LLM Response → TTS → Badge Speaker
```

**Vocera Network Requirements:**

| Requirement | Specification |
|---|---|
| Wi-Fi standard | 802.11 a/b/g/n (5 GHz preferred) |
| Signal strength | ≥ -65 dBm at badge location |
| Roaming | Fast BSS Transition (802.11r) required |
| QoS | Voice traffic (DSCP EF / 46) prioritized |
| Latency | < 150ms round-trip on WLAN |

> See **[Appendix C.2](#c2--vocera-platform-sdk--openproxyai-bridge-java)** for the Vocera Platform SDK (Java) integration.

#### Theatro — Retail & Frontline Workers

Theatro's Communicator clips to a shirt collar — an earpiece and microphone in one compact unit. Cloud-managed, integrates with retail workforce management systems.

```
Theatro Communicator (collar clip + earpiece) — LTE / Wi-Fi
         │
         ▼
Theatro Cloud Platform
         │
         ▼
Theatro OpenAPI webhook → OpenProxyAI Gateway
```

> See **[Appendix C.3](#c3--theatro-webhook--openproxyai-bridge-pythonflask)** for the Theatro webhook integration.

---

## 4. Speech-to-Text Engine Options

The STT engine is the shared foundation of every voice integration method — it converts raw audio into the text prompt that OpenProxyAI processes. Choosing the right STT engine determines accuracy, latency, data privacy, and infrastructure cost.

### 4.1 — Cloud-Based STT Engines

Cloud STT engines require no infrastructure — send audio over HTTPS, receive a transcript. They offer the highest accuracy and broadest language support, but audio leaves your network.

| Provider | Service | Languages | Streaming | Latency | Pricing | Key Strength |
|---|---|---|---|---|---|---|
| **OpenAI** | Whisper API | 99 | No (batch) | ~1–3s | $0.006/min | Best accuracy, accent robust |
| **Google** | Cloud Speech-to-Text v2 | 125 | ✅ Yes | ~200ms | $0.016/min | Medical model, Android native |
| **Microsoft Azure** | Cognitive Services Speech | 100+ | ✅ Yes | ~200ms | $1/hr | HIPAA BAA, custom vocabulary |
| **Amazon** | Transcribe | 75 | ✅ Yes | ~300ms | $0.024/min | AWS ecosystem, Medical variant |
| **AssemblyAI** | Universal-2 | 99 | ✅ Yes | ~300ms | $0.65/hr | Best punctuation, PII redaction |
| **Deepgram** | Nova-3 | 36 | ✅ Yes | ~100ms | $0.0059/min | Lowest latency, streaming-first |
| **Rev AI** | Rev AI API | 36 | ✅ Yes | ~400ms | $0.02/min | Human-in-the-loop fallback |

**Selection guide:**
- **Best overall accuracy:** OpenAI Whisper API
- **Lowest latency (real-time PTT):** Deepgram Nova-3
- **Healthcare / HIPAA:** Azure Speech (BAA available) or Google Medical STT
- **AWS-native deployments:** Amazon Transcribe
- **PII redaction built-in:** AssemblyAI

### 4.2 — On-Premise / Open Source STT Engines

Self-hosted STT engines keep audio entirely within your infrastructure. More setup required, but eliminates cloud dependency, per-minute billing, and data sovereignty concerns.

| Project | License | Accuracy | GPU Required | Streaming | Mobile SDK | Best For |
|---|---|---|---|---|---|---|
| **OpenAI Whisper** | MIT | ★★★★★ | Optional | No (batch) | Via API | Highest open source accuracy |
| **Faster-Whisper** | MIT | ★★★★★ | Optional | No (batch) | Via API | 4× faster, same accuracy |
| **WhisperX** | MIT | ★★★★★ | Optional | No | Via API | Speaker diarization |
| **Whisper.cpp** | MIT | ★★★★★ | No (CPU/Metal) | No | ✅ Android/iOS | On-device, zero network |
| **Vosk** | Apache 2.0 | ★★★☆☆ | No | ✅ Yes | ✅ Android/iOS | Streaming, mobile-native |
| **Coqui STT** | MPL 2.0 | ★★★☆☆ | No | ✅ Yes | Via API | CPU-friendly streaming |
| **Kaldi** | Apache 2.0 | ★★★★☆ | No | ✅ Yes | Partial | Custom vocabulary |
| **SpeechBrain** | Apache 2.0 | ★★★★☆ | Optional | Partial | Via API | Research-grade |
| **NVIDIA Riva** | Proprietary | ★★★★★ | ✅ Required | ✅ Yes | Via API | Enterprise GPU on-prem |

**Selection guide:**
- **Highest accuracy self-hosted:** Faster-Whisper (large-v3) on GPU
- **Fully on-device (zero network):** Whisper.cpp (Android/iOS) or Vosk
- **Real-time streaming on CPU:** Vosk
- **Custom vocabulary / domain:** Kaldi
- **Enterprise GPU on-prem:** NVIDIA Riva
- **Air-gapped / classified:** Faster-Whisper + Whisper.cpp for mobile

> See **[Appendix C.4](#c4--self-hosted-faster-whisper-stt-service-docker--python)** for Docker deployment and the STT gateway microservice.

---

## 5. On-Premise vs. Cloud Deployment

### Comparison Matrix

| Dimension | Cloud-Based | On-Premise |
|---|---|---|
| **STT Engine** | Whisper API, Google STT, Azure Speech | Faster-Whisper, Vosk, NVIDIA Riva |
| **Setup time** | Minutes (API key) | Days to weeks (server setup) |
| **Cost model** | Per-minute / per-request billing | Infrastructure + engineering cost |
| **Data sovereignty** | Audio leaves your network | Audio never leaves your environment |
| **Compliance** | SOC 2, HIPAA BAA available | Full control, air-gap capable |
| **Latency** | 300ms–2s (network dependent) | 100–500ms (GPU), 500ms–3s (CPU) |
| **Accuracy** | Highest (large models, frequent updates) | High (large-v3 on GPU), moderate (CPU) |
| **Scalability** | Auto-scales | Manual capacity planning |
| **Best for** | SMB, fast deployment, SaaS | Healthcare, defense, finance, GDPR-strict |

### On-Premise Architecture (Air-Gapped)

```
Employee Device (mobile / badge / handset)
         │  (Wi-Fi / LTE — internal only)
         ▼
Voice Gateway Service (Faster-Whisper + FastAPI)
  └── On-premise server (GPU recommended for >20 concurrent users)
         │
         ▼
OpenProxyAI Gateway (on-premise deployment)
  └── Local LLM backend (Ollama / vLLM / LocalAI)
         │
         ▼
Response → TTS (Coqui TTS / Piper / ElevenLabs on-prem)
         │
         ▼
Audio playback on device
```

**Recommended on-premise stack:**

| Component | Recommended Tool | Alternative |
|---|---|---|
| STT | Faster-Whisper (large-v3) | NVIDIA Riva |
| AI Gateway | OpenProxyAI (self-hosted) | LiteLLM |
| LLM Backend | vLLM + Llama 3.1 70B | Ollama |
| TTS | Piper TTS | Coqui TTS |
| Orchestration | Docker Compose | Kubernetes |

### Cloud Architecture

```
Employee Device
         │  (HTTPS)
         ▼
Voice Gateway (cloud microservice — AWS Lambda / Cloud Run)
  └── OpenAI Whisper API (transcription)
         │
         ▼
OpenProxyAI Gateway (cloud deployment)
  └── OpenAI / Anthropic / Mistral API
         │
         ▼
Response → Azure TTS / OpenAI TTS → Audio
```

---

## 6. Decision Matrix

| Scenario | Category | Method | Complexity | STT Engine | Notes |
|---|---|---|---|---|---|
| Smart office / meeting rooms | Software (A) | A.1.1 — Smart Speaker | ⭐ Easiest | Amazon Transcribe / Google STT | No code, plug-and-play |
| BYOD users, no hardware budget | Software (A) | A.1.2 — Zello Work / Teams PTT | ⭐ Easiest | Built-in | SaaS, MDM-managed |
| Zero dev, any Android device | Software (A) | A.1.4.1 — Android Built-in Dictation | ⭐ Easiest | Google Voice Typing | Submit button bridges to OpenProxyAI |
| Zero dev, any iPhone | Software (A) | A.1.4.2 — iOS Built-in Dictation | ⭐ Easiest | Apple Dictation (on-device) | On-device iOS 15+, privacy-first |
| PTT → Whisper → OpenProxyAI | Software (A) | A.2.1 — Whisper-to-Input | ⭐⭐ Low | Whisper API / self-hosted | No custom dev, Android app |
| Offline PTT, audio never leaves device | Software (A) | A.2.1 — FUTO Voice Input | ⭐⭐ Low | Whisper.cpp on-device | Fully air-gapped STT |
| Self-hosted PTT server | Software (A) | A.2.2 — Mumble + Bridge | ⭐⭐ Low | Faster-Whisper | Open source, <50ms latency |
| STT with full data sovereignty | Software (A) | A.2.3 — Faster-Whisper / Vosk | ⭐⭐ Low | Self-hosted | Audio never leaves network |
| Org-branded Android app | Software (A) | A.3.1 — Android Native SDK | ⭐⭐⭐ Medium | SpeechRecognizer / Whisper API | Kotlin, OS-native APIs |
| Org-branded iOS app | Software (A) | A.3.2 — Apple Native SDK | ⭐⭐⭐ Medium | SFSpeechRecognizer / Whisper API | Swift, on-device STT available |
| Custom wake word, offline STT | Software (A) | A.4 — Custom SDK/Framework | ⭐⭐⭐⭐ Hardest | Whisper.cpp / NVIDIA Riva | Full pipeline from scratch |
| Field workers, logistics | Hardware (B) | B.1 — LTE PTT Radio | Hardware | Whisper API / Faster-Whisper | Walkie-talkie UX over LTE |
| Warehouse, industrial | Hardware (B) | B.2 — Ruggedized Android | Hardware | Faster-Whisper on-prem | IP67, dedicated PTT key |
| Healthcare / clinical staff | Hardware (B) | B.3 — Vocera Smartbadge | Hardware | NVIDIA Riva (on-prem) | Hands-free, HIPAA, badge-worn |
| Retail / frontline workers | Hardware (B) | B.3 — Theatro | Hardware | Deepgram Nova-3 | Cloud-only, fast deployment |
| Air-gapped / classified env. | Hardware (B) | B.2 + A.4 on-prem LLM | Hardware | Faster-Whisper large-v3 | Zero external traffic |
| HIPAA / GDPR regulated data | Hardware (B) | B.3 + A.2.3 full stack | Hardware | NVIDIA Riva or Faster-Whisper | Audio never leaves your network |

---

## 7. Suggested Implementation: Phased Go-to-Market Plan

This section provides a recommended deployment roadmap for organisations bringing OpenProxyAI voice capabilities to market quickly. The three-phase plan is ordered by increasing security complexity, hardware scope, and user reach — allowing teams to deliver value at each stage without waiting for the full stack to be production-ready.

| Phase | Name | Mode | Target Users | Security Level | Time to Deploy |
|---|---|---|---|---|---|
| **Phase 1** | Push to Talk (PTT) | Controlled Voice Input | Early pilots, internal teams | Low (app-level auth) | Days–Weeks |
| **Phase 2** | Always Listening Assistant | Hands-Free, Secure Mobile Voice | Mobile workforce, managed devices | Medium (device certificates) | Weeks–Months |
| **Phase 3** | Mobile + Wearables | Enterprise-Wide Voice Coverage | Full org, field + clinical + retail | High (zero-trust, hardware identity) | Months |

---

### Phase 1 — Push to Talk (PTT): Controlled Voice Input

> **"Deliver immediate value with minimal security and operational complexity."**

Phase 1 is the fastest path from zero to a working AI voice experience. It uses explicit user intent — press to speak, release to send — which eliminates false triggers and keeps the architecture simple. This phase is ideal for early pilots, internal users, demonstrations, and low-risk environments.

#### Purpose & Target Scenarios

| Scenario | Why Phase 1 fits |
|---|---|
| Internal pilot with a small team | Low risk, easy to iterate, no MDM or cert infrastructure needed |
| Developer / IT admin demonstration | Shows the full PTT → STT → LLM → response loop in minutes |
| Field test in a controlled environment | Validates STT accuracy and AI usefulness before broader rollout |
| Low-sensitivity workflows | No PII, no regulated data — security simplicity is acceptable |

#### Functional Features

**Voice Interaction**

| Feature | Status | Notes |
|---|---|---|
| Push to Talk button | ✅ | User presses to start recording, releases to stop |
| Speech-to-Text conversion | ✅ | Audio transcribed via Whisper API or Google STT |
| Text prompt sent to AI backend | ✅ | Via OpenProxyAI gateway |
| Response returned as text | ✅ | Displayed in app UI |
| Response returned as voice (TTS) | ✅ Optional | AVSpeechSynthesizer / Android TextToSpeech |

**Multimodal Support**

| Feature | Status | Notes |
|---|---|---|
| Take a photo + speak a prompt | ✅ | Image + voice text sent together via API |
| Multimodal response (text + optional voice) | ✅ | Model returns text; app optionally speaks it |
| Document / file upload | ❌ | Not in scope for Phase 1 |

**Authentication & Security**

| Feature | Status | Notes |
|---|---|---|
| App-level authentication | ✅ | Username + password, PIN, or shared secret |
| Session-based auth | ✅ | Token stored for session duration |
| Device identity / certificates | ❌ | Introduced in Phase 2 |
| Certificate-based trust | ❌ | Introduced in Phase 2 |

**What Phase 1 validates:**
- Voice UX and PTT interaction model feel natural to users
- STT accuracy is sufficient for the target use case and language
- Multimodal flow (voice + image) works end-to-end
- AI response quality and usefulness in real workflows

#### Technical Implementation

**Recommended PTT approach for Phase 1:** Android native (`MediaRecorder`) or iOS native (`AVAudioRecorder`), using touch events to gate the recording window.

```
ACTION_DOWN (button press)  → start MediaRecorder / AVAudioRecorder
ACTION_UP   (button release) → stop recording
                             → POST audio to STT engine
                             → POST transcript to OpenProxyAI
                             → Display / speak response
```

**STT engine choices for Phase 1:**

| Option | Setup | Accuracy | Cost | Best For |
|---|---|---|---|---|
| OpenAI Whisper API | API key only | ★★★★★ | $0.006/min | Fast start, highest accuracy |
| Google Cloud STT | API key only | ★★★★☆ | $0.016/min | Streaming support |
| Android SpeechRecognizer | Zero setup | ★★★★☆ | Free | Pilot on Android only |

**Open Source PTT Reference Implementations**

In addition to native Android/iOS APIs, the following open source projects provide ready-made PTT UI components and interaction models that can be adapted:

| Project | Platform | License | What it provides |
|---|---|---|---|
| **VoicePing Android SDK** | Android | Open source + free SDK | One-button PTT UI, audio streaming, walkie-talkie UX. Strip the networking layer and reuse the PTT interaction model. [GitHub: SmartWalkieOrg/VoicePing-Walkie-Talkie-AndroidSDK](https://github.com/SmartWalkieOrg/VoicePing-Walkie-Talkie-AndroidSDK) |
| **Whisper-to-Input** | Android | MIT | PTT keyboard IME, sends to Whisper API, zero custom app dev |
| **FUTO Voice Input** | Android | FUTO open | Offline PTT, replaces Google Voice Typing |
| **Mumble client** | Android / iOS | BSD | Open PTT comms client for self-hosted Murmur server |

**Phase 1 Architecture:**

```
User Device (Android / iOS)
  └── PTT Button (press → hold → release)
         │
         ▼
Audio captured via MediaRecorder / AVAudioRecorder
         │
         ▼
STT Engine (Whisper API / Google STT / On-device SpeechRecognizer)
         │
         ▼
OpenProxyAI Gateway
  ├── App-level auth (session token)
  ├── PII filtering
  └── Prompt routing → LLM backend
         │
         ▼
Response → UI text display + optional TTS playback
```

**Phase 1 Exit Criteria** — before moving to Phase 2:

- [ ] PTT → STT → LLM → response loop working end-to-end on target devices
- [ ] STT word error rate acceptable for the target domain
- [ ] At least 10 internal users have completed real workflow tasks using voice
- [ ] Multimodal (voice + image) tested and validated
- [ ] AI response quality reviewed and prompt tuning completed

---

### Phase 2 — Always Listening Android Assistant: Hands-Free, Secure Mobile Voice

> **"Remove the button. Keep the security."**

#### Objective and Technology Shift

Phase 2 moves the solution from a button-driven dictation model to a true hands-free voice assistant, while simultaneously upgrading security from user-centric authentication to device-centric, zero-trust authentication.

This aligns with the evolution seen in modern dictation and assistant platforms, where speech input, conversational context, and voice output are treated as a continuous interaction rather than isolated actions.

**Why this is a critical inflection point:**

| Shift | From Phase 1 | To Phase 2 |
|---|---|---|
| User experience | Button-driven, transactional | Conversational, continuous, speech-first |
| Security model | Application login (username/password) | Device identity (certificates, mTLS) |
| Architecture | Single-purpose PTT client | Extensible — foundation for wearables and edge devices |

#### New Capabilities vs. Phase 1

| Capability | Phase 1 | Phase 2 |
|---|---|---|
| Interaction model | Press-to-talk | Always listening (wake word or continuous) |
| Device identity | None | Device certificates (MDM-enrolled) |
| Authentication | App-level (username/password) | Certificate-based mutual TLS (mTLS) |
| Target devices | Any phone | MDM-managed Android devices |
| Hands-free operation | No | Yes — full hands-free |
| Wake word | No | "OK OpenProxy" (on-device keyword spotting) |
| Background listening | No | Yes (Android Foreground Service) |
| Conversational context | Stateless | Multi-turn session with history |
| TTS response | Optional | Standard — short and long response handling |

---

#### Modular Functional Architecture

Phase 2 is designed as five cooperating modules, each based on mature speech and dictation technologies. The modules are loosely coupled and independently evolvable — enabling teams to upgrade individual components (e.g., swap the STT engine) without rewriting the others.

```
┌─────────────────────────────────────────────────────────────┐
│                  Phase 2 Module Stack                       │
├──────────────────────────┬──────────────────────────────────┤
│  Module 1                │  Always Listening & Wake Phrase  │
│  Module 2                │  Active Speech Capture & VAD     │
│  Module 3                │  Speech-to-Text (STT) Processing │
│  Module 4                │  Response & Text-to-Speech (TTS) │
│  Module 5                │  Authentication & Device Trust   │
└──────────────────────────┴──────────────────────────────────┘
```

---

#### Module 1 — Always Listening & Wake Phrase Detection

**Purpose:** Enable hands-free activation without transmitting audio until explicit user intent is detected.

| Capability | Status | Notes |
|---|---|---|
| Always-on background service (Android) | ✅ | Runs as an OS-compliant Foreground Service |
| Microphone continuously monitored | ✅ | Audio processed locally only — nothing transmitted |
| Wake phrase: "OK OpenProxy" | ✅ | On-device keyword spotting |
| On-device detection (no network) | ✅ | No raw audio leaves the device before activation |
| Audible or haptic confirmation on activation | ✅ | User knows the assistant is listening |
| No audio transmitted before activation | ✅ | Privacy-by-design |

> **Technology note:** Wake phrase detection is _not_ speech-to-text. It is a keyword spotting problem optimised for always-on operation, low CPU usage, no network dependency, and no raw audio storage. This mirrors industry practice in Android voice assistants and offline voice systems.

**Recommended keyword spotting engines:**

| Engine | License | On-device | Notes |
|---|---|---|---|
| Picovoice Porcupine | Commercial (free tier) | ✅ | Custom wake words, low false-positive rate |
| openWakeWord | Apache 2.0 | ✅ | Community-trained models, Home Assistant ecosystem |
| Snowboy (archived) | Apache 2.0 | ✅ | Legacy but still deployable |
| Whisper.cpp (streaming) | MIT | ✅ | Heavier; suitable for short-phrase detection on-device |

---

#### Module 2 — Active Dictation: Speech Capture & Voice Activity Detection (VAD)

**Purpose:** Once the wake phrase is detected, transition into active dictation mode with high-quality audio capture gated by silence detection.

| Capability | Status | Notes |
|---|---|---|
| Audio captured at higher quality | ✅ | PCM 16kHz mono (standard for STT pipelines) |
| VAD: detects when user starts speaking | ✅ | Silero VAD or WebRTC VAD |
| VAD: detects when user stops (silence) | ✅ | Recording stops automatically on silence |
| Audio finalised and forwarded for transcription | ✅ | Sent to STT module |

> **Why this separation matters:** Wake word detection is lightweight and continuous (low power). Active dictation is high accuracy and short-lived (high power only when needed). This separation is standard in modern dictation pipelines to balance battery life and accuracy.

**Recommended VAD libraries:**

| Library | Language | Notes |
|---|---|---|
| Silero VAD | Python / ONNX | State-of-the-art accuracy, runs on Android via ONNX Runtime |
| WebRTC VAD | C / Android | Built into Android SDK; fast and lightweight |
| py-webrtcvad | Python | Server-side VAD for cloud STT pre-processing |

---

#### Module 3 — Speech-to-Text (STT) Processing

**Purpose:** Convert captured speech into a reliable text prompt for the AI backend.

| Capability | Status | Notes |
|---|---|---|
| Audio converted to text | ✅ | Full transcript of spoken input |
| Partial / streaming results (optional) | ✅ | For responsive UI during transcription |
| Final transcript stored | ✅ | Used as AI prompt |
| Deterministic behaviour | ✅ | Same audio → same transcript (engine-dependent) |
| Language auto-detection | ✅ Optional | Supported by Whisper and Google STT |
| Punctuation and sentence segmentation | ✅ | Supported by all major engines |

> **Technology alignment:** This module aligns with modern dictation engines — offline or cloud-based — that support streaming recognition, incremental results, and session-aware transcription. Open source engines (Vosk, Whisper-based APIs) and commercial engines (Google, Azure, Amazon) all follow this exact pattern. See [Section 4](#4-speech-to-text-engine-options) for a full STT engine comparison.

---

#### Module 4 — Response & Text-to-Speech (TTS)

**Purpose:** Return the AI response as both text and voice, with natural playback behaviour.

| Capability | Status | Notes |
|---|---|---|
| Response returned as text | ✅ | Mandatory; displayed in app UI |
| Response returned as voice (TTS) | ✅ | Standard in Phase 2 |
| Short responses → immediate playback | ✅ | Below threshold: single audio chunk |
| Long responses → chunked playback | ✅ | Streamed sentence by sentence |
| Playback interruptible at any time (barge-in) | ✅ | User speaks → audio stops → new input captured |

**Recommended TTS engines:**

| Engine | Type | Notes |
|---|---|---|
| Android TextToSpeech (built-in) | On-device | Zero setup; quality varies by device |
| Google Cloud TTS (WaveNet) | Cloud | High naturalness; streaming support |
| Azure Neural TTS | Cloud | Enterprise SLA; SSML support |
| OpenAI TTS API | Cloud | Natural voices; simple REST API |
| Piper TTS | On-device / open source | Neural quality; runs fully offline |
| Coqui TTS | On-device / open source | Customisable voice models |

> **Technology alignment:** Chunked playback and barge-in interruption are standard techniques in all conversational TTS systems — from Dragon NaturallySpeaking to Google Assistant to OpenAI Realtime API.

---

#### Module 5 — Authentication & Device Trust

**Purpose:** Replace user-password authentication with device identity, establishing a zero-trust security posture.

**Core principles:**

| Principle | Description |
|---|---|
| Device identity over user passwords | Every API call is authenticated by the device certificate, not a stored secret |
| Zero-trust access model | No device is trusted by default; trust is earned via MDM enrolment and cert validity |
| No secrets stored in the app | The certificate is hardware-backed where available (Android Keystore) |

| Capability | Status | Notes |
|---|---|---|
| Android device enrolled via Android Enterprise / MDM | ✅ | Intune, Workspace ONE, SOTI |
| Device certificates issued automatically via SCEP | ✅ | MDM pushes cert to device keystore |
| Mutual TLS (mTLS) for all API calls | ✅ | Device cert presented on every OpenProxyAI request |
| No passwords stored locally | ✅ | Phase 1 session auth is replaced by mTLS |
| Device unenrolment = automatic access revocation | ✅ | MDM wipes cert; device loses API access instantly |
| Certificate pinning in app | ✅ | Prevents MITM attacks even on compromised networks |
| Per-device audit trail in OpenProxyAI | ✅ | Device cert identity logged on every interaction |

**MDM options for certificate provisioning:**

| MDM Platform | Certificate Protocol | Notes |
|---|---|---|
| Microsoft Intune | SCEP / PKCS | Automated cert provisioning; strong Android Enterprise support |
| VMware Workspace ONE | SCEP / PKCS | Enterprise fleet management with deep Android integration |
| SOTI MobiControl | SCEP | Field device specialist; ruggedized device expertise |
| Jamf Connect (iOS) | SCEP / PKCS | For future iOS expansion in Phase 3 |

---

#### Advanced Voice Assistant Capabilities

Beyond the five core modules, Phase 2 includes three differentiating capabilities that define the difference between dictation software and a true voice assistant:

**Hands-Free Conversation**
- After wake phrase, no further user action required
- Natural pauses are allowed and handled by VAD
- Speech automatically chunked into prompt-ready segments

**Barge-In (Interruption)**
- User can speak while the assistant is playing back a response
- Audio playback stops immediately on new speech detection
- New input is captured and processed
- Conversation continues seamlessly

**Transcript Visibility**
- Every spoken interaction is transcribed and visible in-app
- Voice and text are fully synchronised
- Provides an audit trail for compliance and user review

---

#### Conversational Intelligence: Prompt Construction & Context Management

Phase 2 introduces stateful, multi-turn conversation — moving from isolated prompts (Phase 1) to a continuous dialogue session.

**Prompt enrichment:** The final transcript is optionally enriched with:
- User role (from MDM identity)
- Device context (device type, location, enrolment group)
- Session history (previous prompts and responses)
- Time context (for time-sensitive queries)

**Multi-turn session support:**

| Capability | Status | Notes |
|---|---|---|
| Each interaction belongs to a session | ✅ | Session ID tied to device cert identity |
| Previous prompts and responses retained | ✅ | Context window managed by gateway |
| Context survives interruptions | ✅ | Follow-up questions reference prior turns |

> This mirrors conversational dictation and assistant designs where speech is stateful, not stateless — consistent with how Dragon, Siri, Google Assistant, and OpenAI Realtime API all manage conversational context.

---

#### Multimodal Interaction

| Capability | Status | Notes |
|---|---|---|
| Voice + photo prompts | ✅ | Image + transcribed voice sent together |
| Real-time interaction | ✅ | Response returned immediately |
| Document or file upload | ❌ | Not in scope for Phase 2 |
| Response as text | ✅ | Mandatory |
| Response as voice (TTS) | ✅ | Standard in Phase 2 |

---

#### Phase 2 Architecture

```
MDM-Enrolled Android Device
  └── Always-on Foreground Service (Module 1)
         │   Keyword spotting: "OK OpenProxy"
         │   (Porcupine / openWakeWord — on-device, no network)
         │
         ▼
Active Dictation (Module 2)
  └── AudioRecord + VAD (Silero / WebRTC)
         │   Captures audio from speech start → silence
         │
         ▼
STT Engine (Module 3)
  ├── On-device: Whisper.cpp / Vosk
  └── Cloud: Whisper API / Google STT / Azure STT
         │   Returns transcript (streaming or final)
         │
         ▼
Prompt Constructor (Conversational Intelligence)
  └── Transcript + role + device context + session history
         │
         ▼
OpenProxyAI Gateway
  ├── mTLS: device certificate validated (Module 5)
  ├── PII filtering + compliance logging
  ├── Role-based prompt routing
  └── LLM backend (OpenAI / Anthropic / local)
         │
         ▼
Response Handler (Module 4)
  └── Text displayed + TTS playback (chunked, interruptible)
         │
         ▼
Barge-in detection → interrupt playback → return to Module 2
```

---

#### Why Phase 2 Is the Key Milestone

Phase 2 is the pivotal release in the roadmap — not an incremental improvement, but a fundamental shift in both user experience and security posture:

| Dimension | Phase 1 | Phase 2 |
|---|---|---|
| Usability | Button-driven dictation | ChatGPT-like hands-free conversation |
| Security | App login (username/password) | Device identity (zero-trust certificates) |
| Enterprise readiness | Pilot-grade | Production-grade |
| Foundation for Phase 3 | No | Yes — same modules extend to wearables and edge devices |

**Phase 2 Exit Criteria** — before moving to Phase 3:

- [ ] Wake word ("OK OpenProxy") running on-device with acceptable false positive rate (< 1 per hour)
- [ ] VAD accurately detecting speech start and end (< 500ms latency)
- [ ] STT producing transcripts with acceptable Word Error Rate for target domain
- [ ] MDM certificate provisioning fully automated for enrolled device fleet
- [ ] mTLS connection to OpenProxyAI verified, audited, and cert revocation tested
- [ ] Multi-turn conversation context working across at least 5 turns per session
- [ ] Barge-in (interruption) tested and validated
- [ ] Hands-free workflow validated with at least 25 users in a real-world environment
- [ ] Battery and performance impact assessed and within acceptable bounds

---

### Phase 3 — Mobile + Wearables: Eyes-Free, Device-Neutral Voice Platform

> **"Extend voice to every worker, every device, every environment."**

#### Objective

Phase 3 extends the secure, conversational voice platform built in Phase 2 beyond the smartphone — enabling AI voice access across the full spectrum of enterprise wearables, ruggedized devices, and purpose-built voice badges. The goal is a **vendor-neutral, device-neutral platform** that delivers ubiquitous voice access for any worker in any environment where hands and eyes are occupied.

This phase specifically targets:
- **Hands-busy environments** — factory floors, field service, clinical settings where a phone cannot be held
- **Eyes-busy environments** — driving, operating machinery, wearing protective gear where looking at a screen is not possible
- **Always-available voice** — interaction that requires no unlock, no tap, no sequence of steps

**Target verticals:**

| Vertical | Typical Scenario | Primary Constraint | Device Preference |
|---|---|---|---|
| Healthcare | Nurse queries, medication checks, clinical notes | Hands sterile / occupied with patient | Vocera Smartbadge, Android phone |
| Retail | Product lookup, stock check, customer assist | Hands on products / customer | Theatro Communicator, Zebra device |
| Field operations | Maintenance workflows, fault logging | Hands on tools, outdoors | Sonim / Honeywell rugged phone, RealWear glasses |
| Logistics / Warehousing | Pick-and-pack, routing, exception handling | Hands on goods, gloves worn | Zebra WT wearable, Honeywell device |
| Public safety | Field reporting, situational awareness | Hands on equipment / weapon | Motorola WAVE, Inrico, Sonim |
| Manufacturing | Process guidance, quality inspection | Hands on machinery, PPE worn | RealWear AR glasses, Zebra wearable |

---

#### New Capabilities vs. Phase 2

| Capability | Phase 2 | Phase 3 |
|---|---|---|
| Device types | Managed Android phones | Phones + ruggedized + PTT radios + wearable badges + AR glasses |
| Platform coverage | Android only | Android + iOS + wearables (Vocera, Theatro, Zebra, RealWear, Vuzix…) |
| Identity model | Device certificates (phone holds cert) | Phone holds cert; wearables delegate identity to phone |
| SSO integration | No | Yes — SAML / OIDC / Azure AD / Okta |
| Observability | Session logging | Full prompt audit (Langfuse), Prometheus, Grafana |
| Offline capability | Partial | Full offline STT + local LLM fallback (Whisper.cpp + Ollama) |
| Multi-language support | Org English | Org-configured language list per user identity |
| Multimodal | Voice + image (phone only) | Wearable captures voice; paired phone captures image; combined submission |

---

#### Supported Devices (Vendor Neutral)

Phase 3 adopts a **device-neutral** philosophy. The Android phone remains the primary trust anchor, compute hub, and API gateway. Wearables and ruggedized devices are voice capture endpoints that delegate processing and identity to the phone.

| Device Category | Form Factor | Examples | STT Level | Status |
|---|---|---|---|---|
| Android mobile phones | Smartphone | Samsung, Pixel, MDM-enrolled fleet | A | ✅ Core anchor |
| Ruggedized Android handhelds | Handheld terminal | Zebra TC series, Honeywell CT series, Sonim XP series, Urovo | A | ✅ |
| LTE / Wi-Fi PTT radios | PTT radio | Motorola WAVE TLK, Hytera PNC series, Inrico T522A | A / B | ✅ |
| Smart badge (enterprise) | Badge worn on chest | Vocera Smartbadge, Theatro Communicator | B | ✅ |
| Mini badge (enterprise) | Smaller clip-on badge | Vocera Minibadge | B | ✅ |
| Intelligent wearable clocks | Wrist-worn | Samsung Galaxy Watch (enterprise mode), Xiaomi PTT wearables | C | 🔸 Optional |
| Wearable computers / AR glasses | Head-mounted | RealWear Navigator 520, Vuzix M400, Zebra WT series | A | ✅ |
| Body-worn cameras (voice-enabled) | Body camera | Huawei EC310, Inrico PoC body cam | A | ✅ |
| Consumer wearables | Smartwatch | Samsung Galaxy Watch (Wear OS), Apple Watch | C | 🔸 Limited |
| AI voice badges (recording-first) | Badge / clip-on | Speakly AI, VoxAI, TicNote, ANYPIN | C | 🔸 Emerging |
| Open wearable / pendant (developer) | Pendant / clip | Omi, PLAUD NotePin, Bee, Limitless (discontinued HW) | C | 🔸 Emerging |

---

#### Voice Interaction Capabilities (Wearables)

Wearable voice interaction is designed around three activation modes, each suited to different operational contexts:

| Activation Mode | How it works | Best for |
|---|---|---|
| Wake phrase ("OK OpenProxy") | Always-on keyword spotting; no button press needed | Hands sterile / gloved / occupied |
| PTT hardware button | Press dedicated key → speak → release | High-noise environments, mission-critical |
| Soft PTT button (app) | Touch-screen button on wearable display | Intermediate; some hand availability |

**Capability matrix:**

| Feature | Status | Notes |
|---|---|---|
| Wake phrase "OK OpenProxy" | ✅ | On-device keyword spotting (Porcupine / openWakeWord); no audio transmitted before activation |
| Hands-free voice capture | ✅ | Always available after activation; no phone interaction required |
| PTT button — hardware | ✅ | Dedicated key on ruggedized devices (Zebra, Sonim, Honeywell, Inrico) |
| PTT button — soft | ✅ | Touch-based button on badge or wearable display |
| Activation feedback: audio cue | ✅ | Earcon / beep confirms assistant is listening |
| Activation feedback: haptic | ✅ | Vibration on devices with haptics (Galaxy Watch, Honeywell) |
| Activation feedback: visual | ✅ | LED or display indicator on badge / glasses |
| Always-available interaction | ✅ | No phone unlock, no tap sequence, no screen interaction needed |
| Automatic silence detection (VAD) | ✅ | Recording stops automatically; inherited from Phase 2 Module 2 |

---

#### Multimodal Interaction (Wearable + Mobile)

Phase 3 introduces a **split-device multimodal pattern** — the wearable handles voice capture (hands-free), while the paired Android phone handles compute-intensive operations (STT, image capture, API submission). This preserves the lightweight nature of the wearable while leveraging the phone's processing power and connectivity.

**Example workflow:** A field engineer wearing RealWear glasses says *"OK OpenProxy, what's the fault code on this panel?"* while pointing their phone camera at the equipment. The wearable captures the voice, the phone takes the photo, and both are submitted together as a multimodal prompt.

```
Wearable device (badge / glasses / wrist)
  └── "OK OpenProxy, check this component"
         │  Wake phrase detected on-device
         ▼
Audio transmitted to paired Android phone
  └── Via Bluetooth A2DP / Wi-Fi Direct / BLE
         │
         ▼
Paired Android phone
  ├── STT: Whisper API / Google STT / on-device Whisper.cpp
  ├── Optional: Camera triggered by user (photo capture)
  └── Unified multimodal submission → OpenProxyAI
         │  { "prompt": transcript, "image": base64 }
         ▼
OpenProxyAI Gateway
  ├── mTLS: device certificate (phone)
  ├── PII filtering + prompt audit
  └── LLM backend (vision-capable model)
         │
         ▼
Response
  ├── Phone: text display + TTS audio playback
  └── Wearable: audio routed back via Bluetooth / BLE
                or short text pushed to wearable display
```

| Capability | Status | Notes |
|---|---|---|
| Wearable captures voice | ✅ | Via badge mic, headset mic, or wearable mic array |
| Audio transmitted to paired phone | ✅ | Bluetooth A2DP / BLE / Wi-Fi Direct |
| Phone performs STT | ✅ | Whisper API, Google STT, or on-device Whisper.cpp |
| Paired phone captures photo | ✅ | Camera triggered independently by user |
| Unified multimodal API submission (voice + image) | ✅ | Single API call to OpenProxyAI |
| Response returned to phone (text + TTS voice) | ✅ | Standard |
| Response returned to wearable (voice cue or short text) | ✅ | Audio routed back via Bluetooth; text pushed to wearable display where supported |
| Real-time interaction | ✅ | End-to-end latency target: < 3 seconds |
| Document / file upload | ❌ | Not in scope for Phase 3 |

---

#### Authentication & Security (Wearable-Friendly)

Phase 3 extends the Phase 2 zero-trust model to wearables using a **phone-anchored identity delegation** pattern — avoiding the operational complexity of provisioning certificates on every wearable.

| Principle | Description |
|---|---|
| Single device identity model | The enrolled Android phone holds the device certificate |
| Wearables delegate to phone | Wearables communicate via Bluetooth / Wi-Fi to the phone; the phone authenticates to the backend |
| No cert provisioning on wearables | Reduces MDM complexity significantly |
| Backend trusts only enrolled phones | Wearable access is implicitly gated by the phone's enrolment status |
| Device unenrolment = instant revocation | MDM wipes phone cert; all paired wearables lose backend access |

| Feature | Status | Notes |
|---|---|---|
| Phone holds MDM-issued device certificate | ✅ | From Phase 2 |
| mTLS from phone to OpenProxyAI | ✅ | From Phase 2 |
| Wearable audio routed through phone | ✅ | Phone is the trust anchor |
| SSO / SAML / OIDC (user identity) | ✅ | Azure AD, Okta, Ping Identity |
| Device posture check | ✅ | MDM compliance verified before session |
| Per-user prompt audit trail | ✅ | User identity + device cert + prompt logged |
| Role-based AI access | ✅ | Different AI personas / tools per role (nurse, technician, manager) |
| DLP / PII scanning | ✅ | Microsoft Presidio or AWS Comprehend inline |
| Air-gapped / offline mode | ✅ | On-prem Faster-Whisper + local vLLM / Ollama |

---

#### Optional Advanced Capabilities (Future-Ready)

| Capability | Status | Description |
|---|---|---|
| Per-device policy enforcement | 🔹 Future | Different AI access rules per device type (e.g., badge vs. phone) |
| Contextual prompts | 🔹 Future | Prompt enriched with location, role, device type, shift context |
| Offline degraded mode | 🔹 Future | Local STT + queued prompts synced when connectivity restored |

---

#### Supported Hardware: Vendor Catalogue

##### Category 1 — Dedicated Smart Badge & Mini Badge Systems

Purpose-built, hands-free voice wearables for always-on enterprise voice interaction.

---

**1.1 Vocera (Stryker)**

| Attribute | Details |
|---|---|
| Device types | Vocera Smartbadge, Vocera Minibadge |
| Primary verticals | Healthcare, hospitals, regulated frontline environments |
| Voice capabilities | Always-available voice capture, hands-free commands, VoIP, voice messages, group broadcasts, Wi-Fi streaming |
| STT integration level | Level B (indirect / platform API) |
| Integration method | Vocera Platform SDK + webhook; audio or transcript extracted via platform |
| Why relevant | Market leader in healthcare wearable voice; deeply integrated with clinical workflows |

---

**1.2 Theatro (Motorola Solutions)**

| Attribute | Details |
|---|---|
| Device types | Theatro Communicator (wearable badge + in-ear + belt unit) |
| Primary verticals | Retail, hospitality, manufacturing, logistics |
| Voice capabilities | Always-on capture, PTT, hands-free, continuous cloud streaming, AI-driven voice workflows, group / 1-to-many comms |
| STT integration level | Level B (platform API + webhook) |
| Integration method | Theatro cloud platform → webhook → OpenProxyAI |
| Why relevant | Purpose-built for retail and hospitality frontline AI voice workflows |

---

##### Category 2 — Ruggedized Mobile + Wearable Ecosystems (PTT-First)

Android-based devices with dedicated PTT hardware — the most direct integration path for OpenProxyAI.

---

**2.1 Motorola Solutions (WAVE PTX)**

| Attribute | Details |
|---|---|
| Device types | Android smartphones (WAVE PTX app), TLK 25 wearable, broadband PTT radios |
| Primary verticals | Public safety, field operations, transportation, utilities |
| Voice capabilities | PTT, live voice streaming (LTE / Wi-Fi), voice recording / playback, group / private calls, radio interoperability |
| STT integration level | Level A (direct — Android OS, raw audio access) |
| Integration method | WAVE PTX API + on-device Android app capturing mic audio → STT → OpenProxyAI |
| Why relevant | Largest PTT ecosystem; strong enterprise and public safety deployments globally |

---

**2.2 Zebra Technologies**

| Attribute | Details |
|---|---|
| Device types | Rugged Android handhelds (TC series, EC series), WT series wearable computers, headset accessories |
| Primary verticals | Warehousing, retail, manufacturing, logistics |
| Voice capabilities | PTT Pro, voice messaging, audio streaming (Wi-Fi / LTE), Bluetooth headset integration |
| STT integration level | Level A (direct — Android OS, raw audio) |
| Integration method | Capture mic audio in custom Android app → STT → OpenProxyAI; PTT key mapped via DataWedge |
| Why relevant | Zebra devices act as the **mobile anchor** for wearable voice capture in warehouse and retail environments |

---

**2.3 Honeywell (Smart Talk)**

| Attribute | Details |
|---|---|
| Device types | Rugged Android phones, rugged tablets, wearable accessories |
| Primary verticals | Industrial, logistics, warehousing, utilities |
| Voice capabilities | PTT, voice messaging, live voice communication, secure voice upload via Smart Talk |
| STT integration level | Level A (direct — Android OS) |
| Integration method | Custom Android app captures mic; routes to STT engine → OpenProxyAI alongside Smart Talk |
| Why relevant | Enterprise-grade Android voice stack designed for harsh environments; ATEX-rated options for hazardous sites |

---

**2.4 Sonim Technologies**

| Attribute | Details |
|---|---|
| Device types | Ultra-rugged Android phones with hardware PTT buttons, wearable audio accessories |
| Primary verticals | Public safety, construction, energy, field services |
| Voice capabilities | Dedicated hardware PTT, voice recording, live streaming, emergency voice features |
| STT integration level | Level A (direct — hardware PTT key → app → STT) |
| Integration method | Hardware PTT → `ACTION_DOWN` → app starts recording → STT → OpenProxyAI |
| Why relevant | Sonim phones are widely used as voice hubs paired with wearables in mission-critical environments |

---

**2.5 Inrico (China) — Top Recommendation for APAC / Global Budget Deployments**

| Attribute | Details |
|---|---|
| Device types | Inrico T522A, S200, IRC-100, PoC body-worn cameras, speaker mic wearable radios |
| Primary verticals | Public safety, logistics, security |
| Voice capabilities | PTT, continuous voice streaming (LTE / Wi-Fi), voice recording, Android OS (raw audio access) |
| STT integration level | Level A (direct — Android OS, full raw audio access) |
| Integration method | Audio → custom STT client on device / companion phone / backend |
| Why relevant | Android-based, mission-critical voice, widely deployed globally; excellent value for APAC deployments |

---

**2.6 Hytera (China) — Enterprise Grade, Carrier Scale**

| Attribute | Details |
|---|---|
| Device types | LTE / Android PoC radios, Bluetooth PTT rings, wearable accessories, PoC smartphone apps |
| Primary verticals | Public safety, utilities, transport |
| Voice capabilities | PTT, group voice streaming, encrypted voice, voice recording (platform-dependent) |
| STT integration level | Level B (indirect — best via Android terminals or PoC app audio export) |
| Integration method | Android terminal or PoC app → audio forwarded to STT backend |
| Why relevant | One of the world's largest professional communications vendors; deployed globally across public safety and utilities |

---

**2.7 Xiaomi (China) — Prosumer PTT Wearable Ecosystem**

| Attribute | Details |
|---|---|
| Device types | Xiaomi PTT wearables (walkie-talkie form factor), Mi Band accessories, selected Redmi rugged phones |
| Primary verticals | Prosumer, SME field ops, APAC logistics |
| Voice capabilities | PTT, voice messaging, short-range and LTE voice streaming |
| STT integration level | Level C for wearables (consumer OS constraints); Level A for paired Android phones |
| Integration method | Paired Android phone captures and processes audio via custom app → STT → OpenProxyAI |
| Why relevant | Strong APAC market presence; affordable entry point for SME and prosumer deployments; wearable PTT products growing rapidly |

---

**2.8 Huawei EC310 (China) — Body-Worn Camera with Dedicated Voice**

| Attribute | Details |
|---|---|
| Device types | Huawei EC310 body-worn camera (enterprise grade) |
| Primary verticals | Law enforcement, field ops, security, utilities |
| Voice capabilities | Dedicated voice recording button, dual microphones, real-time audio/video streaming, LTE upload |
| STT integration level | Level A (audio streams directly forwarded to STT backend) |
| Integration method | Audio stream from EC310 → backend STT engine → OpenProxyAI |
| Why relevant | Widely deployed in law enforcement and field ops; dual mic array delivers high-quality audio; direct stream architecture makes STT integration straightforward |

---

##### Category 3 — Head-Mounted Wearables (Voice-First AR)

---

**3.1 RealWear**

| Attribute | Details |
|---|---|
| Device types | RealWear Navigator 520, HMT-1 (assisted reality head-mounted wearables) |
| Primary verticals | Manufacturing, oil & gas, field service, remote expert assistance |
| Voice capabilities | Always-on voice control, local voice recognition, voice commands, workflow voice capture, audio/video streaming |
| STT integration level | Level A (on-device Android environment; direct mic capture possible) |
| Integration method | On-device app captures audio → STT (on-device or streamed to phone / server) |
| Why relevant | Voice-first by design; purpose-built for hands-busy scenarios; no screen interaction required |

---

**3.2 Vuzix**

| Attribute | Details |
|---|---|
| Device types | Vuzix M400, M4000, Blade 2, Shield (Android-based smart glasses) |
| Primary verticals | Enterprise AR, logistics, remote assistance |
| Voice capabilities | Voice commands, audio recording, streaming via Wi-Fi / Bluetooth, Android app ecosystem |
| STT integration level | Level A (Android-based; custom app can capture mic audio) |
| Integration method | Custom app on device captures audio → STT → OpenProxyAI; or stream to companion phone |
| Why relevant | Android-based wearable capable of direct voice capture and upload; strong enterprise partner ecosystem |

---

##### Category 4 — Consumer Wearables (Optional / Limited Control)

---

**4.1 Samsung Galaxy Watch (Wear OS)**

| Attribute | Details |
|---|---|
| Voice capabilities | Voice recording, built-in speech-to-text dictation, sync to paired Android phone |
| STT integration level | Level C (built-in STT available; limited raw audio control) |
| Limitation | Consumer OS restrictions; battery constraints; STT tied to Samsung/Google services |
| Integration path | Dictation output synced to phone → forwarded to OpenProxyAI (indirect) |

**4.2 Apple Watch** *(out of scope for Android-primary deployment; noted for completeness)*

- Voice recording APIs exist; audio upload via paired iPhone
- Strong OS restrictions on continuous background streaming
- Consider for Phase 3 iOS fleet expansion only

---

##### Category 5 — AI Voice Badges & Recording-First Wearables (Emerging / Future)

These devices are recording-and-transcription-first rather than communications-first. They are highly relevant for knowledge capture, compliance, and future AI pipeline integration.

---

**5.1 Speakly AI (China) — Smart Voice Badge for Sales & Compliance Analytics**

| Attribute | Details |
|---|---|
| Form factor | Clip-on / pin-on badge; name-badge style |
| Battery | 12+ hours active; stores dozens of hours locally |
| Voice pipeline | Continuous recording → upload → cloud ASR → speaker role separation → NLP / LLM analysis |
| STT integration level | Level C (native STT included; transcript / audio export via API) |
| Outputs | Full transcripts, speaker-labelled dialogues, SOP compliance scoring, customer intent signals, analytics dashboards |
| Best fit | Retail sales analytics, compliance & quality inspection, voice of customer, offline environments with delayed sync |
| Weak fit | Real-time voice assistants, PTT communications, wake-word assistants |
| Integration with OpenProxyAI | Speakly backend → transcript export API → OpenProxyAI for downstream LLM analysis |

---

**5.2 VoxAI (China) — Professional AI Voice Badge**

| Attribute | Details |
|---|---|
| Form factor | Compact clip-on / badge; quad-microphone array |
| Voice pipeline | Badge records → uploads → STT with speaker ID → timestamping → LLM post-processing |
| STT integration level | Level C (built-in STT + audio/transcript export API) |
| Outputs | Full transcripts, structured summaries, forms, reports, LLM-ready conversation artefacts |
| Best fit | Legal documentation, medical consultations (non-real-time), professional services, knowledge capture, meetings |
| Integration with OpenProxyAI | Transcript / audio export → OpenProxyAI for LLM summarisation and routing |

---

**5.3 TicNote by Mobvoi (China / US)**

| Form factor | Clip-on / badge-like wearable recorder |
| Purpose | Records conversations, speech-to-text, AI summaries and notes |
| Why relevant | Serious speech AI company (also behind TicWatch); almost identical concept to VoxAI; more consumer-visible |
| Integration | Audio / transcript export → OpenProxyAI |

---

**5.4 Omi (Developer Ecosystem)**

| Form factor | Wearable sensor / pendant |
| Purpose | Open SDK; app marketplace; treats wearable as a sensor feeding AI systems |
| Why relevant | Custom enterprise logic possible via open SDK; treats the wearable as an AI data source |
| Integration | Open SDK → custom integration with OpenProxyAI gateway |

---

**5.5 ANYPIN (China / Hong Kong)**

| Form factor | Smart badge / pin recorder |
| Purpose | One-tap recording, multi-speaker separation, AI transcription and summaries, offline + later upload |
| Why relevant | Very close to Speakly's concept; badge-recorder positioning |
| Integration | Transcript / audio export → OpenProxyAI |

---

**5.6 Friend AI Pendant (US)**

| Form factor | Pendant / badge-style wearable |
| Purpose | Always-on (or semi-always-on) voice capture, transcription, summaries, personal conversation recall |
| Why relevant | Same "wearable microphone + AI backend" model; often compared with Limitless, Bee, Plaud |
| Integration | Audio / transcript API → OpenProxyAI |

---

**5.7 PLAUD NotePin (Global)**

| Attribute | Details |
|---|---|
| Form factor | Wearable pin / badge recorder; attaches to clothing magnetically |
| Voice pipeline | Continuous or on-demand recording → cloud STT → AI summaries and notes |
| STT integration level | Level C (native STT; transcript export API) |
| Outputs | Full transcripts, AI-generated summaries, meeting notes |
| Best fit | Professional knowledge capture, meetings, interviews, sales conversations |
| Why relevant | One of the most polished badge-style recorders in the global market; direct competitor to TicNote and VoxAI; strong transcript export capabilities |
| Integration with OpenProxyAI | Transcript export API → OpenProxyAI for downstream LLM processing and routing |

---

**5.8 Bee (Acquired by Amazon)**

| Attribute | Details |
|---|---|
| Form factor | Clip-on wearable recorder |
| Voice pipeline | Continuous recording → cloud STT → summaries and action items |
| STT integration level | Level C (native STT; transcript export) |
| Status | Acquired by Amazon; hardware sales ongoing at time of writing |
| Best fit | Meeting transcription, knowledge capture, personal productivity |
| Why relevant | Validated the wearable-microphone-as-AI-input concept at scale; Amazon acquisition signals mainstream enterprise interest in this device category |
| Integration with OpenProxyAI | Transcript export → OpenProxyAI for LLM summarisation or routing |

---

**5.9 Limitless (formerly Rewind) — Acquired by Meta**

| Attribute | Details |
|---|---|
| Form factor | Pendant wearable; always-on voice capture |
| Voice pipeline | Continuous ambient recording → cloud STT → AI memory and context retrieval |
| STT integration level | Level C (native STT; hardware sales discontinued after Meta acquisition) |
| Status | Hardware discontinued post-acquisition by Meta; software/API may continue |
| Why relevant | Pioneered the "personal AI memory" wearable concept; demonstrates the direction enterprise ambient voice capture is heading |
| Lesson for OpenProxyAI | The acquisition trajectory of Bee (Amazon) and Limitless (Meta) confirms that enterprise ambient voice wearables are becoming a platform-level investment for major cloud providers |

---

##### Category 6 — China / APAC Market — Extended Vendor Map

For organisations deploying in China or APAC-first markets, the following vendors offer the strongest local support, regulatory compliance, and cost efficiency:

| Vendor | Category | STT Level | Key Strength |
|---|---|---|---|
| Inrico | Android PoC radios + body-worn | A | Android OS = full raw audio control; mission-critical deployments |
| Hytera | Broadband PTT / PoC radios | B | Carrier scale; encryption; global public safety presence |
| Xiaomi | Prosumer PTT wearables | C (wearable) / A (phone) | APAC market reach; affordable entry point |
| Huawei (EC310) | Body-worn camera | A | Dual mic; real-time streaming; law enforcement / field ops |
| Speakly AI | Smart voice badge | C | Retail analytics; conversation intelligence; offline + sync |
| VoxAI / VoxPIN | AI voice badge | C | Multi-mic; structured transcription; LLM-ready output |
| ANYPIN / iFLYTEK ANYPIN | Wearable badge recorder | C | Multi-speaker separation; offline + later upload |

> **iFLYTEK note:** iFLYTEK is China's leading speech AI company. Their ANYPIN product embeds their proprietary ASR engine directly in the badge, giving it some of the strongest STT accuracy in this device category for Mandarin and other Asian languages.

---

##### STT Integration Levels — Reference Guide

When evaluating any wearable or ruggedized device, use this three-level classification to quickly assess the integration complexity and control you will have over the audio pipeline.

---

**Level A — Direct STT Integration (Best / Easiest)**

> You capture raw audio on the device (or via your Android app) and send it directly to your chosen STT engine (Whisper / Vosk / Google STT / Azure STT). You own the full pipeline.

| Vendor | Device Type | Why Level A |
|---|---|---|
| Zebra Technologies | Rugged Android handhelds, WT series | Android OS → your app captures mic; PTT key mapped via DataWedge |
| Honeywell | Rugged Android phones / tablets | Android OS → custom app captures mic alongside Smart Talk |
| Sonim Technologies | Ultra-rugged Android + hardware PTT | Hardware PTT button → `ACTION_DOWN` event → app starts recording |
| RealWear | Android-based AR headsets | Voice-first Android device; mic capture available to on-device apps |
| Vuzix (M Series) | Android-based smart glasses | Android OS; custom app captures audio (permission-gated) |
| Inrico | Android PoC radios + body-worn | Android OS = full raw audio access; widely deployed in APAC |
| Motorola WAVE PTX | Android smartphones + TLK wearable | WAVE PTX app + on-device Android → mic capture → STT |
| Huawei EC310 | Body-worn camera | Dedicated voice recording button; audio stream forwarded to backend |

**Recommended STT engines for Level A:**
- **Cloud:** OpenAI Whisper API, Google Cloud STT, Azure Speech Services
- **On-device:** Whisper.cpp, Vosk, Faster-Whisper

---

**Level B — Indirect / Platform-Mediated Integration**

> Voice is handled by the vendor's proprietary platform. You integrate via platform APIs or webhooks to extract audio or transcripts. You do not have direct mic access.

| Vendor | Device Type | Integration Pattern |
|---|---|---|
| Vocera (Stryker) | Smartbadge, Minibadge | Vocera Platform SDK → webhook → OpenProxyAI |
| Theatro (Motorola Solutions) | Theatro Communicator | Theatro cloud platform → webhook → OpenProxyAI |
| Hytera | LTE PoC radios, Bluetooth PTT rings | Android terminal or PoC app audio export → backend STT |
| Motorola WAVE PTX (dispatch mode) | WAVE dispatch / interoperability | WAVE dispatch API / call recording export → STT |

**Integration pattern for Level B:**
```
Vendor Platform
  └── Voice session / call recording
         │  Platform API / webhook
         ▼
OpenProxyAI integration layer
  └── Audio or transcript forwarded to STT → LLM
```

---

**Level C — Built-in STT / Dictation Available (Useful, but Less Controllable)**

> The device or platform performs STT natively. You receive a transcript (not raw audio). Useful for rapid integration but limits your ability to choose the STT engine or enforce enterprise routing policies.

| Vendor | Device Type | Limitation |
|---|---|---|
| Samsung Galaxy Watch | Wear OS smartwatch | STT tied to Samsung / Google services; consumer OS battery constraints |
| Speakly AI | Smart voice badge | STT cloud-processed by Speakly; transcript export via API |
| VoxAI / VoxPIN | AI voice badge | Built-in multi-mic STT; transcript export API |
| ANYPIN / iFLYTEK ANYPIN | Wearable badge recorder | iFLYTEK ASR embedded; strong Mandarin accuracy; transcript export |
| TicNote (Mobvoi) | Clip-on recorder | Native STT; transcript sync to app |
| PLAUD NotePin | Badge / pin recorder | Cloud STT; transcript export API |
| Bee (Amazon) | Clip-on recorder | Native STT; transcript export |
| Limitless (Meta) | Pendant (HW discontinued) | Native STT; cloud memory; hardware no longer sold |
| Omi | Pendant / open wearable | Open SDK; STT handled by Omi platform or custom |

> **Note on Apple Watch:** Apple Watch has audio recording APIs (WatchKit / Voice Memos) but strong platform restrictions on continuous background audio streaming. Treat as Level C and route audio through the paired iPhone.

---

**Recommendation for OpenProxyAI deployments:**

| Priority | Device target | Rationale |
|---|---|---|
| 1st | Level A devices | Full pipeline control; no vendor lock-in; widest STT engine choice |
| 2nd | Level B devices | Where the vertical demands it (e.g., Vocera in healthcare); integrate via platform API |
| 3rd | Level C devices | For analytics / knowledge capture use cases (Speakly, VoxAI) or consumer-grade pilots |

---

#### Observability & Governance

| Capability | Tool | Notes |
|---|---|---|
| Prompt & response audit | Langfuse | Full trace of every voice interaction, across all device types |
| Metrics & alerting | Prometheus + Grafana | Latency, error rate, STT accuracy per device type |
| Cost tracking | OpenProxyAI dashboard | Per-user / per-team / per-device token usage |
| Compliance reporting | OpenProxyAI + SIEM export | SOC 2, HIPAA audit trail |

---

#### Phase 3 Architecture

```
Device Fleet
  ├── Android phones (MDM-enrolled, Phase 2 stack)
  ├── Ruggedized devices (Zebra / Honeywell / Sonim / Inrico)
  ├── PTT radios (Motorola WAVE / Hytera)
  ├── Wearable badges (Vocera / Theatro)
  └── AR glasses (RealWear / Vuzix)
         │
         ▼  Wake word / PTT button / recording trigger
         │
         ▼
Audio capture
  ├── On-device (Android app for Level A devices)
  └── Wearable → Bluetooth → Paired Android phone (for badges / wearables)
         │
         ▼
STT Engine
  ├── On-device: Whisper.cpp / Vosk (offline)
  └── Cloud: Whisper API / Google STT / Azure STT
         │
         ▼
Prompt Constructor (transcript + role + device context + session history)
         │
         ▼
OpenProxyAI Gateway (on-prem or cloud)
  ├── Zero-trust: device cert (phone) + user identity (SSO) + posture check
  ├── Role-based routing (persona / tool selection)
  ├── DLP / PII filtering (Presidio / AWS Comprehend)
  ├── Prompt audit log (Langfuse)
  └── LLM backend (OpenAI / Anthropic / local vLLM)
         │
         ▼
Response
  ├── Phone: text display + TTS playback
  └── Wearable: audio cue / short text display
         │
         ▼
Metrics → Prometheus → Grafana
```

---

#### Why the 3-Phase Sequence Is Optimal

Before describing the Phase 3 rollout steps, it is worth explaining why the three-phase sequence is the recommended approach rather than starting with the full wearable + always-listening stack from day one.

**Why not start with always-listening + wearables?**

| Risk | Detail |
|---|---|
| Higher battery impact | Always-on microphone + keyword spotting running continuously drains device battery faster; unacceptable for many consumer or semi-consumer wearables |
| Higher security scrutiny | Continuous audio capture on a wearable triggers compliance and privacy reviews that delay deployment — especially in healthcare and regulated environments |
| Higher operational complexity | Wearable MDM, pairing management, audio routing, and vendor API integration all require significant operational infrastructure before you have a single working user session |
| Stakeholder confidence gap | Deploying wearables without first proving the AI value (Phase 1) and security model (Phase 2) makes budget approval and organisational buy-in much harder |

**Why the 3-phase sequence is optimal:**

| Phase | What it proves | What it builds |
|---|---|---|
| Phase 1 — PTT | Value: AI is useful; STT is accurate enough; multimodal works | Stakeholder confidence, prompt tuning, STT calibration |
| Phase 2 — Always Listening | UX: hands-free is better; Security: device certs work at scale | Zero-trust foundation, MDM infrastructure, wake word tuning |
| Phase 3 — Wearables | Reach: voice everywhere, for every worker | Ubiquitous coverage without re-architecting backend or APIs |

**Every phase reuses:**
- The same OpenProxyAI backend gateway
- The same STT pipeline and engine choices
- The same LLM routing and prompt construction logic
- The same mTLS / certificate trust model
- The same observability stack (Langfuse, Prometheus, Grafana)

This means Phase 3 is an **expansion of reach**, not a rebuild.

---

#### Recommended Deployment Sequence for Phase 3

**Phase 3 rollout steps:**

1. **Extend to iOS fleet** — apply Phase 2 mTLS + wake word pattern to MDM-enrolled iPhones
2. **Onboard Level A ruggedized devices** — deploy custom Kotlin app via MDM; map PTT hardware key (Zebra DataWedge / Honeywell DCU / Sonim PTT key)
3. **Integrate PTT radios** — connect WAVE PTX API / Hytera API / Inrico API to voice gateway bridge
4. **Deploy wearable badges** — Vocera Platform SDK integration + Theatro webhook pipeline
5. **Enable AR glasses** — deploy app on RealWear / Vuzix (Level A) or streaming bridge to companion phone
6. **Enable SSO** — connect OpenProxyAI to Azure AD / Okta for per-user identity and role-based access
7. **Activate observability** — Langfuse prompt audit, Prometheus metrics, Grafana dashboards per device type
8. **Air-gap fallback** — deploy on-prem Faster-Whisper + Ollama / vLLM for offline resilience
9. **Evaluate AI badge integration** — Speakly AI or VoxAI for retail / professional service transcript pipelines

**Phase 3 Exit Criteria:**

- [ ] At least two ruggedized device types onboarded and validated in production environment
- [ ] At least one wearable badge type (Vocera or Theatro) integrated and validated in target vertical
- [ ] Phone-anchored identity delegation tested and audited (wearable → phone → OpenProxyAI)
- [ ] SSO integration live with per-user identity and role-based AI access
- [ ] Offline mode tested: STT + LLM fallback working without internet connectivity
- [ ] Full observability stack live: Langfuse audit + Prometheus metrics + Grafana dashboards
- [ ] At least 50 users across at least two device types validated in real-world workflows

---

### Phase Summary

| | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Name** | Push to Talk (PTT) | Always Listening Android Assistant | Mobile + Wearables |
| **Tagline** | Controlled Voice Input | Hands-Free, Secure Mobile Voice | Eyes-Free, Device-Neutral Voice Platform |
| **Interaction** | Press-to-talk | Wake word / continuous | PTT + wake word + badge activation |
| **Devices** | Any phone | MDM Android phones | Phones + ruggedized + PTT radios + wearable badges + AR glasses |
| **Platform** | Android / iOS | Android (MDM) | Android + iOS + wearables (Vocera, Theatro, Zebra, RealWear, Vuzix…) |
| **Auth** | Username / PIN / session | Device certificates + mTLS | Zero-trust: phone cert + SSO + posture; wearables delegate to phone |
| **STT** | Whisper API / Google STT | Whisper API or on-device | On-device (Whisper.cpp) + cloud fallback |
| **Offline** | No | Partial | Yes (Whisper.cpp + Ollama / vLLM) |
| **Multimodal** | Voice + image | Voice + image | Wearable voice + phone image, combined submission |
| **Observability** | Basic | Session logging | Full audit: Langfuse + Prometheus + Grafana per device type |
| **Target verticals** | Any / pilot | Enterprise mobile workforce | Healthcare, retail, field ops, logistics, manufacturing, public safety |
| **Complexity** | ⭐ Low | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ High |
| **Estimated time** | Days–Weeks | Weeks–Months | Months |

---

## Appendix A: Voice API Domain Reference

```
# OpenAI Voice / Realtime
api.openai.com/v1/audio/transcriptions   (Whisper STT)
api.openai.com/v1/audio/speech           (TTS)
api.openai.com/v1/realtime               (Advanced Voice Mode — WebSocket)

# Google Cloud Speech
speech.googleapis.com

# Azure Cognitive Services Speech
*.cognitiveservices.azure.com

# Amazon Transcribe
transcribe.*.amazonaws.com

# Deepgram
api.deepgram.com

# AssemblyAI
api.assemblyai.com
```

---

## Appendix B: Recommended Hardware Vendors

| Category | Vendor | Model | Price Range |
|---|---|---|---|
| LTE PTT Radio (B.1) | Motorola Solutions | WAVE PTX / TLK 150 | $200–$350 |
| LTE PTT Radio (B.1) | Hytera | PNC380 / BP515 | $300–$500 |
| LTE PTT Radio (B.1) | Kenwood | NX-5400 | $350–$550 |
| Ruggedized Android (B.2) | Zebra Technologies | TC58 / EC50 | $600–$900 |
| Ruggedized Android (B.2) | Honeywell | CT45 XP | $700–$1,000 |
| Ruggedized Android (B.2) | Sonim Technologies | XP10 | $400–$600 |
| Ruggedized Android (B.2) | Urovo | DT50S | $250–$350 |
| Clinical Wearable Badge (B.3) | Vocera (Stryker) | Smartbadge | $400–$600 |
| Clinical Wearable Badge (B.3) | Ascom | Myco 4 | $350–$550 |
| Retail Wearable (B.3) | Theatro | Communicator Gen 3 | $150–$200/yr SaaS |
| Retail Wearable (B.3) | Spectralink | Versity 97 | $300–$500 |
| Smart Speaker (A.1) | Amazon | Echo (4th gen) | $60–$100 |
| Smart Speaker (A.1) | Google | Nest Audio | $100 |

---

## Appendix C: Code Reference

All integration code samples are consolidated here. Each sample is cross-referenced from the relevant section of the guide.

---

### C.1 — Motorola WAVE PTX → OpenProxyAI Bridge (Python)

*Section: B.1 — LTE / Wi-Fi PTT Radios*

```python
# WAVE API — PTT release handler: transcribe audio and forward to OpenProxyAI
import requests

OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

def on_ptt_release(audio_bytes: bytes, user_id: str) -> str:
    transcript = whisper_client.transcribe(audio_bytes)
    response = requests.post(
        OPENPROXYAI_URL,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a field assistant."},
                {"role": "user", "content": transcript, "name": user_id}
            ]
        },
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    )
    return response.json()['choices'][0]['message']['content']
```

---

### C.2 — Vocera Platform SDK → OpenProxyAI Bridge (Java)

*Section: B.3 — Wearable Voice Badges*

```java
// VoceraOpenProxyBridge.java
public class VoceraOpenProxyBridge extends VoceraApp {

    private static final String OPENPROXYAI_URL =
        "https://openproxai.yourdomain.com/v1/chat/completions";
    private static final String ORG_API_KEY = "openproxyai-org-key-abc123";

    @Override
    public void onVoiceCommand(String command, String badgeId) {
        if (command.startsWith("ask the AI")) {
            String prompt = command.replace("ask the AI", "").trim();
            String response = queryOpenProxyAI(prompt, badgeId);
            speakResponse(badgeId, response);
        }
    }

    private String queryOpenProxyAI(String prompt, String userId) {
        HttpClient client = HttpClient.newHttpClient();
        String body = String.format(
            "{\"model\":\"gpt-4o\",\"messages\":[{\"role\":\"user\",\"content\":\"%s\"}],\"user\":\"%s\"}",
            prompt, userId
        );
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(OPENPROXYAI_URL))
            .header("Authorization", "Bearer " + ORG_API_KEY)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        return parseResponse(response.body());
    }
}
```

---

### C.3 — Theatro Webhook → OpenProxyAI Bridge (Python/Flask)

*Section: B.3 — Wearable Voice Badges*

```python
from flask import Flask, request
import requests

app = Flask(__name__)
OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

@app.route('/theatro/voice', methods=['POST'])
def theatro_voice_handler():
    transcript = request.json['transcript']
    employee_id = request.json['employee_id']
    store_id = request.json['store_id']

    response = requests.post(
        OPENPROXYAI_URL,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": f"You are a retail assistant for store {store_id}."},
                {"role": "user", "content": transcript}
            ],
            "user": employee_id
        },
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    )
    return {"speech": response.json()['choices'][0]['message']['content']}
```

---

### C.4 — Self-Hosted Faster-Whisper STT Service (Docker + Python)

*Sections: A.2.3, Section 4.2 — On-Premise STT Engines*

**Docker Compose — Faster-Whisper service:**

```yaml
services:
  whisper:
    image: onerahmet/openai-whisper-asr-webservice:latest
    ports:
      - "9000:9000"
    environment:
      - ASR_MODEL=base.en        # Options: tiny, base, small, medium, large-v3
      - ASR_ENGINE=openai_whisper
    volumes:
      - ./whisper-models:/root/.cache/whisper
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]  # Remove if no GPU available
```

**Test the transcription endpoint:**

```bash
curl -X POST http://whisper.internal:9000/asr \
  -F "audio_file=@/tmp/recording.m4a" \
  -F "language=en" \
  -F "output=json"
```

**FastAPI voice gateway microservice (STT → OpenProxyAI):**

```python
# voice_gateway.py — accepts audio, transcribes, forwards to OpenProxyAI
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import httpx

app = FastAPI()
whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

@app.post("/voice-prompt")
async def voice_prompt(audio: UploadFile = File(...), user_id: str = ""):
    audio_bytes = await audio.read()
    with open("/tmp/voice_input.wav", "wb") as f:
        f.write(audio_bytes)

    segments, _ = whisper.transcribe("/tmp/voice_input.wav")
    transcript = " ".join([s.text for s in segments]).strip()

    if not transcript:
        return {"error": "Could not transcribe audio", "transcript": ""}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENPROXYAI_URL,
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": transcript}], "user": user_id},
            headers={"Authorization": f"Bearer {ORG_API_KEY}"},
            timeout=60.0
        )
    return {
        "transcript": transcript,
        "response": response.json()["choices"][0]["message"]["content"],
        "user_id": user_id
    }
```

---

### C.5 — Vosk Android SDK — On-Device Streaming STT (Kotlin)

*Sections: A.2.3, A.3.1 — Android Native Voice Integration*

```kotlin
// build.gradle — add Vosk dependency
// implementation 'com.alphacep:vosk-android:0.3.47'

class VoskSTTManager(context: Context) {
    private var model: Model? = null
    private var recognizer: SpeechStreamService? = null

    fun init() {
        StorageService.unpack(context, "model-en-us", "model") { model ->
            this.model = model
        }
    }

    fun startListening(resultCallback: (String) -> Unit) {
        val rec = Recognizer(model, 16000f)
        recognizer = SpeechStreamService(rec, getMicInputStream(), 16000f)
        recognizer?.start(object : RecognitionListener {
            override fun onResult(hypothesis: String) {
                val text = JSONObject(hypothesis).getString("text")
                if (text.isNotBlank()) resultCallback(text)
            }
            override fun onFinalResult(hypothesis: String) = onResult(hypothesis)
            override fun onPartialResult(hypothesis: String) {}
            override fun onError(e: Exception) {}
            override fun onTimeout() {}
        })
    }
}
```

---

### C.6 — Amazon Alexa Custom Skill Handler (Node.js)

*Section: A.1.1 — Smart Speaker Integration*

```javascript
const Alexa = require('ask-sdk-core');
const axios = require('axios');

const AskMyAIIntentHandler = {
  canHandle(input) {
    return Alexa.getIntentName(input.requestEnvelope) === 'AskMyAIIntent';
  },
  async handle(input) {
    const prompt = Alexa.getSlotValue(input.requestEnvelope, 'prompt');
    const response = await axios.post(
      'https://openproxai.yourdomain.com/v1/chat/completions',
      { model: 'gpt-4o', messages: [{ role: 'user', content: prompt }] },
      { headers: { 'Authorization': `Bearer ${process.env.OPENPROXYAI_ORG_KEY}` } }
    );
    const reply = response.data.choices[0].message.content;
    return input.responseBuilder.speak(reply).getResponse();
  }
};
```

---

### C.7 — Google Home Conversational Action (Python/Cloud Functions)

*Section: A.1.1 — Smart Speaker Integration*

```python
from flask import Request, jsonify
import requests

OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
OPENPROXYAI_ORG_KEY = "openproxyai-org-key-abc123"

def openproxyai_action(request: Request):
    body = request.get_json()
    prompt = body['intent']['params']['prompt']['resolved']
    resp = requests.post(
        OPENPROXYAI_URL,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}]},
        headers={"Authorization": f"Bearer {OPENPROXYAI_ORG_KEY}"}
    )
    reply = resp.json()['choices'][0]['message']['content']
    return jsonify({
        "session": {"id": body['session']['id'], "params": {}},
        "prompt": {"override": True, "firstSimple": {"speech": reply}}
    })
```

---

### C.8 — Home Assistant + Google Cloud STT Configuration (YAML)

*Section: A.2.1 — Home Assistant + Whisper Cloud*

```yaml
# configuration.yaml — Google STT + OpenProxyAI forwarding
stt:
  - platform: google_cloud
    key_file: /config/google_credentials.json
    language: en-US

rest_command:
  openproxyai_query:
    url: "https://openproxai.yourdomain.com/v1/chat/completions"
    method: POST
    headers:
      Authorization: "Bearer openproxyai-org-key-abc123"
      Content-Type: "application/json"
    payload: >
      {"model": "gpt-4o", "messages": [{"role": "user", "content": "{{ prompt }}"}]}

intent_script:
  ForwardToAI:
    action:
      - service: rest_command.openproxyai_query
        data:
          prompt: "{{ prompt }}"
```

---

### C.9 — Android SpeechRecognizer → OpenProxyAI (Kotlin)

*Section: A.3.1 — Android Native Voice Integration (Option 1)*

```kotlin
// Uses Google's built-in STT — no Whisper server needed
class SpeechToOpenProxyAI(private val context: Context) {

    private val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
    private val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
    }

    fun startListening() {
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle) {
                val transcript = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull() ?: return
                forwardToOpenProxyAI(transcript)
            }
            override fun onError(error: Int) {}
            override fun onReadyForSpeech(params: Bundle) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle) {}
            override fun onEvent(eventType: Int, params: Bundle) {}
        })
        recognizer.startListening(intent)
    }

    private fun forwardToOpenProxyAI(transcript: String) {
        CoroutineScope(Dispatchers.IO).launch {
            val response = OpenProxyAIClient().complete(prompt = transcript)
            withContext(Dispatchers.Main) { speakResponse(response) }
        }
    }
}
```

---

### C.10 — Android MediaRecorder PTT + Whisper API (Kotlin)

*Section: A.3.1 — Android Native Voice Integration (Option 2)*

```kotlin
// VoicePromptManager.kt — hold-to-speak PTT pattern
class VoicePromptManager(private val context: Context) {

    private val mediaRecorder = MediaRecorder()
    private val openProxyClient = OpenProxyAIClient()

    fun onPttPress() {
        mediaRecorder.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioSamplingRate(16000)
            setAudioChannels(1)
            setOutputFile(getTempAudioFile())
            prepare()
            start()
        }
    }

    fun onPttRelease() {
        mediaRecorder.stop()
        mediaRecorder.reset()
        CoroutineScope(Dispatchers.IO).launch {
            val transcript = WhisperClient.transcribe(File(getTempAudioFile()), apiKey = ORG_WHISPER_KEY)
            val response = openProxyClient.complete(prompt = transcript, userId = getCurrentUserId())
            withContext(Dispatchers.Main) { speakResponse(response) }
        }
    }
}
```

**PTT Button XML layout:**

```xml
<com.google.android.material.button.MaterialButton
    android:id="@+id/btn_ptt"
    android:layout_width="120dp"
    android:layout_height="120dp"
    android:text="Hold to Talk"
    app:cornerRadius="60dp"
    app:backgroundTint="@color/emerald_600"
    android:onTouch="@{(v, e) -> viewModel.onPttTouch(v, e)}" />
```

**Android TextToSpeech — speak AI response:**

```kotlin
val tts = TextToSpeech(context) { status ->
    if (status == TextToSpeech.SUCCESS) {
        tts.language = Locale.US
        tts.speak(aiResponse, TextToSpeech.QUEUE_FLUSH, null, "response")
    }
}
```

---

### C.10b — iOS AVAudioRecorder PTT + Whisper API (Swift)

*Section: A.3.2 — Apple iOS Native Voice Integration (Option 2)*

```swift
// VoicePromptViewController.swift — hold-to-speak PTT
import AVFoundation
import UIKit

class VoicePromptViewController: UIViewController {

    private var audioRecorder: AVAudioRecorder?
    private let openProxyClient = OpenProxyAIClient()

    @IBAction func pttButtonDown(_ sender: UIButton) {
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("voice_prompt.m4a")
        audioRecorder = try? AVAudioRecorder(url: url, settings: settings)
        audioRecorder?.record()
        sender.backgroundColor = .systemRed
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    @IBAction func pttButtonUp(_ sender: UIButton) {
        audioRecorder?.stop()
        sender.backgroundColor = .systemGreen
        guard let audioURL = audioRecorder?.url else { return }
        Task {
            let transcript = try await WhisperClient.transcribe(audioURL: audioURL)
            let response = try await openProxyClient.complete(prompt: transcript)
            await MainActor.run { displayResponse(response) }
        }
    }
}
```

**AVSpeechSynthesizer — speak AI response:**

```swift
let synthesizer = AVSpeechSynthesizer()

func speakResponse(_ text: String) {
    let utterance = AVSpeechUtterance(string: text)
    utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
    utterance.rate = 0.5
    synthesizer.speak(utterance)
}
```

---

### C.11 — Zello Work Webhook Bridge (Python/Flask)

*Section: A.1.2 — Commercial PTT Apps*

```python
from flask import Flask, request
import requests, whisper

app = Flask(__name__)
model = whisper.load_model("base")
OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

@app.route('/zello-webhook', methods=['POST'])
def handle_zello_audio():
    audio_url = request.json['audio_url']
    user = request.json['from']
    audio_bytes = download_audio(audio_url)
    transcript = model.transcribe(audio_bytes)['text']
    ai_response = requests.post(
        OPENPROXYAI_URL,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": transcript}]},
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    ).json()['choices'][0]['message']['content']
    return {"response": ai_response, "status": "ok"}
```

---

### C.12 — Custom gRPC Streaming Voice Pipeline (Python)

*Section: A.4 — Custom Development from Scratch*

```python
import grpc
from voice_pb2 import AudioChunk
from voice_pb2_grpc import VoiceGatewayStub

def stream_voice_to_openproxyai(audio_generator):
    channel = grpc.insecure_channel('openproxyai-voice-gateway.internal:50051')
    stub = VoiceGatewayStub(channel)

    def audio_chunks():
        for chunk in audio_generator:
            yield AudioChunk(data=chunk, sample_rate=16000, encoding="LINEAR16")

    for response in stub.StreamVoicePrompt(audio_chunks()):
        print(f"AI: {response.text}")
        speak(response.audio_bytes)
```

---

### C.13 — Mumble → OpenProxyAI Bridge (Python + Docker Compose)

*Section: A.2.2 — Open Source PTT Communication Servers*

```python
# Mumble bridge — listens for PTT audio via Ice middleware, pipes to OpenProxyAI
import whisper, requests

model = whisper.load_model("base.en")
OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

def on_audio_received(audio_bytes: bytes, username: str) -> str:
    transcript = model.transcribe(audio_bytes)['text']
    response = requests.post(
        OPENPROXYAI_URL,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are a team assistant."},
                {"role": "user", "content": transcript}
            ],
            "user": username
        },
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    )
    return response.json()['choices'][0]['message']['content']
```

**Docker Compose — Mumble server + OpenProxyAI bridge:**

```yaml
services:
  murmur:
    image: mumblevoip/mumble-server:latest
    ports:
      - "64738:64738/tcp"
      - "64738:64738/udp"
    volumes:
      - ./murmur.ini:/etc/mumble-server.ini

  openproxyai-bridge:
    build: ./mumble-bridge
    environment:
      - MURMUR_HOST=murmur
      - OPENPROXYAI_URL=https://openproxai.yourdomain.com/v1/chat/completions
      - ORG_API_KEY=openproxyai-org-key-abc123
    depends_on:
      - murmur
```

---

### C.14 — Google Cloud STT → OpenProxyAI (Python)

*Section: A.1.3 — Top Commercial Dictation Systems*

```python
from google.cloud import speech
import requests

OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

def transcribe_and_forward(audio_bytes: bytes, user_id: str) -> str:
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )
    response = client.recognize(config=config, audio=audio)
    transcript = response.results[0].alternatives[0].transcript

    ai_response = requests.post(
        OPENPROXYAI_URL,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": transcript}], "user": user_id},
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    )
    return ai_response.json()['choices'][0]['message']['content']
```

---

### C.15 — Azure Speech → OpenProxyAI (Python)

*Section: A.1.3 — Top Commercial Dictation Systems*

```python
import azure.cognitiveservices.speech as speechsdk
import requests

OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

def azure_stt_to_openproxyai(audio_file: str, user_id: str) -> str:
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
    audio_config = speechsdk.AudioConfig(filename=audio_file)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once()
    transcript = result.text

    return requests.post(
        OPENPROXYAI_URL,
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": transcript}], "user": user_id},
        headers={"Authorization": f"Bearer {ORG_API_KEY}"}
    ).json()['choices'][0]['message']['content']
```

---

### C.16 — Android Built-in Dictation Bridge (Kotlin)

*Section: A.1.4.1 — Android Built-in Dictation*

```kotlin
// User dictates into a text field using the system keyboard mic.
// On submit, the text is forwarded to OpenProxyAI.
class DictationActivity : AppCompatActivity() {

    private lateinit var inputField: EditText
    private lateinit var submitButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        inputField = findViewById(R.id.dictation_input)
        submitButton = findViewById(R.id.submit_btn)

        submitButton.setOnClickListener {
            val prompt = inputField.text.toString()
            if (prompt.isNotBlank()) {
                CoroutineScope(Dispatchers.IO).launch {
                    val response = OpenProxyAIClient().complete(prompt = prompt)
                    withContext(Dispatchers.Main) { showResponse(response) }
                }
            }
        }
    }
}
```

---

### C.17 — iOS Built-in Dictation Bridge (SwiftUI)

*Section: A.1.4.2 — iOS Built-in Dictation*

```swift
// User dictates into a TextField using the system keyboard mic.
// On submit, the text is forwarded to OpenProxyAI.
struct DictationView: View {
    @State private var prompt: String = ""
    @State private var response: String = ""

    var body: some View {
        VStack(spacing: 16) {
            TextField("Tap the mic on keyboard to dictate...", text: $prompt)
                .textFieldStyle(.roundedBorder)
                .padding()

            Button("Send to OpenProxyAI") {
                Task {
                    response = try await OpenProxyAIClient.shared.complete(prompt: prompt)
                }
            }
            .buttonStyle(.borderedProminent)

            Text(response).padding()
        }
    }
}
```

---

### C.18 — iOS SFSpeechRecognizer → OpenProxyAI (Swift)

*Section: A.3.2 — Apple iOS Native Voice Integration (Option 1)*

```swift
import Speech
import AVFoundation

class VoiceRecognitionManager: NSObject {

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))!
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private let audioEngine = AVAudioEngine()

    func startRecognition() {
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        recognitionRequest?.shouldReportPartialResults = true

        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }
        audioEngine.prepare()
        try? audioEngine.start()

        speechRecognizer.recognitionTask(with: recognitionRequest!) { result, _ in
            if let result = result, result.isFinal {
                let transcript = result.bestTranscription.formattedString
                Task { await self.forwardToOpenProxyAI(transcript) }
            }
        }
    }

    func stopRecognition() {
        audioEngine.stop()
        recognitionRequest?.endAudio()
    }

    private func forwardToOpenProxyAI(_ transcript: String) async {
        let response = try? await OpenProxyAIClient.shared.complete(prompt: transcript)
        await MainActor.run { speakResponse(response ?? "") }
    }
}
```

---

### C.19 — React Native PTT Button (JavaScript)

*Section: A.4 — Custom Development from Scratch*

```javascript
import { NativeModules, TouchableOpacity, Text } from 'react-native';
import { useState } from 'react';

const { AudioRecorderModule } = NativeModules;

export default function VoicePTTButton() {
  const [isRecording, setIsRecording] = useState(false);

  const onPressIn = async () => {
    setIsRecording(true);
    await AudioRecorderModule.startRecording();
  };

  const onPressOut = async () => {
    setIsRecording(false);
    const audioPath = await AudioRecorderModule.stopRecording();
    const transcript = await transcribeAudio(audioPath);
    const response = await queryOpenProxyAI(transcript);
    speakResponse(response);
  };

  return (
    <TouchableOpacity
      onPressIn={onPressIn}
      onPressOut={onPressOut}
      style={{
        backgroundColor: isRecording ? '#ef4444' : '#10b981',
        borderRadius: 60, width: 120, height: 120
      }}
    >
      <Text>{isRecording ? 'Listening...' : 'Hold to Talk'}</Text>
    </TouchableOpacity>
  );
}
```

---

### C.20 — On-Device Whisper.cpp Android (Kotlin via JNI)

*Section: A.4 — Custom Development from Scratch*

```kotlin
// Whisper.cpp via JNI — fully offline STT, no network required
class WhisperOnDevice(context: Context) {

    private val whisperContext: Long

    init {
        val modelFile = copyAssetToFile(context, "ggml-base.en.bin")
        whisperContext = WhisperLib.initContext(modelFile.absolutePath)
    }

    fun transcribe(audioFile: File): String {
        val pcmSamples = convertToPcm(audioFile)
        return WhisperLib.transcribeData(whisperContext, pcmSamples)
    }

    external fun initContext(modelPath: String): Long
    external fun transcribeData(ctx: Long, samples: FloatArray): String

    companion object {
        init { System.loadLibrary("whisper") }
    }
}
```

---

### C.21 — Custom Wake Word with openWakeWord (Python)

*Section: A.4 — Custom Development from Scratch*

```python
# Detects "Hey OpenProxy" before starting audio recording
from openwakeword.model import Model

oww_model = Model(wakeword_models=["hey_openproxy.tflite"], inference_framework="tflite")

def listen_for_wake_word(audio_stream):
    while True:
        chunk = audio_stream.read(1280)
        prediction = oww_model.predict(chunk)
        if prediction["hey_openproxy"] > 0.7:
            print("Wake word detected — starting recording")
            record_and_forward_to_openproxyai()
```

---

### C.22 — Vosk Streaming STT Python (CPU-only, real-time)

*Section: A.2.3 — Open Source STT Engines*

```python
from vosk import Model, KaldiRecognizer
import pyaudio, json

model = Model("vosk-model-en-us-0.22")
rec = KaldiRecognizer(model, 16000)
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8192)

print("Listening...")
while True:
    data = stream.read(4096)
    if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        transcript = result.get('text', '')
        if transcript:
            forward_to_openproxyai(transcript)
```

---

### C.13 — Apple Siri App Intents (Swift)

*Section: A.1.1 — Smart Speaker Integration*

```swift
import AppIntents

struct AskAIIntent: AppIntent {
    static var title: LocalizedStringResource = "Ask AI"

    @Parameter(title: "Prompt")
    var prompt: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let response = try await OpenProxyAIClient.shared.complete(prompt: prompt)
        return .result(dialog: IntentDialog(response))
    }
}
```

---

*Last Updated: February 2026 | OpenProxyAI Documentation*
