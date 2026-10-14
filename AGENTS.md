# AGENTS.md - Repository Guide for AI Coding Agents

This is the Chinese translation of "Designing Data-Intensive Applications, 2nd Edition" (DDIA2), built as a Hugo static site with the Hextra theme.

## Build Commands

### Development
```bash
# Start development server (with live reload)
make dev
# or
hugo serve

# Build for production
make build
# or
hugo build
```

### EPUB Generation
```bash
# Generate EPUB book (requires pandoc and Python)
make epub
# or
bin/epub
```

### PDF Generation
```bash
# Generate PDF book (requires pandoc + LaTeX)
make pdf
# or
bin/pdf
# or (Python version with more options)
bin/pdf.py --help
```

### Translation
```bash
# Convert Simplified Chinese (zh) to Traditional Chinese (tw)
make translate
# or
bin/zh-tw.py
```

## Project Structure

```
├── content/           # Markdown content
│   ├── zh/           # Simplified Chinese (2nd edition) - PRIMARY
│   ├── tw/           # Traditional Chinese (auto-converted from zh)
│   ├── v1/           # Simplified Chinese (1st edition)
│   ├── v1_tw/        # Traditional Chinese (1st edition)
│   └── en/           # English original (reference)
├── hugo.yaml         # Hugo site configuration
├── go.mod            # Go module for Hugo theme
├── layouts/          # Custom Hugo templates
│   └── shortcodes/   # Custom shortcodes
├── static/           # Static assets (images, etc.)
├── bin/              # Utility scripts
│   ├── zh-tw.py      # Chinese translation converter
│   ├── epub          # EPUB generation script
│   ├── pdf           # PDF generation script (shell)
│   ├── pdf.py        # PDF generation script (Python)
│   ├── preprocess-epub.py
│   └── toc.py        # Table of contents generator
├── i18n/             # Internationalization strings
└── .github/workflows/# CI/CD for GitHub Pages
```

## Code Style Guidelines

### Markdown Content
- Use YAML frontmatter with `title`, `weight`, and `breadcrumbs`:
  ```yaml
  ---
  title: "Chapter Title"
  weight: 101
  breadcrumbs: false
  ---
  ```
- Use Chinese punctuation for Chinese content（full-width brackets, Chinese commas）
- Use `{{< figure >}}` shortcode for tables with captions:
  ```markdown
  {{< figure id="table_id" title="Table Title" class="w-full my-4" >}}
  | Column | Column |
  |--------|--------|
  | Data   | Data   |
  ```
- Use callout blocks for notes/tips:
  ```markdown
  > [!NOTE]
  > Note content

  > [!TIP]
  > Tip content
  ```
- Use explicit anchors for section links: `## Section Title {#sec_custom_id}`
- Mathematical expressions: use `\( inline \)` and `\[ block \]` or `$$ block $$`

### Internal Links
- Cross-reference chapters using relative paths: `[Chapter 1](/ch1)`
- For anchors: `[Section](/ch1#section-id)`
- The zh-tw.py script automatically converts `/ch1` to `/tw/ch1` for Traditional Chinese

### Python Scripts
- Use Python 3 with type hints where applicable
- Scripts in `bin/` should be executable (`chmod +x`)
- Use `opencc` library for Chinese conversion
- Follow existing patterns in `zh-tw.py` for URL handling

### Hugo Configuration
- Site config is in `hugo.yaml` (not config.toml)
- Theme: Hextra (imported via Go modules)
- Math rendering: enabled via goldmark passthrough
- Multi-language: zh (default), tw, v1, v1_tw

## Common Tasks

### Adding a New Chapter
1. Create file in `content/zh/chN.md`
2. Add YAML frontmatter with appropriate weight
3. Use weight pattern: 101, 102, ... for chapters
4. Add to `_index.md` if needed for navigation
5. Run `make translate` to update Traditional Chinese version

### Fixing Translation Issues
1. Edit files in `content/zh/` (source of truth)
2. Run `make translate` to regenerate `content/tw/`
3. Do NOT edit `content/tw/` directly - changes will be overwritten

### Updating Shortcodes
- Custom shortcodes go in `layouts/shortcodes/`
- Refer to Hextra documentation for built-in shortcodes

## Dependencies

### Required Tools
- Hugo Extended v0.155.3+ (for SCSS processing)
- Go 1.22+ (for Hugo modules)
- Python 3.8+ with `opencc-python-reimplemented`
- Pandoc (for EPUB and PDF generation)
- XeLaTeX or LuaLaTeX (for PDF generation)

### Install Dependencies
```bash
# Hugo (macOS)
brew install hugo

# Go
brew install go

# Python dependencies
cd bin && pip install opencc-python-reimplemented

# Pandoc
brew install pandoc

# LaTeX (for PDF generation)
brew install --cask mactex
# or
brew install texlive
```

## CI/CD

GitHub Actions workflow (`.github/workflows/pages.yaml`):
- Triggers on push to `main`
- Builds with Hugo (production environment)
- Deploys to GitHub Pages
- Uses Hugo v0.155.3 and Go 1.26

## Notes

- This is a documentation/translation project, not a software project
- No traditional "tests" - verify by building the site
- Content changes should be made in Simplified Chinese (`content/zh/`) only
- Traditional Chinese is auto-generated - never edit `content/tw/` manually
- EPUB and PDF generation require preprocessing to convert Hugo shortcodes to standard Markdown
