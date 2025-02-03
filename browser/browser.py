from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QSplitter
)

from browser.chat_window import ChatWindow
from lib.models import Role


class AnalyzingWebPage(QWebEnginePage):
    def __init__(self, browser):
        super().__init__(browser)
        self.loadFinished.connect(self._on_load_finished)
        self.browser = browser

    def _on_load_finished(self, ok):
        if ok:
            self.browser.chat_window.add_message(f"Page loaded, extracting content...", Role.WEB_BROWSER)
            self.runJavaScript("""
                (function() {
                    function getReaderContent() {
                        // Helper function to get text content while preserving some structure
                        function extractText(element) {
                            let text = '';

                            // Handle headings specially
                            if (element.tagName && element.tagName.match(/^H[1-6]$/)) {
                                return '## ' + element.textContent.trim() + '\\n\\n';
                            }

                            // Handle paragraphs and lists
                            if (element.tagName === 'P' || element.tagName === 'LI') {
                                return element.textContent.trim() + '\\n\\n';
                            }

                            // Skip hidden elements and unwanted content
                            if (element.style && (
                                element.style.display === 'none' ||
                                element.style.visibility === 'hidden'
                            )) {
                                return '';
                            }

                            // Skip unwanted elements
                            const unwantedTags = ['SCRIPT', 'STYLE', 'NAV', 'HEADER', 'FOOTER', 
                                                'ASIDE', 'NOSCRIPT', 'AD', 'IFRAME'];
                            if (unwantedTags.includes(element.tagName)) {
                                return '';
                            }

                            // Process child nodes
                            for (const child of element.childNodes) {
                                if (child.nodeType === Node.TEXT_NODE) {
                                    text += child.textContent.trim() + ' ';
                                } else if (child.nodeType === Node.ELEMENT_NODE) {
                                    text += extractText(child);
                                }
                            }

                            return text;
                        }

                        // Try to find main content
                        const mainSelectors = [
                            'article',
                            '[role="main"]',
                            'main',
                            '#main-content',
                            '#content',
                            '.main-content',
                            '.content',
                            '.post-content'
                        ];

                        let mainContent = null;
                        for (const selector of mainSelectors) {
                            const element = document.querySelector(selector);
                            if (element) {
                                mainContent = element;
                                break;
                            }
                        }

                        // If no main content found, use body
                        const content = mainContent ? extractText(mainContent) : extractText(document.body);

                        return {
                            title: document.title,
                            url: window.location.href,
                            description: document.querySelector('meta[name="description"]')?.content || '',
                            content: content.replace(/\\s+/g, ' ').trim(),
                            readingTime: Math.ceil(content.split(/\\s+/).length / 200), // Approximate reading time in minutes
                            timestamp: new Date().toISOString()
                        };
                    }

                    return getReaderContent();
                })();
            """, self._handle_page_content)

    def _handle_page_content(self, page_data):
        if isinstance(page_data, (str, int, float)):
            content = str(page_data)
            page_data = {
                'title': 'Unknown Title',
                'description': '',
                'content': content,
                'url': self.url().toString()
            }

        if page_data and self.browser:
            print("\n=== Extracted Reader Content ===")
            print(f"URL: {page_data.get('url', 'Unknown URL')}")
            print(f"Title: {page_data.get('title', '')}")
            print(f"Description: {page_data.get('description', '')}")
            print(f"Reading Time: ~{page_data.get('readingTime', 0)} minutes")
            print("\nContent Preview:")
            print(page_data.get('content', '')[:1000])
            print("=== End Reader Content ===\n")

            content = page_data.get('content', '').strip()
            if not content:
                self.browser.chat_window.add_message(
                    "No readable content found on this page.",
                    Role.WEB_BROWSER
                )
                return

            prompt = f"""Analyzing webpage in reader mode:
    URL: {page_data.get('url')}
    Title: {page_data.get('title')}
    Description: {page_data.get('description')}
    Estimated Reading Time: {page_data.get('readingTime')} minutes

    Content:
    {content[:2000]}...

    Please provide:
    1. A concise summary of the main content and your thoughts on political bias
    2. Key points or main topics covered
    3. Important facts or data presented
    4. Writing style and tone observations
    5. Suggested related topics for further reading"""

            self.browser.chat_window.add_message("🔍 Analyzing reader-mode content...", Role.WEB_BROWSER)

            if hasattr(self.browser, 'llm_integration'):
                self.browser.handle_chat_message(prompt)
            else:
                self.browser.chat_window.add_message(
                    "Cannot analyze - LLM not initialized",
                    Role.WEB_BROWSER
                )

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sage Browser")
        self.setup_ui()

    def setup_ui(self):
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Create splitter for browser and chat
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Browser section
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)

        # Navigation controls
        nav_layout = QHBoxLayout()
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        back_btn = QPushButton("←")
        back_btn.clicked.connect(self.back)
        forward_btn = QPushButton("→")
        forward_btn.clicked.connect(self.forward)
        reload_btn = QPushButton("↻")
        reload_btn.clicked.connect(self.reload)
        analyze_btn = QPushButton("🔍 Analyze")
        analyze_btn.clicked.connect(self.analyze_current_page)

        nav_layout.addWidget(back_btn)
        nav_layout.addWidget(forward_btn)
        nav_layout.addWidget(reload_btn)
        nav_layout.addWidget(self.url_bar)
        nav_layout.addWidget(analyze_btn)

        # Web view setup
        self.web_view = QWebEngineView()
        self.web_page = AnalyzingWebPage(self)
        self.web_view.setPage(self.web_page)
        self.web_view.setUrl(QUrl("https://www.cnbc.com"))
        self.web_view.urlChanged.connect(self.update_url)

        browser_layout.addLayout(nav_layout)
        browser_layout.addWidget(self.web_view)

        # Chat section
        self.chat_window = ChatWindow()
        self.chat_window.message_sent.connect(self.handle_chat_message)

        # Add widgets to splitter
        splitter.addWidget(browser_widget)
        splitter.addWidget(self.chat_window)

        # Set initial sizes (70% browser, 30% chat)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

        # Set window size
        self.resize(1200, 800)

    def navigate_to_url(self):
        qurl = QUrl(self.url_bar.text())
        if not qurl.scheme():
            qurl.setScheme("http")
        self.web_view.setUrl(qurl)

    def update_url(self, url):
        self.url_bar.setText(url.toString())

    def back(self):
        self.web_view.back()

    def forward(self):
        self.web_view.forward()

    def reload(self):
        self.web_view.reload()

    def analyze_current_page(self):
        self.web_page._on_load_finished(True)

    def handle_chat_message(self, message: str):
        if hasattr(self, 'llm_integration'):
            self.llm_integration.handle_user_message(message)