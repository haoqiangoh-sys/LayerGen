# LayerGen

LayerGen is a small desktop app for building chained AI workflows.

Instead of using one large prompt, you create separate layers. Each layer can have its own prompt, model, API key, temperature, language, attachments, and output. A layer can use the project input, the previous layer's output, or the output from any specific layer.

LayerGen was originally designed for code generation, but it can be used for any workflow where one AI step should feed another.

This README was made for the latest version of LayerGen, version 0.0.4.

## Quick Start

Open Command Prompt and run:

```cmd
cd C:\Users\haoqi\Documents\Codex\2026-08-03\thi\outputs
python LayerGen.py
```

LayerGen is a single Python file and uses Python's standard library. You do not need to install extra packages for the GUI.

The main file is:

```text
LayerGen.py
```

The folder also contains older compatibility copies:

```text
code_generator_app.py
three_layer_code_generator_gui.py
```

They are kept synced with `LayerGen.py`.

## What LayerGen Does

LayerGen lets you:

- Create blank layers like browser tabs.
- Give each layer its own prompt and settings.
- Chain layers together with insertable variables.
- Run every layer, or start from one layer and run only that layer plus everything after it.
- Chat with one layer to fine-tune that layer and downstream layers.
- Save and load full projects.
- Attach text, code, images, PDFs, and URLs.
- View a flowchart of how layers depend on each other.
- Save generated code directly to a file.

## Basic Workflow

1. Click `New layer`.
2. Choose a provider.
3. Add or load an API key if the provider needs one.
4. Choose a model.
5. Write the layer prompt.
6. Add more layers.
7. Use `Run all` or `Run selected + after`.

Each layer has a `Settings` menu and a `Models` menu.

## Layers

Each layer stores:

- Layer name
- Provider
- Model
- API key behavior
- Endpoint/base URL
- Temperature
- Max tokens
- Language
- Prompt
- Attachments
- Output

Layers are independent, but they can reference each other through variables.

## Variables

Use the `Insert` control in a layer prompt to insert variables without typing braces manually.

Common variables:

```text
{input}
{language}
{layer_name}
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
Write clean Python code from this plan:

{previous_output}
```

Example using a specific earlier layer:

```text
Use the architecture from Layer 1:

{layer_1_output}

Now write the final implementation.
```

## Running Layers

`Run all` starts at the first layer and runs the full workflow.

`Run selected + after` starts at the selected layer and runs only that layer plus the layers after it.

This is useful when you already like the earlier layers and only want to regenerate the later steps.

## Chat

The `Chat` tab is for fine-tuning existing layer outputs.

Use `Chat with` to choose the layer you want to talk to. The chat will update that layer and every layer after it. Earlier layers are not rerun.

Modes:

```text
Replace outputs
Append outputs
```

`Replace outputs` rewrites the selected layer's output.

`Append outputs` adds the new response to the existing output.

Chat uses the current outputs and chat history as memory, so it should build on existing progress instead of starting over.

## Providers

LayerGen supports:

```text
Gemini
OpenAI-compatible
Anthropic
Ollama
Hugging Face
```

### Gemini

Use a Gemini API key.

Typical setup:

```text
Provider: Gemini
Settings > API key > Enter API key...
Models > Load from provider
```

### Anthropic

Use an Anthropic API key.

Typical setup:

```text
Provider: Anthropic
Settings > API key > Enter API key...
Models > Load from provider
```

### OpenAI-Compatible

Use this for OpenAI-style APIs, local model servers, LM Studio, or any service that exposes:

```text
/v1/models
/v1/chat/completions
```

Common endpoints:

```text
https://api.openai.com/v1
http://localhost:1234/v1
```

Set the endpoint with:

```text
Settings > Endpoint...
```

### Ollama

Use this when Ollama is running locally.

Default endpoint:

```text
http://localhost:11434
```

Example outside LayerGen:

```cmd
ollama pull deepseek-r1:7b
```

Then inside LayerGen:

```text
Provider: Ollama
Models > Load from provider
```

Ollama does not need an API key.

### Hugging Face

Use this for Hugging Face Inference Providers.

To search for eligible models:

```text
Provider: Hugging Face
Models > Search Hugging Face models...
```

The search window has three types:

```text
Chat / code / text
Vision / image input
Any compatible
```

You can search for names like:

```text
qwen
gemma
deepseek
coder
vision
```

The search list is filtered toward models Hugging Face reports as served by at least one Inference Provider.

To run a Hugging Face layer, add a Hugging Face token:

```text
Settings > API key > Enter API key...
```

The search can often load public catalog results without a token, but running the model usually requires one.

## API Keys

Each layer can use either:

```text
Shared provider key
Layer-specific key
```

Use a shared key when several layers use the same provider.

Use a layer-specific key when one layer should use a different account, provider route, or token.

API keys are not saved into session files unless you enable:

```text
Save keys
```

For safety, leave `Save keys` off unless you really want the session file to contain your keys.

## Model Menus

Use `Models` inside a layer.

Options include:

```text
Load from provider
Search Hugging Face models...
Import model list from file...
Enter model name...
Clear model list
```

For Hugging Face, the recommended path is:

```text
Models > Search Hugging Face models...
```

For Gemini, Anthropic, OpenAI-compatible servers, and Ollama, use:

```text
Models > Load from provider
```

## Attachments

Project input, layer prompts, and chat messages can include attachments.

Buttons:

```text
Add file
Add URL
Clear files
```

Text and code files are added as readable context.

Images are sent as image input when the selected provider/model supports image input.

PDFs are sent directly to Gemini and Anthropic when supported. Other providers still receive the filename and any readable text LayerGen can include.

Large local files are not copied into the session file. LayerGen saves their file paths, so keep attached files in place if you want a saved session to keep using them.

## Output Display

Layer outputs and chat transcripts render common model formatting more cleanly.

LayerGen styles:

```text
# headings
**bold**
*italic*
`inline code`
fenced code blocks
[links](https://example.com)
> quotes
- lists
~~strikethrough~~
$math$
```

The display is only visual. Copying or saving still uses the underlying text the model produced.

## Saving Code

Each layer output has:

```text
Copy
Save
Clear
```

Use `Save` when you want to write the generated output to a file.

LayerGen chooses a suggested file extension from the layer's language setting.

## Flowchart

Open the `Flowchart` tab to see how layers feed into each other.

The diagram updates based on variables such as:

```text
{previous_output}
{all_previous_outputs}
{layer_1_output}
{layer_2_output}
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

LayerGen saves:

- Project input
- Project attachments
- Layers
- Prompts
- Model choices
- Settings
- Outputs
- Chat history
- Flow state

API keys are saved only if `Save keys` is enabled.

## Temperature

Temperature controls how random or creative a model is.

Good coding range:

```text
0.2 to 0.7
```

Lower temperature:

```text
More predictable
More consistent
Less creative
```

Higher temperature:

```text
More varied
More creative
More likely to make mistakes
```

## Troubleshooting

### The app will not run

Try running it from Command Prompt:

```cmd
cd C:\Users\haoqi\Documents\Codex\2026-08-03\thi\outputs
python LayerGen.py
```

If `python` does not work, try:

```cmd
py LayerGen.py
```

### The model dropdown is empty

Try:

```text
Models > Load from provider
```

For Hugging Face, try:

```text
Models > Search Hugging Face models...
```

If the provider needs an API key, add it first.

### Hugging Face says a model is not supported

Use the Hugging Face search menu and pick from the eligible results instead of typing a model manually.

For image input, use:

```text
Vision / image input
```

For Qwen coding models, search:

```text
qwen coder
```

For Gemma models, search:

```text
gemma
```

### Hugging Face returns HTTP 401

The token is missing, invalid, or does not have the right permission.

Add a Hugging Face token here:

```text
Settings > API key > Enter API key...
```

### Hugging Face returns HTTP 403

Your token or account may not be allowed to use the selected provider route.

Check that:

- Your token has Inference Providers permission.
- Your Hugging Face account can use the selected provider.
- Billing or credits are available if the provider requires them.

### A model takes too long

Try a short test:

```text
Max tokens: 20
Prompt: hello
```

If that works, increase max tokens again.

Large models can take much longer than small models.

### Chat reruns too much

Use the `Chat with` dropdown in the Chat tab.

The dropdown controls which layer is fine-tuned. Chat should update that layer and all layers after it, but it should not rerun earlier layers.

### Saved sessions do not include attached files

LayerGen saves local attachment paths, not full file contents.

Keep attached files in the same location if you want old sessions to keep finding them.

## Project Files

Main app:

```text
LayerGen.py
```

README:

```text
README_LayerGen.md
```

Synced compatibility copies:

```text
code_generator_app.py
three_layer_code_generator_gui.py
```

Backups may also appear in the folder. They are kept so you can return to older versions if a large change does not work the way you wanted.
