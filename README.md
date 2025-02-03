# Sage Browser

Sage Browser is an AI-powered web browser that combines traditional web browsing capabilities with integrated AI analysis. It features a split interface with a web view and an interactive chat window, allowing users to analyze web content and engage in conversations with an AI assistant.

## Features

- **Integrated Web Browser**: Built on PyQt6 and QtWebEngine for robust web browsing capabilities
- **AI-Powered Analysis**: Local LLM integration using DeepSeek Distill Llama 3 8B quantized model
- **Split Interface**: Side-by-side browsing and chat experience
- **Reader Mode**: Automatic content extraction and analysis
- **Real-time Chat**: Interactive conversation with AI assistant
- **Local Processing**: All AI processing happens locally using llama.cpp

## Requirements

- Python 3.12
- Qt6
- OpenBLAS (for optimized LLM inference)
- At least 16GB RAM recommended
- 8GB+ disk space for AI model

## Installation

1. Clone the repository:
```bash
git clone https://github.com/allnash/sage-browser.git
cd sage-browser
```

2. Install system dependencies (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install python3.12 python3.12-dev python3-pip build-essential cmake
sudo apt-get install qt6-base-dev qt6-webengine-dev libgl1-mesa-dev
```

3. Set up Python environment:
```bash
pip install pipenv
pipenv install
```

4. Install optimized llama-cpp-python:
```bash
chmod +x install_packages.sh
./install_packages.sh
```

5. Download the AI model:
- Create an `ai_models` directory
- Download DeepSeek-R1-Distill-Llama-8B-Q8_0.gguf from Hugging Face
  - `wget https://huggingface.co/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF/resolve/main/DeepSeek-R1-Distill-Llama-8B-Q8_0.gguf`
- Place the model file in the `ai_models` directory

## Usage

1. Activate the Python environment:
```bash
pipenv shell
```

2. Run the browser:
```bash
python main.py
```

### Browser Controls
- Navigation bar with back, forward, and reload buttons
- URL input field
- Analyze button (🔍) to trigger AI analysis of current page

### Chat Interface
- Type messages in the input field
- Press Enter to send (Shift+Enter for new line)
- Chat history is displayed above
- AI responses stream in real-time

## Project Structure

```
.
├── browser/                 # Browser-related components
│   ├── browser.py          # Main browser window implementation
│   ├── chat_window.py      # Chat interface implementation
│   └── widgets/            # UI components
│       ├── chat_input.py   # Chat input widget
│       └── chat_message.py # Chat message display widget
├── lib/                    # Core functionality
│   ├── llm_api.py         # LLM interface and management
│   ├── llm_browser_integration.py # Browser-LLM integration
│   └── models.py          # Data models and types
├── ai_models/             # Directory for AI model files
├── install_packages.sh    # Installation script
└── main.py               # Application entry point
```

## Technical Details

### LLM Integration
- Uses llama.cpp for efficient local inference
- Streaming response generation
- Conversation history management
- Automatic token management

### Browser Features
- Built on QtWebEngine
- Reader mode with content extraction
- Async message handling
- Responsive UI with PyQt6

## Development

### Setting up development environment:
```bash
pipenv install
```

Development dependencies include:
- Black (code formatting)
- Flake8 (linting)
- Jupyter (notebooks for testing)
- IPython (interactive development)

## License

This project is licensed under MIT License. See the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Please ensure your code follows the project's style guidelines and includes appropriate tests.
