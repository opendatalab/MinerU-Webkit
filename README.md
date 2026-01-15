# MinerU-Webkit

**MinerU-Webkit** is a high-performance web content conversion toolkit builtl. It intelligently parses and extracts structured content from HTML web pages, supporting various output formats and customizable configurations.

## Key Features

- 🚀 **High-Performance Parsing**: Leverages Python and lxml for fast processing and low memory footprint.
- 🎯 **Multi-Format Output**: Supports Markdown, JSON, Txt, and other structured formats to meet diverse needs.
- ⚡ **Asynchronous Processing**: Supports asynchronous batch processing for improved efficiency with multiple web pages.
- 🌐 **Dual-Protocol Support**: A unified service gateway that supports both Model Context Protocol (MCP) and traditional RESTful APIs enables your web conversion service to be seamlessly invoked by both AI agents (such as Claude, Cursor) and traditional web clients and mobile applications.
- 🔧 **Error Resilience**: Incorporates robust error recovery mechanisms to handle malformed HTML gracefully.

## Installation

### Prerequisites

- Python >= 3.13

#### Basic Installation (Core Functionality)

For basic usage of MinerU-Webkit, install with core dependencies only:

```bash
# Clone the repository
git clone https://github.com/ccprocessor/MinerU-Webkit.git
cd MinerU-Webkit

# Dependencies from pyproject.toml are automatically installed
uv sync --package webpage_converter
```

## Quick Start

### 1. Basic Usage

```python
from webpage_converter.convert import convert_html_to_structured_data

# Extract main content from HTML
html_content = """
<html>
  <body>
    <div>
    <h1>This is a title</h1>
    <p>This is a paragraph</p>
    <p>This is another paragraph</p>
    </div>
    <div>
    <p>Related content</p>
    <p>Advertising content</p>
    </div>
  </body>
</html>
"""
result = convert_html_to_structured_data(main_html=html_content, url="http://www.example.com", output_format='mm_md')
print(result)
```

## Configuration

### Configuration Options

| Parameter           | Type | Default             | Description                                                                        |
| ------------------- | ---- | ------------------- | ---------------------------------------------------------------------------------- |
| `main_html`         | str  | **Required**        | HTML that needs to be converted                                                    |
| `url`               | str  | https://example.com | The URL link for HTML is required in mm_md mode                                    |
| `output_format`     | str  | mm_md               | Conversion format, supports mm_md (markdown), md (markdown with images), json, txt |
| `use_raw_image_url` | bool | True                | Whether to use the original image URL (only valid for mm_md format)                |

# TODO

# contributors

![contributors](https://contrib.rocks/image?repo=ccprocessor/llm-webkit-mirror)
