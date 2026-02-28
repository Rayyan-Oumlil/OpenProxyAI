# End-User Integration: Voice Prompt Integration Guide

**OpenProxyAI — Voice Input Deployment Reference**

> This guide explains how to enable end users to submit AI prompts using their voice — via mobile apps, push-to-talk hardware, smart speakers, speech-to-text engines, and wearable handsets — while routing all voice-derived text through your OpenProxyAI gateway for security, compliance, and observability.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Method 1: Mobile App — Android Standard Voice Mode](#2-method-1-android-standard-voice-mode)
3. [Method 2: Mobile App — Android Advanced Voice Mode](#3-method-2-android-advanced-voice-mode)
4. [Method 3: Smart Speaker & Voice Assistant Integration](#4-method-3-smart-speaker--voice-assistant)
5. [Method 4: Push-to-Talk (PTT) Hardware Handsets](#5-method-4-push-to-talk-hardware-handsets)
6. [Method 5: Wearable Badge Systems (Enterprise / Healthcare)](#6-method-5-wearable-badge-systems)
7. [Method 6: Custom Mobile SDK Integration](#7-method-6-custom-mobile-sdk-integration)
8. [Speech-to-Text Engine Reference](#8-speech-to-text-engine-reference)
9. [On-Premise vs. Cloud Deployment](#9-on-premise-vs-cloud-deployment)
10. [Decision Matrix](#10-decision-matrix)

---

## 1. Architecture Overview

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

## 2. Method 1: Android Standard Voice Mode

The simplest path for mobile users — no custom development required.

### Option A: Native ChatGPT App (Push-to-Talk)

The official ChatGPT app on Android supports a hold-to-speak (PTT) pattern in **Standard Voice Mode**.

**Setup:**
1. Open the ChatGPT app → start a new chat
2. Tap the **microphone icon** (bottom right)
3. Select **Standard Voice Mode** (white circle icon)
4. Hold the button to speak, release to send

> **Separate Mode:** Go to **Settings → Voice → Separate Mode** for a full-screen dedicated voice conversation interface.

**Routing through OpenProxyAI:**

Since the native app connects directly to `api.openai.com`, you must redirect it through the gateway using one of the traffic redirection methods from [01_traffic_redirection_guide.md](./01_traffic_redirection_guide.md):
- PAC file (Method 1) — catches the app's HTTPS traffic
- DNS redirection (Method 3) — transparent, no app config needed
- Firewall interception (Method 4) — network-level, zero client config

### Option B: Set ChatGPT as Default Android Assistant

Replace Google Assistant with ChatGPT to trigger voice via hardware buttons.

**Steps:**
```
Android Settings
  └── Apps
        └── Default apps
              └── Digital assistant app
                    → Select: ChatGPT
```

After this, long-pressing the **Home button** or **Power button** (device-dependent) launches ChatGPT's voice mode instantly.

### Option C: Tasker Automation (Custom PTT Button Mapping)

For a true hardware push-to-talk experience without custom development:

**Required:** [Tasker](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) + [AutoInput plugin](https://play.google.com/store/apps/details?id=com.joaomgcd.autoinput)

**Tasker Task Configuration:**
```
Task: "PTT to OpenProxyAI"
  1. Action: Launch App → ChatGPT (or your custom app)
  2. Action: Wait → 1000ms
  3. Action: AutoInput → Click element "Microphone Button"
  4. Action: Vibrate → 100ms (haptic confirmation)

Trigger: Hardware Button (Volume Down, Power, etc.)
```

**Pixel Quick Tap (No Tasker needed):**
```
Settings → System → Gestures → Quick Tap
  → Action: Open app → ChatGPT
```

**Nothing Phone / Earbuds:**
Nothing OS ships with native ChatGPT integration — configure in:
```
Settings → Buttons & Gestures → Essential Key → ChatGPT Voice
```

---

## 3. Method 2: Android Advanced Voice Mode

Advanced Voice Mode enables real-time, interruption-capable conversation — closer to a phone call than PTT.

### ChatGPT Advanced Voice Mode

**How it differs from Standard:**

| Feature | Standard Voice Mode | Advanced Voice Mode |
|---|---|---|
| Interaction style | Hold-to-speak (PTT) | Continuous, hands-free |
| Interruptions | Not supported | Supported mid-response |
| Latency | ~2–4s (STT + LLM) | ~500ms (real-time streaming) |
| Model | GPT-4o (text pipeline) | GPT-4o Realtime API |
| Availability | All ChatGPT tiers | ChatGPT Plus / API access |

**Routing Advanced Voice Mode through OpenProxyAI:**

The Realtime API uses WebSocket connections to `wss://api.openai.com/v1/realtime`. Standard HTTP proxying does not cover WebSocket. Use:

```nginx
# nginx WebSocket proxy config
location /v1/realtime {
    proxy_pass http://openproxyai-backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

### Google Assistant with OpenProxyAI Backend

You can replace Google Assistant's AI backend with OpenProxyAI using **App Actions** and the **Assistant SDK**:

```kotlin
// AndroidManifest.xml — Register as Assistant
<activity android:name=".VoiceActivity">
    <intent-filter>
        <action android:name="android.intent.action.VOICE_COMMAND" />
        <category android:name="android.intent.category.DEFAULT" />
    </intent-filter>
</activity>
```

---

## 4. Method 3: Smart Speaker & Voice Assistant Integration

Route voice queries from Alexa, Google Home, or Siri through OpenProxyAI.

### Amazon Alexa — Custom Skill

Build an Alexa Skill that forwards transcribed prompts to OpenProxyAI:

**Alexa Skill Flow:**
```
User: "Alexa, ask my AI [prompt]"
         │
         ▼
Alexa STT (Amazon Transcribe)
         │
         ▼
Alexa Skill Lambda (Node.js or Python)
         │
         ▼
POST https://openproxai.yourdomain.com/v1/chat/completions
         │
         ▼
Response text → Alexa TTS → Speaker
```

**Alexa Skill Handler (Node.js):**
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
      {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: prompt }]
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.OPENPROXYAI_ORG_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );

    const reply = response.data.choices[0].message.content;
    return input.responseBuilder.speak(reply).getResponse();
  }
};
```

**Skill Manifest (`skill.json`):**
```json
{
  "skillManifest": {
    "publishingInformation": {
      "locales": {
        "en-US": {
          "name": "My AI Assistant",
          "invocationName": "my ai"
        }
      }
    },
    "apis": {
      "custom": {
        "endpoint": {
          "uri": "arn:aws:lambda:us-east-1:ACCOUNT:function:openproxyai-alexa-skill"
        }
      }
    }
  }
}
```

### Google Home — Conversational Action

```python
# Google Cloud Functions handler
from flask import Request, jsonify
import requests

def openproxyai_action(request: Request):
    body = request.get_json()
    prompt = body['intent']['params']['prompt']['resolved']

    resp = requests.post(
        "https://openproxai.yourdomain.com/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}]
        },
        headers={"Authorization": f"Bearer {OPENPROXYAI_ORG_KEY}"}
    )

    reply = resp.json()['choices'][0]['message']['content']
    return jsonify({
        "session": {"id": body['session']['id'], "params": {}},
        "prompt": {"override": True, "firstSimple": {"speech": reply}}
    })
```

### Apple Siri — App Intents (iOS 17+)

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

## 5. Method 4: Push-to-Talk Hardware Handsets

Dedicated PTT hardware provides the most reliable voice experience for field workers, security teams, and industrial environments.

### Category A: Traditional PTT Radios with LTE (Hybrid Devices)

These devices look and feel like walkie-talkies but transmit over LTE/Wi-Fi, routing voice through your OpenProxyAI gateway.

| Vendor | Device | OS | Integration Method |
|---|---|---|---|
| **Motorola Solutions** | WAVE PTX, TLK 150 | Android | Custom app + WAVE API |
| **Hytera** | PNC380, BP515 | Android | OpenMDM + REST API |
| **Kenwood** | NX-5400 | Android | KWD-NT3000 middleware |
| **Sonim Technologies** | XP10 | Android (ruggedized) | Native PTT SDK |
| **Zebra Technologies** | TC58 / EC50 | Android Enterprise | Zebra PTT Pro SDK |

**Motorola WAVE PTX Integration:**
```python
# WAVE API — transcribe and forward to OpenProxyAI
import requests

def on_ptt_release(audio_bytes: bytes, user_id: str):
    # Step 1: Transcribe via Whisper
    transcript = whisper_client.transcribe(audio_bytes)

    # Step 2: Forward to OpenProxyAI
    response = requests.post(
        "https://openproxai.yourdomain.com/v1/chat/completions",
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

### Category B: Ruggedized Android PTT Devices

Designed for field, warehouse, and industrial environments:

| Vendor | Device | Notable Feature |
|---|---|---|
| **Honeywell** | CT45, CT60 XP | Barcode scanner + PTT, IP67 |
| **Datalogic** | Skorpio X5 | Pistol-grip, hazardous area certified |
| **Bluebird** | EF501R | RFID + PTT, military-grade |
| **Point Mobile** | PM90 | 5G, Android 13, PTT dedicated key |
| **Urovo** | DT50S | Sub-$300, IP67, Android Enterprise |

### Category C: Consumer Smartphone PTT Apps

Software PTT overlaid on standard Android/iOS smartphones — lowest hardware cost:

| App | Platform | On-Premise Option | Notes |
|---|---|---|---|
| **Zello** | Android / iOS | Zello Work (self-hosted) | Most popular PTT app, 150M+ users |
| **TeamSpeak** | Android / iOS | Yes (TeamSpeak Server) | Low-latency, used in gaming/enterprise |
| **Mumble** | Android / iOS | Yes (Murmur server) | Open source, <50ms latency |
| **Voxer** | Android / iOS | Voxer for Business | Async + live PTT |
| **RealWear Companion** | Android | No | Designed for head-mounted displays |

**Self-Hosted Zello Work → OpenProxyAI Bridge:**
```python
# Zello webhook → OpenProxyAI pipeline
from flask import Flask, request
app = Flask(__name__)

@app.route('/zello-webhook', methods=['POST'])
def handle_zello_audio():
    audio_url = request.json['audio_url']
    user = request.json['from']

    # Download and transcribe
    audio_bytes = download_audio(audio_url)
    transcript = transcribe_with_whisper(audio_bytes)

    # Route through OpenProxyAI
    ai_response = query_openproxyai(transcript, user_context=user)

    # Optionally TTS the response back to the channel
    audio_response = text_to_speech(ai_response)
    post_to_zello_channel(audio_response)

    return {"status": "ok"}
```

---

## 6. Method 5: Wearable Badge Systems

Wearable voice badge systems — pioneered in healthcare — are purpose-built for hands-free, eyes-free AI interaction in high-compliance environments.

### Market Leaders

| Vendor | Platform | Deployment | Best For |
|---|---|---|---|
| **Vocera (Stryker)** | Vocera Engage + Smartbadge/Minibadge | On-premise + Cloud | Healthcare, clinical workflows |
| **Spectralink** | Versity 97 Series | On-premise Wi-Fi | Hospitality, manufacturing |
| **Ascom** | Myco 4 | On-premise DECT/Wi-Fi | Hospital and industrial |
| **Cisco** | 8821 Wireless IP Phone | On-premise | Enterprise Wi-Fi voice |
| **Theatro** | Theatro Communicator | Cloud | Retail, frontline workers |

### Vocera Integration Architecture

Vocera (Stryker) devices operate over 802.11 Wi-Fi and expose a **Vocera Platform API** that can bridge badge voice commands to OpenProxyAI:

```
Clinician says: "OK Vocera, ask the AI: what is the maximum dose of metformin?"
         │
         ▼
Vocera Minibadge / Smartbadge (Wi-Fi 802.11 a/b/g/n)
         │
         ▼
Vocera Engage Platform (on-premise server)
  └── Custom Voice App (via Vocera Platform SDK)
         │
         ▼
Vocera Platform API → OpenProxyAI Gateway
  POST /v1/chat/completions
  { "model": "gpt-4o", "messages": [...], "user": "nurse-badge-id-042" }
         │
         ▼
LLM Response → Text-to-Speech → Badge Speaker
```

**Vocera Platform SDK (Java):**
```java
// VoceraOpenProxyBridge.java
public class VoceraOpenProxyBridge extends VoceraApp {

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
            .uri(URI.create("https://openproxai.yourdomain.com/v1/chat/completions"))
            .header("Authorization", "Bearer " + ORG_API_KEY)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        return parseResponse(response.body());
    }
}
```

**Vocera Network Requirements:**

| Requirement | Specification |
|---|---|
| Wi-Fi standard | 802.11 a/b/g/n (5 GHz preferred) |
| Signal strength | ≥ -65 dBm at badge location |
| Roaming | Fast BSS Transition (802.11r) required |
| QoS | Voice traffic (DSCP EF / 46) prioritized |
| Latency | < 150ms round-trip on WLAN |

### Theatro (Retail / Frontline)

Theatro's cloud-based communicator clips to a shirt collar and integrates with workforce management systems:

```
Theatro Communicator (earpiece + microphone clip)
         │  (LTE / Wi-Fi)
         ▼
Theatro Cloud Platform
         │
         ▼
Theatro OpenAPI → OpenProxyAI Gateway
```

**Theatro Webhook Integration:**
```python
@app.route('/theatro/voice', methods=['POST'])
def theatro_voice_handler():
    transcript = request.json['transcript']
    employee_id = request.json['employee_id']
    store_id = request.json['store_id']

    response = requests.post(
        "https://openproxai.yourdomain.com/v1/chat/completions",
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

## 7. Method 6: Custom Mobile SDK Integration

Build your own voice-enabled app on Android or iOS with full control over the PTT workflow.

### Android — Kotlin Implementation

**Full PTT → OpenProxyAI pipeline:**

```kotlin
// VoicePromptManager.kt
class VoicePromptManager(private val context: Context) {

    private val mediaRecorder = MediaRecorder()
    private val openProxyClient = OpenProxyAIClient()

    // Start recording on button press
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
        providePttFeedback()
    }

    // On button release: transcribe + send
    fun onPttRelease() {
        mediaRecorder.stop()
        mediaRecorder.reset()

        CoroutineScope(Dispatchers.IO).launch {
            val audioFile = File(getTempAudioFile())

            // Step 1: Speech-to-Text
            val transcript = transcribeAudio(audioFile)

            // Step 2: Send to OpenProxyAI
            val response = openProxyClient.complete(
                prompt = transcript,
                systemPrompt = "You are a helpful workplace assistant.",
                userId = getCurrentUserId()
            )

            // Step 3: Optional TTS playback
            withContext(Dispatchers.Main) {
                speakResponse(response)
            }
        }
    }

    private suspend fun transcribeAudio(file: File): String {
        // Option A: OpenAI Whisper API (cloud)
        return WhisperClient.transcribe(file, apiKey = ORG_WHISPER_KEY)

        // Option B: On-device Whisper (no network for STT)
        // return LocalWhisperModel.transcribe(file)
    }
}
```

**OpenProxyAI Client:**
```kotlin
// OpenProxyAIClient.kt
class OpenProxyAIClient {
    private val baseUrl = "https://openproxai.yourdomain.com/v1"
    private val apiKey = BuildConfig.OPENPROXYAI_ORG_KEY

    suspend fun complete(
        prompt: String,
        systemPrompt: String = "You are a helpful assistant.",
        userId: String = ""
    ): String {
        val body = ChatRequest(
            model = "gpt-4o",
            messages = listOf(
                Message("system", systemPrompt),
                Message("user", prompt)
            ),
            user = userId
        )

        val response = retrofit.create(OpenProxyAIApi::class.java)
            .chatCompletion(
                authorization = "Bearer $apiKey",
                body = body
            )

        return response.choices.first().message.content
    }
}
```

**Android PTT Button UI (XML layout):**
```xml
<!-- activity_voice.xml -->
<com.google.android.material.button.MaterialButton
    android:id="@+id/btn_ptt"
    android:layout_width="120dp"
    android:layout_height="120dp"
    android:text="Hold to Talk"
    app:cornerRadius="60dp"
    app:backgroundTint="@color/emerald_600"
    android:onTouch="@{(v, e) -> viewModel.onPttTouch(v, e)}" />
```

### iOS — Swift Implementation

```swift
// VoicePromptViewController.swift
import AVFoundation
import UIKit

class VoicePromptViewController: UIViewController {

    private var audioRecorder: AVAudioRecorder?
    private let openProxyClient = OpenProxyAIClient()

    @IBAction func pttButtonDown(_ sender: UIButton) {
        startRecording()
        sender.backgroundColor = .systemRed
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    @IBAction func pttButtonUp(_ sender: UIButton) {
        stopRecordingAndSend()
        sender.backgroundColor = .systemGreen
    }

    private func startRecording() {
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("voice_prompt.m4a")
        audioRecorder = try? AVAudioRecorder(url: url, settings: settings)
        audioRecorder?.record()
    }

    private func stopRecordingAndSend() {
        audioRecorder?.stop()
        guard let audioURL = audioRecorder?.url else { return }

        Task {
            let transcript = try await WhisperClient.transcribe(audioURL: audioURL)
            let response = try await openProxyClient.complete(prompt: transcript)
            await MainActor.run { displayResponse(response) }
        }
    }
}
```

---

## 8. Speech-to-Text Engine Reference

The STT layer converts raw audio to the text prompt that OpenProxyAI processes.

### Cloud-Based STT Engines

| Provider | Service | Languages | Notes |
|---|---|---|---|
| **OpenAI** | Whisper API | 99 | Best accuracy, $0.006/min, used by ChatGPT |
| **Google** | Cloud Speech-to-Text v2 | 125 | Streaming support, Medical model available |
| **Microsoft Azure** | Speech Services | 100+ | Custom vocabulary, Speaker ID |
| **Amazon** | Transcribe | 75 | Real-time + batch, Medical variant |
| **AssemblyAI** | Universal-2 | 99 | Best punctuation, PII redaction built-in |
| **Deepgram** | Nova-3 | 36 | Lowest latency (~300ms), streaming-first |
| **Rev AI** | Rev AI API | 36 | Human-in-the-loop fallback available |

### On-Premise / Self-Hosted STT Engines

| Project | Language | License | Accuracy | GPU Required |
|---|---|---|---|---|
| **OpenAI Whisper** | Python | MIT | ★★★★★ | Optional (faster with) |
| **Faster-Whisper** | Python (CTranslate2) | MIT | ★★★★★ | Optional, 4x faster than Whisper |
| **Vosk** | C++/Python/Java | Apache 2.0 | ★★★☆☆ | No — CPU only |
| **Coqui STT** | Python | MPL 2.0 | ★★★☆☆ | No — CPU-friendly |
| **Kaldi** | C++ | Apache 2.0 | ★★★★☆ | No — enterprise-grade |
| **NVIDIA Riva** | C++/Python | Proprietary | ★★★★★ | Yes — NVIDIA GPU required |
| **SpeechBrain** | Python | Apache 2.0 | ★★★★☆ | Optional |
| **WhisperX** | Python | MIT | ★★★★★ | Optional, adds speaker diarization |

### Self-Hosted Whisper Deployment (Docker)

```yaml
# docker-compose.yml — Whisper STT service
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
            - capabilities: [gpu]  # Remove if no GPU
```

**Transcription API call:**
```bash
curl -X POST http://whisper.internal:9000/asr \
  -F "audio_file=@/tmp/recording.m4a" \
  -F "language=en" \
  -F "output=json"
```

**Response:**
```json
{
  "text": "What is the maximum safe temperature for the reactor cooling loop?",
  "segments": [...],
  "language": "en"
}
```

### STT → OpenProxyAI Pipeline Service

A lightweight Python microservice that accepts audio, transcribes it, and forwards the text to OpenProxyAI:

```python
# voice_gateway.py
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import httpx

app = FastAPI()
whisper = WhisperModel("base.en", device="cpu", compute_type="int8")

OPENPROXYAI_URL = "https://openproxai.yourdomain.com/v1/chat/completions"
ORG_API_KEY = "openproxyai-org-key-abc123"

@app.post("/voice-prompt")
async def voice_prompt(audio: UploadFile = File(...), user_id: str = ""):
    # Step 1: Save audio
    audio_bytes = await audio.read()
    with open("/tmp/voice_input.wav", "wb") as f:
        f.write(audio_bytes)

    # Step 2: Transcribe (on-premise Whisper)
    segments, _ = whisper.transcribe("/tmp/voice_input.wav")
    transcript = " ".join([s.text for s in segments]).strip()

    if not transcript:
        return {"error": "Could not transcribe audio", "transcript": ""}

    # Step 3: Forward to OpenProxyAI
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENPROXYAI_URL,
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": transcript}],
                "user": user_id
            },
            headers={"Authorization": f"Bearer {ORG_API_KEY}"},
            timeout=60.0
        )

    ai_reply = response.json()["choices"][0]["message"]["content"]

    return {
        "transcript": transcript,
        "response": ai_reply,
        "user_id": user_id
    }
```

---

## 9. On-Premise vs. Cloud Deployment

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

## 10. Decision Matrix

Use this table to choose the right voice integration approach for your organization.

| Scenario | Recommended Method | STT Engine | Notes |
|---|---|---|---|
| End users on personal Android phones | Android Standard Voice Mode + PAC proxy | Native app / Whisper API | Fastest user-facing deployment |
| Developers / power users | Custom Android SDK (Kotlin) | Faster-Whisper or Whisper API | Full control, org branding |
| Smart office / meeting rooms | Google Home / Alexa Skill | Amazon Transcribe / Google STT | Hands-free shared AI access |
| Field workers, warehouse | PTT Android handset (Zebra / Honeywell) | Faster-Whisper on-prem | Ruggedized, PTT key mapped |
| Healthcare / clinical staff | Vocera Smartbadge + Engage API | NVIDIA Riva (on-prem) | Hands-free, HIPAA, badge-worn |
| Retail / frontline workers | Theatro Communicator | Deepgram Nova-3 | Cloud-only, fast deployment |
| Air-gapped / classified environment | Custom app + on-prem Whisper + local LLM | Faster-Whisper large-v3 | No external traffic whatsoever |
| HIPAA / GDPR regulated data | On-premise full stack | NVIDIA Riva or Faster-Whisper | Audio never leaves your network |
| Maximum voice accuracy | Custom app + Whisper large-v3 | OpenAI Whisper API | Best-in-class transcription |
| Lowest latency PTT | Deepgram streaming + WebSocket proxy | Deepgram Nova-3 | ~300ms STT, streaming response |

---

## Appendix A: Voice Domain & API Reference

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

## Appendix B: Recommended Hardware Vendors

| Category | Vendor | Model | Price Range |
|---|---|---|---|
| Ruggedized PTT Android | Zebra Technologies | TC58 / EC50 | $600–$900 |
| Ruggedized PTT Android | Honeywell | CT45 XP | $700–$1,000 |
| LTE PTT Radio | Motorola Solutions | TLK 150 | $200–$350 |
| Clinical Wearable Badge | Vocera (Stryker) | Smartbadge | $400–$600 |
| Retail Wearable | Theatro | Communicator Gen 3 | $150–$200/yr SaaS |
| Consumer Earbuds w/ AI | Nothing | Ear (2) | $99–$149 |
| Smart Speaker | Amazon | Echo (4th gen) | $60–$100 |
| Smart Speaker | Google | Nest Audio | $100 |

---

*Last Updated: February 2026 | OpenProxyAI Documentation*
