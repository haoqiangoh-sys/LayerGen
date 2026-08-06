# LayerGen

LayerGen is a simple desktop app for building chained AI workflows. You create blank layers, give each layer its own prompt and settings, then run the layers in order so one layer can feed into another.

It is designed for coding workflows, but the layers can be used for any text-generation pipeline.

## Quick Start

Run the app with Python:

```cmd
python LayerGen.py
```

If you are already in the `outputs` folder:

```cmd
cd C:\Users\haoqi\Documents\Codex\2026-08-03\thi\outputs
python LayerGen.py
```

LayerGen uses only Python's standard library. No extra Python packages are required for the GUI itself.

## Basic Workflow

1. Click `New layer`.
2. Pick a `Provider`.
3. Choose or enter a model.
4. Write the layer prompt.
5. Add more layers as needed.
6. Use `Run all` or `Run selected + after`.

Each layer has its own prompt, provider, model, temperature, max tokens, API key behavior, language, and output box.

## Chaining Layers

Use the `Insert variable` button in a layer prompt to insert values without typing curly braces manually.

Useful variables:

```text
{input}
{language}
{previous_output}
{all_previous_outputs}
{current_output}
{chat_message}
{chat_history}
{layer_1_output}
{layer_2_output}
```

Example:

```text
Turn this plan into clean Python code.

Plan:
{previous_output}
```

To feed Layer 1 directly into Layer 3, use:

```text
Use this source from Layer 1:
{layer_1_output}
```

## Providers

LayerGen supports:

```text
Gemini
OpenAI-compatible
Anthropic
Ollama
Local GGUF
```

### Gemini

Use a Gemini API key. Click `Settings > API key > Enter API key...`, then `Models > Load from provider`.

### Anthropic

Use an Anthropic API key. Click `Settings > API key > Enter API key...`, then `Models > Load from provider`.

### OpenAI-Compatible

Use this for OpenAI, LM Studio, local OpenAI-style servers, or any service with `/v1/models` and `/v1/chat/completions`.

Set the endpoint with:

```text
Settings > Endpoint / runtime...
```

Common examples:

```text
https://api.openai.com/v1
http://localhost:1234/v1
```

### Ollama

Use this when Ollama is running locally.

Default endpoint:

```text
http://localhost:11434
```

Example setup outside LayerGen:

```cmd
ollama pull deepseek-r1:7b
```

Then in LayerGen:

```text
Provider: Ollama
Models > Load from provider
```

No API key is needed for local Ollama.

### Local GGUF

Use this for local GGUF models through `llama-cli.exe`.

Steps:

1. Set provider to `Local GGUF`.
2. Click `Settings > Choose local runtime...`.
3. Select `llama-cli.exe` from the extracted llama.cpp folder.
4. Add a model using one of:
   - `Models > Import local model file...`
   - `Models > Import local model folder...`
   - `Models > Import Hugging Face repo...`

Important: do not copy only `llama-cli.exe` by itself. The Windows llama.cpp build usually needs nearby DLL files. Select the `llama-cli.exe` inside the extracted llama.cpp folder.

## Hugging Face GGUF Repos

For Hugging Face repo IDs, use `Local GGUF` and a recent `llama-cli.exe`.

Example repo IDs:

```text
ggml-org/gemma-3-1b-it-GGUF
unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF:Q4_K_M
```

In LayerGen:

```text
Models > Import Hugging Face repo...
```

Then paste the repo ID.

LayerGen passes the repo to `llama-cli` using the Hugging Face route. The first run may take a long time because the model may need to download before generation starts.

Manual test:

```cmd
"C:\path\to\llama-cli.exe" -hf ggml-org/gemma-3-1b-it-GGUF -p "hello" -n 20 --simple-io
```

If that works in Command Prompt, it should work in LayerGen.

## Chat Fine-Tuning

The `Chat` tab lets you talk to one layer and update that layer plus everything after it.

Use the `Chat with` dropdown to choose the starting layer.

Modes:

```text
Replace outputs
Append outputs
```

`Replace outputs` rewrites the selected layer's output.

`Append outputs` adds new material to the existing output instead of replacing it.

Chat uses the current layer outputs and chat history as memory. It does not rerun earlier layers.

## Flowchart

Open the `Flowchart` tab to see how layers feed into each other.

The flowchart updates based on:

```text
{previous_output}
{all_previous_outputs}
{layer_N_output}
```

Click `Refresh` if you want to force an update.

## Sessions

Use the `File` menu:

```text
File > Save session
File > Save session as...
File > Load session...
File > New project
```

Keyboard shortcuts:

```text
Ctrl+S
Ctrl+Shift+S
```

LayerGen saves layer prompts, settings, outputs, chat history, and the global input.

API keys are not saved unless `Save keys` or `File > Save keys in session` is enabled.

## Output

Each layer has:

```text
Copy output
Save output
Clear output
```

Use `Save output` when you want to save the generated code directly to a file.

## Temperature

Temperature controls randomness.

Lower values make responses more predictable:

```text
0.0 to 0.3
```

Middle values are usually good for coding:

```text
0.3 to 0.7
```

Higher values are more creative but can be less reliable:

```text
0.8 to 2.0
```

## Troubleshooting

### The model is taking forever

For Hugging Face or local GGUF models, the first run may download or load the model. LayerGen shows status updates every minute and warns after about 10 minutes.

Try:

```text
Max tokens: 20
Prompt: hello
```

If it still hangs, run the same `llama-cli` command in Command Prompt to see the runtime's own messages.

### Local model failed: no output returned

Most likely causes:

```text
llama-cli.exe was copied without its DLL files
the wrong executable was selected
the Hugging Face repo is not a GGUF repo
the model is too large for your machine
```

Fix:

```text
Choose llama-cli.exe inside the extracted llama.cpp folder.
Use a small GGUF model first.
Set max tokens to 20 for testing.
```

### The Hugging Face repo does not work

Make sure the repo is GGUF-compatible. GGUF repos often end with:

```text
-GGUF
```

Also try adding a quant:

```text
author/model:Q4_K_M
```

### The dropdown has no models

Use one of:

```text
Models > Load from provider
Models > Enter model name...
Models > Import model list from file...
Models > Import local model file...
Models > Import Hugging Face repo...
```

For `Local GGUF`, `Load from provider` is not used. Import a local file/folder or Hugging Face repo instead.

## Main Files

```text
LayerGen.py
README_LayerGen.md
```

The other Python files in the folder are synced copies kept for compatibility with earlier names.
