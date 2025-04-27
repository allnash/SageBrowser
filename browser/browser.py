from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QSplitter
)
import json
import threading
import time

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


class WebViewAutomator:
    def __init__(self, browser):
        self.browser = browser
        self.web_view = browser.web_view

    def fill_form(self, field_data):
        """Improved universal form field finder and filler with better field identification"""
        for field, value in field_data.items():
            js_script = f"""
            (function() {{
                // Universal form field finder with improved accuracy
                function findFormField(fieldText) {{
                    let foundElements = [];
                    const fieldLower = fieldText.toLowerCase();

                    // STRATEGY 1: Find by exact field label match
                    const textElements = document.querySelectorAll('label, h1, h2, h3, h4, h5, h6, p, span, div, legend, [role="heading"]');
                    for (const el of textElements) {{
                        // Skip invisible elements
                        if (!isVisible(el)) continue;

                        // Check for EXACT matches first (highest priority)
                        const trimmedContent = el.textContent.trim();
                        if (trimmedContent.toLowerCase() === fieldLower) {{
                            // We found an exact match! Now find its input

                            // If it's a label with 'for' attribute
                            if (el.tagName === 'LABEL' && el.htmlFor) {{
                                const input = document.getElementById(el.htmlFor);
                                if (input && isInputElement(input)) {{
                                    foundElements.push({{ element: input, method: 'exact_label_match', score: 100 }});
                                    // Exact match is so good we can return immediately
                                    return {{ element: input, method: 'exact_label_match', score: 100 }};
                                }}
                            }}

                            // Look for input in the same section
                            const section = findCommonContainer(el);
                            if (section) {{
                                const inputs = section.querySelectorAll('input, textarea, select, [role="radio"], [role="checkbox"], [contenteditable="true"]');
                                if (inputs.length > 0) {{
                                    // If there's only one input, it's almost certainly the right one
                                    if (inputs.length === 1) {{
                                        foundElements.push({{ element: inputs[0], method: 'exact_text_match_single_input', score: 99 }});
                                    }} else {{
                                        // Multiple inputs, find closest one that's not a radio/checkbox
                                        // or take first input as fallback
                                        const textInputs = Array.from(inputs).filter(input => 
                                            !['radio', 'checkbox'].includes(input.type) && 
                                            input.getAttribute('role') !== 'radio' &&
                                            input.getAttribute('role') !== 'checkbox');

                                        if (textInputs.length > 0) {{
                                            const closestInput = textInputs[0]; // First is often correct in forms
                                            foundElements.push({{ element: closestInput, method: 'exact_text_match_multi_input', score: 95 }});
                                        }} else {{
                                            foundElements.push({{ element: inputs[0], method: 'exact_text_match_fallback', score: 90 }});
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}

                    // STRATEGY 2: Find field by visual proximity to matching label text
                    // This is crucial for finding fields in complex forms
                    for (const el of textElements) {{
                        if (!isVisible(el)) continue;

                        // Check for containing matches
                        const trimmedContent = el.textContent.trim();
                        if (trimmedContent.toLowerCase().includes(fieldLower) && 
                            !foundElements.some(f => f.score > 90)) {{ // Skip if we already have very good matches

                            // Check if this is a heading element
                            const isHeading = /^H[1-6]$/.test(el.tagName) || 
                                             el.getAttribute('role') === 'heading' ||
                                             window.getComputedStyle(el).fontWeight >= 600;

                            // Find the form section containing this label
                            const section = findCommonContainer(el);
                            if (section) {{
                                // Get all inputs within this section
                                const allInputs = section.querySelectorAll(
                                    'input, textarea, select, [role="radio"], [role="checkbox"], [contenteditable="true"]'
                                );

                                if (allInputs.length > 0) {{
                                    // Calculate visual position of the label
                                    const labelRect = el.getBoundingClientRect();

                                    // Get inputs positioned below this label (form fields are typically below labels)
                                    // or get all inputs if no inputs found below
                                    let relevantInputs = Array.from(allInputs).filter(input => {{
                                        const inputRect = input.getBoundingClientRect();
                                        return inputRect.top >= labelRect.bottom || // input is below label
                                               (inputRect.bottom >= labelRect.top && inputRect.top <= labelRect.bottom); // input overlaps label
                                    }});

                                    // If no inputs found below, consider all inputs in the section
                                    if (relevantInputs.length === 0) {{
                                        relevantInputs = Array.from(allInputs);
                                    }}

                                    // Filter out hidden inputs
                                    relevantInputs = relevantInputs.filter(input => isVisible(input));

                                    if (relevantInputs.length > 0) {{
                                        // If there's only one input, it's very likely the correct field
                                        if (relevantInputs.length === 1) {{
                                            const score = isHeading ? 94 : 88; // Headings are more reliable
                                            foundElements.push({{ 
                                                element: relevantInputs[0], 
                                                method: 'single_field_section', 
                                                score: score
                                            }});
                                        }}
                                        // For multiple inputs, find the closest one vertically and horizontally
                                        else {{
                                            // Score each input by its position relative to the label
                                            const scoredInputs = relevantInputs.map(input => {{
                                                const inputRect = input.getBoundingClientRect();

                                                // Calculate vertical and horizontal distance
                                                const verticalDist = Math.abs(inputRect.top - labelRect.bottom);
                                                const horizontalOverlap = Math.max(0, 
                                                    Math.min(inputRect.right, labelRect.right) - 
                                                    Math.max(inputRect.left, labelRect.left)
                                                );

                                                // Check if input is a text field (preferred over radio/checkbox)
                                                const isTextField = input.tagName === 'INPUT' && 
                                                                  !['radio', 'checkbox'].includes(input.type);

                                                // Calculate score based on positioning and input type
                                                // Lower vertical distance is better, horizontal overlap is good
                                                let posScore = (1000 - verticalDist) + (horizontalOverlap > 0 ? 200 : 0);

                                                // Prefer text fields to radio/checkbox for most field names
                                                // Unless the field name suggests boolean/multiple choice
                                                const isBooleanField = /yes|no|agree|disagree|accept|true|false/i.test(fieldLower);
                                                if (isTextField && !isBooleanField) posScore += 300;

                                                return {{ input, posScore }};
                                            }});

                                            // Sort by score
                                            scoredInputs.sort((a, b) => b.posScore - a.posScore);

                                            // Take the best match
                                            if (scoredInputs.length > 0) {{
                                                const bestInput = scoredInputs[0].input;
                                                const score = isHeading ? 92 : 86; // Headings are more reliable
                                                foundElements.push({{ 
                                                    element: bestInput, 
                                                    method: 'positioned_field', 
                                                    score: score
                                                }});
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}

                    // STRATEGY 3: Find field by direct selectors (ID, name, placeholder)
                    // This works well for properly semantic forms
                    const directSelectors = [
                        // Exact matches
                        `#${{fieldText}}`,                        // id exactly matches
                        `[name="${{fieldText}}"]`,                // name exactly matches
                        `[placeholder="${{fieldText}}"]`,         // placeholder exactly matches
                        `[aria-label="${{fieldText}}"]`,          // aria-label exactly matches

                        // Contains matches (case insensitive)
                        `[id*="${{fieldText}}" i]`,               // id contains
                        `[name*="${{fieldText}}" i]`,             // name contains
                        `input[placeholder*="${{fieldText}}" i]`, // placeholder contains
                        `[aria-label*="${{fieldText}}" i]`        // aria-label contains
                    ];

                    for (const selector of directSelectors) {{
                        try {{
                            const element = document.querySelector(selector);
                            if (element && isInputElement(element) && isVisible(element)) {{
                                // Determine score based on match type
                                let score = 85;
                                if (selector.includes('*=')) {{
                                    score = 75; // Partial matches are less reliable
                                }}

                                // Exact ID match is very reliable
                                if (selector === `#${{fieldText}}`) score = 98;

                                foundElements.push({{ element, method: 'direct_selector', score: score }});
                            }}
                        }} catch (e) {{
                            // Invalid selector, continue
                        }}
                    }}

                    // STRATEGY 4: Special case for complex forms like Google Forms
                    // Look for headings/questions and their associated inputs
                    const allHeadings = document.querySelectorAll('.M7eMe, [role="heading"], .freebirdFormviewerViewItemsItemItemTitle, h1, h2, h3, h4, h5');
                    for (const heading of allHeadings) {{
                        if (!isVisible(heading)) continue;

                        const headingText = heading.textContent.trim();
                        if (headingText.toLowerCase().includes(fieldLower)) {{
                            // For Google Forms, we need to find the container with the input
                            let container = heading;
                            while (container && 
                                   !container.classList.contains('Qr7Oae') &&
                                   !container.classList.contains('freebirdFormviewerViewItemsItemItem') &&
                                   container.tagName !== 'BODY') {{
                                container = container.parentElement;
                            }}

                            if (container) {{
                                // Google Form inputs often have these classes
                                const googleInputs = container.querySelectorAll('.whsOnd, .rFrNMe input, [role="radio"], [role="checkbox"]');

                                if (googleInputs.length > 0) {{
                                    // Prefer text inputs unless field suggests radio/checkbox
                                    const isBooleanField = /yes|no|agree|disagree|accept|true|false/i.test(fieldLower);

                                    let bestInput;
                                    if (isBooleanField) {{
                                        // For boolean fields, prefer radio/checkboxes
                                        bestInput = Array.from(googleInputs).find(el => 
                                            el.type === 'radio' || 
                                            el.type === 'checkbox' || 
                                            el.getAttribute('role') === 'radio' ||
                                            el.getAttribute('role') === 'checkbox'
                                        ) || googleInputs[0];
                                    }} else {{
                                        // For text fields, prefer text inputs
                                        bestInput = Array.from(googleInputs).find(el => 
                                            el.type === 'text' || 
                                            el.type === 'email' || 
                                            el.tagName === 'TEXTAREA'
                                        ) || googleInputs[0];
                                    }}

                                    foundElements.push({{ 
                                        element: bestInput, 
                                        method: 'google_form_pattern', 
                                        score: 96  // Very reliable for Google Forms
                                    }});
                                }}
                            }}
                        }}
                    }}

                    // STRATEGY 5: Positional strategy for forms with no labels
                    // This is a last resort for poorly designed forms
                    if (foundElements.length === 0) {{
                        const allVisibleInputs = Array.from(document.querySelectorAll('input, textarea, select'))
                            .filter(el => isVisible(el));

                        // Create a simple mapping of input positions to potential field names
                        const fieldNames = extractPotentialFieldNames();

                        // Find field index
                        const fieldIndex = fieldNames.findIndex(name => 
                            name.toLowerCase() === fieldLower ||
                            name.toLowerCase().includes(fieldLower)
                        );

                        if (fieldIndex >= 0 && fieldIndex < allVisibleInputs.length) {{
                            foundElements.push({{ 
                                element: allVisibleInputs[fieldIndex], 
                                method: 'positional', 
                                score: 60  // Low confidence
                            }});
                        }}
                    }}

                    // Sort by score (highest first) and return best match
                    foundElements.sort((a, b) => b.score - a.score);

                    if (foundElements.length > 0) {{
                        return foundElements[0];
                    }}

                    return {{ element: null, method: 'none', score: 0 }};
                }}

                // Extract potential field names from visible text
                function extractPotentialFieldNames() {{
                    const potentialLabels = [];
                    const textElements = document.querySelectorAll('label, h1, h2, h3, h4, h5, h6, p, span, div, legend');

                    for (const el of textElements) {{
                        if (isVisible(el) && el.textContent.trim()) {{
                            potentialLabels.push(el.textContent.trim());
                        }}
                    }}

                    return potentialLabels;
                }}

                // Find the common container for a form element
                function findCommonContainer(element) {{
                    let current = element;

                    // First look for standard form containers
                    while (current && current.tagName !== 'BODY') {{
                        // Standard form containers
                        if (current.tagName === 'FORM' || 
                            current.tagName === 'FIELDSET' ||
                            current.classList.contains('form-group') ||
                            current.classList.contains('form-field') ||
                            current.classList.contains('field-container') ||
                            current.classList.contains('input-group') ||
                            current.getAttribute('role') === 'group') {{
                            return current;
                        }}

                        // Google Forms specific containers
                        if (current.classList.contains('Qr7Oae') ||
                            current.classList.contains('freebirdFormviewerViewItemsItemItem') ||
                            current.classList.contains('geS5n')) {{
                            return current;
                        }}

                        // Look for any container with both text and input
                        const hasText = !!current.textContent.trim();
                        const hasInput = !!current.querySelector('input, textarea, select, [role="radio"]');

                        if (hasText && hasInput && current.children.length < 15) {{
                            return current;
                        }}

                        current = current.parentElement;
                    }}

                    // Fallback to nearest common container with other inputs
                    current = element;
                    while (current && current.tagName !== 'BODY') {{
                        if (current.querySelectorAll('input, textarea, select').length > 0) {{
                            return current;
                        }}

                        current = current.parentElement;
                    }}

                    return element.parentElement;
                }}

                // Check if element is a valid input element
                function isInputElement(element) {{
                    if (!element) return false;

                    // Standard form inputs
                    if (element.tagName === 'INPUT' || 
                        element.tagName === 'TEXTAREA' || 
                        element.tagName === 'SELECT') return true;

                    // ARIA roles
                    const role = element.getAttribute('role');
                    if (role === 'textbox' || role === 'combobox' || 
                        role === 'radio' || role === 'checkbox') return true;

                    // Contenteditable
                    if (element.getAttribute('contenteditable') === 'true') return true;

                    return false;
                }}

                // Check if element is visible
                function isVisible(element) {{
                    if (!element) return false;

                    // Get computed style
                    const style = window.getComputedStyle(element);
                    if (style.display === 'none' || 
                        style.visibility === 'hidden' || 
                        style.opacity === '0') {{
                        return false;
                    }}

                    // Check dimensions
                    const rect = element.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) {{
                        return false;
                    }}

                    return true;
                }}

                // MAIN EXECUTION LOGIC
                // Find the element
                const result = findFormField('{field}');
                if (!result.element) {{
                    return {{ success: false, message: `Could not find field: {field}` }};
                }}

                // Make element visible and in view
                if (result.element.scrollIntoView) {{
                    result.element.scrollIntoView({{ behavior: 'auto', block: 'center' }});
                }}

                // Focus and click the element
                result.element.focus();

                try {{
                    // Handle different element types
                    const element = result.element;

                    if (element.tagName === 'SELECT') {{
                        // Handle select dropdowns
                        let optionFound = false;

                        for (const option of element.options) {{
                            if (option.text.toLowerCase().includes('{value}'.toLowerCase()) || 
                                option.value.toLowerCase() === '{value}'.toLowerCase()) {{
                                element.value = option.value;
                                optionFound = true;
                                break;
                            }}
                        }}

                        if (optionFound) {{
                            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }} else {{
                            return {{ success: false, message: `Option '{value}' not found in dropdown` }};
                        }}
                    }}
                    else if (element.type === 'checkbox' || 
                             element.getAttribute('role') === 'checkbox') {{
                        // Handle checkboxes
                        if ('{value}'.toLowerCase() === 'true' || 
                            '{value}'.toLowerCase() === 'yes' || 
                            '{value}'.toLowerCase() === 'checked' || 
                            '{value}'.toLowerCase() === 'on') {{
                            // Check the box if not already checked
                            if (!element.checked) {{
                                element.click();
                            }}
                        }} else if ('{value}'.toLowerCase() === 'false' || 
                                    '{value}'.toLowerCase() === 'no' || 
                                    '{value}'.toLowerCase() === 'unchecked' || 
                                    '{value}'.toLowerCase() === 'off') {{
                            // Uncheck the box if checked
                            if (element.checked) {{
                                element.click();
                            }}
                        }} else {{
                            // Default to clicking
                            element.click();
                        }}
                    }}
                    else if (element.type === 'radio' || 
                             element.getAttribute('role') === 'radio') {{
                        // For radio buttons, we need to handle group behavior
                        // Try to find all radios in the same group
                        let radioGroup;
                        const name = element.name;

                        if (name) {{
                            // Find all radios with the same name
                            radioGroup = document.querySelectorAll(`input[name="${{name}}"]`);
                        }} else if (element.getAttribute('role') === 'radio') {{
                            // Find all radio roles in the same container
                            let container = element.closest('[role="radiogroup"]') || 
                                           element.closest('.Qr7Oae') || 
                                           element.closest('form') || 
                                           document;
                            radioGroup = container.querySelectorAll('[role="radio"]');
                        }} else {{
                            // Just click this specific radio
                            element.click();
                            radioGroup = [element];
                        }}

                        // If we want a specific value and have multiple radios
                        if (radioGroup.length > 1 && '{value}' && 
                            '{value}'.toLowerCase() !== 'true' && 
                            '{value}'.toLowerCase() !== 'yes') {{

                            let foundMatch = false;

                            // Try to find radio by value, label, or aria-label
                            for (const radio of radioGroup) {{
                                // Check radio value
                                if (radio.value && radio.value.toLowerCase() === '{value}'.toLowerCase()) {{
                                    radio.click();
                                    foundMatch = true;
                                    break;
                                }}

                                // Check associated label
                                let label = null;
                                if (radio.id) {{
                                    label = document.querySelector(`label[for="${{radio.id}}"]`);
                                }} else {{
                                    // Look for nearby or parent label
                                    label = radio.closest('label') || 
                                            Array.from(radio.parentElement.querySelectorAll('label')).find(l => 
                                                l.textContent.toLowerCase().includes('{value}'.toLowerCase()));
                                }}

                                if (label && label.textContent.toLowerCase().includes('{value}'.toLowerCase())) {{
                                    radio.click();
                                    foundMatch = true;
                                    break;
                                }}

                                // Try to find by nearby text (Google Forms pattern)
                                const container = radio.closest('.nWQGrd, .docssharedWizToggleLabeledContainer');
                                if (container) {{
                                    const text = container.textContent.toLowerCase();
                                    if (text.includes('{value}'.toLowerCase())) {{
                                        radio.click();
                                        foundMatch = true;
                                        break;
                                    }}
                                }}
                            }}

                            if (!foundMatch) {{
                                // Default to the first radio if we couldn't find a match
                                radioGroup[0].click();
                            }}
                        }} else {{
                            // Default selection - just click this radio
                            element.click();
                        }}
                    }}
                    else {{
                        // Handle text inputs
                        if (element.value !== undefined) {{
                            // Clear existing value
                            element.value = '';
                            element.dispatchEvent(new Event('input', {{ bubbles: true }}));

                            // Set new value
                            element.value = '{value}';
                            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                        else if (element.getAttribute('contenteditable') === 'true') {{
                            // Handle contenteditable
                            element.textContent = '{value}';
                            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }}

                    // Final events for all field types
                    if (element.tagName !== 'SELECT') {{
                        element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}

                    element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    element.dispatchEvent(new Event('blur', {{ bubbles: true }}));

                    return {{ 
                        success: true, 
                        field: '{field}',
                        method: result.method,
                        score: result.score,
                        value: '{value}'
                    }};
                }} catch (e) {{
                    return {{ 
                        success: false, 
                        message: `Error filling field: ${{e.message}}`,
                        field: '{field}'
                    }};
                }}
            }})();
            """

            self.web_view.page().runJavaScript(js_script, self._handle_form_fill_result)

    def _handle_form_fill_result(self, result):
        """Handle the result of a form fill operation"""
        # Check if result is None to avoid AttributeError
        if result is None:
            self.browser.chat_window.add_message(
                f"⚠️ Error processing form fill result: received None",
                Role.WEB_BROWSER
            )
            return

        if result.get('success'):
            method = result.get('method', 'unknown')
            field = result.get('field', '')
            score = result.get('score', 'N/A')

            self.browser.chat_window.add_message(
                f"✓ Filled field '{field}' (found by {method})\n" +
                f"  Match confidence: {score}/100",
                Role.WEB_BROWSER
            )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to fill field '{result.get('field', '')}': {result.get('message', 'Unknown error')}",
                Role.WEB_BROWSER
            )

    def select_option(self, selector, value):
        """Select an option from a dropdown select element"""
        js_script = f"""
        (function() {{
            try {{
                // Function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return "/none";
                    if (element.id) return `//*[@id="${{element.id}}"]`;

                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;
                        if (!current || current.tagName === 'BODY' || current === document) break;
                    }}

                    return path || "/unknown";
                }}

                // Helper function to find elements by various attributes
                function findElement(selector) {{
                    // Try direct CSS selector first
                    try {{
                        const element = document.querySelector(selector);
                        if (element) return {{ element, method: 'css_selector' }};
                    }} catch (e) {{
                        // Invalid selector, continue with other methods
                    }}

                    // Try by ID
                    const elementById = document.getElementById(selector);
                    if (elementById) return {{ element: elementById, method: 'id' }};

                    // Try by name attribute
                    const elementByName = document.querySelector(`[name="${{selector}}"]`);
                    if (elementByName) return {{ element: elementByName, method: 'name' }};

                    // Try by label text
                    const labels = Array.from(document.querySelectorAll('label'));
                    for (const label of labels) {{
                        if (label.textContent.toLowerCase().includes(selector.toLowerCase())) {{
                            if (label.htmlFor) {{
                                const elementByLabel = document.getElementById(label.htmlFor);
                                if (elementByLabel) return {{ element: elementByLabel, method: 'label' }};
                            }}
                        }}
                    }}

                    // Try by placeholder
                    const elementByPlaceholder = document.querySelector(`[placeholder*="${{selector}}" i]`);
                    if (elementByPlaceholder) return {{ element: elementByPlaceholder, method: 'placeholder' }};

                    return {{ element: null, method: 'none' }};
                }}

                // Find the select element
                const result = findElement('{selector}');
                if (!result.element || result.element.tagName !== 'SELECT') {{
                    return {{ 
                        success: false, 
                        message: `Could not find select element with selector: ${{{selector}}}`
                    }};
                }}

                const select = result.element;
                const xpath = getXPath(select);
                let optionFound = false;
                let selectedText = '';

                // Try to find the option by value, text content, or index
                if ('{value}'.match(/^\\d+$/)) {{
                    // If value is a number, try to select by index
                    const index = parseInt('{value}');
                    if (index >= 0 && index < select.options.length) {{
                        select.selectedIndex = index;
                        optionFound = true;
                        selectedText = select.options[index].text;
                    }}
                }}

                // If not found by index or value is not a number, try value and text
                if (!optionFound) {{
                    for (let i = 0; i < select.options.length; i++) {{
                        const option = select.options[i];

                        // Try exact value match
                        if (option.value === '{value}') {{
                            select.selectedIndex = i;
                            optionFound = true;
                            selectedText = option.text;
                            break;
                        }}

                        // Try case-insensitive text content match
                        if (option.text.toLowerCase() === '{value}'.toLowerCase()) {{
                            select.selectedIndex = i;
                            optionFound = true;
                            selectedText = option.text;
                            break;
                        }}

                        // Try contains text match
                        if (option.text.toLowerCase().includes('{value}'.toLowerCase())) {{
                            select.selectedIndex = i;
                            optionFound = true;
                            selectedText = option.text;
                            break;
                        }}
                    }}
                }}

                // Dispatch change event
                if (optionFound) {{
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{ 
                        success: true, 
                        method: result.method,
                        xpath: xpath,
                        selectedText: selectedText,
                        selectedValue: select.value
                    }};
                }}

                return {{ 
                    success: false, 
                    message: `Option "${{'{value}'"}}" not found in select element` 
                }};
            }} catch (e) {{
                return {{ 
                    success: false, 
                    message: `Error selecting option: ${{e.message}}` 
                }};
            }}
        }})();
        """

        self.web_view.page().runJavaScript(js_script, self._handle_select_option_result)

    def _handle_select_option_result(self, result):
        """Handle the result of a select option operation"""
        if result.get('success'):
            self.browser.chat_window.add_message(
                f"✓ Selected option '{result.get('selectedText')}' (value: {result.get('selectedValue')})\n" +
                f"  Found by: {result.get('method')}\n" +
                f"  XPath: {result.get('xpath')}",
                Role.WEB_BROWSER
            )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to select option: {result.get('message')}",
                Role.WEB_BROWSER
            )

    def check_radio(self, selector, value=None):
        """Select a radio button"""
        js_script = f"""
        (function() {{
            try {{
                // Function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return "/none";
                    if (element.id) return `//*[@id="${{element.id}}"]`;

                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;
                        if (!current || current.tagName === 'BODY' || current === document) break;
                    }}

                    return path || "/unknown";
                }}

                // Strategy 1: If value is provided, look for a radio with that value
                if ('{value}') {{
                    // Try to find by selector + value
                    let radioButton = null;

                    // Try by CSS selector + value
                    try {{
                        radioButton = document.querySelector(`${{'{selector}'}}[value="${{'{value}'}}"]`);
                    }} catch (e) {{
                        // Invalid selector, continue with other methods
                    }}

                    // Try by name attribute + value
                    if (!radioButton) {{
                        const radiosByName = document.querySelectorAll(`[name="${{'{selector}'}}"]`);
                        for (const radio of radiosByName) {{
                            if (radio.type === 'radio' && radio.value === '{value}') {{
                                radioButton = radio;
                                break;
                            }}
                        }}
                    }}

                    // Try by general radio + value
                    if (!radioButton) {{
                        const allRadios = document.querySelectorAll('input[type="radio"]');
                        for (const radio of allRadios) {{
                            if (radio.value === '{value}') {{
                                radioButton = radio;
                                break;
                            }}
                        }}
                    }}

                    // Try by label text
                    if (!radioButton) {{
                        const labels = Array.from(document.querySelectorAll('label'));
                        for (const label of labels) {{
                            if (label.textContent.trim().toLowerCase() === '{value}'.toLowerCase()) {{
                                if (label.htmlFor) {{
                                    const radioByLabel = document.getElementById(label.htmlFor);
                                    if (radioByLabel && radioByLabel.type === 'radio') {{
                                        radioButton = radioByLabel;
                                        break;
                                    }}
                                }} else {{
                                    const nestedRadio = label.querySelector('input[type="radio"]');
                                    if (nestedRadio) {{
                                        radioButton = nestedRadio;
                                        break;
                                    }}
                                }}
                            }}
                        }}
                    }}

                    if (radioButton) {{
                        const radioXPath = getXPath(radioButton);
                        radioButton.checked = true;
                        radioButton.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        // Also trigger click event for additional compatibility
                        radioButton.click();

                        return {{ 
                            success: true, 
                            method: 'value_or_label_match',
                            xpath: radioXPath,
                            value: radioButton.value,
                            name: radioButton.name || 'unknown'
                        }};
                    }}
                }}

                // Strategy 2: By selector directly - for when selector is more specific
                try {{
                    let radioButton = null;

                    // Direct CSS selector
                    try {{
                        radioButton = document.querySelector('{selector}');
                    }} catch (e) {{
                        // Invalid selector, continue with other methods
                    }}

                    // By ID
                    if (!radioButton) {{
                        radioButton = document.getElementById('{selector}');
                    }}

                    // By name (gets first radio in group)
                    if (!radioButton) {{
                        const radios = document.getElementsByName('{selector}');
                        if (radios.length > 0) {{
                            radioButton = radios[0]; // Select first by default
                        }}
                    }}

                    if (radioButton && radioButton.type === 'radio') {{
                        const radioXPath = getXPath(radioButton);
                        radioButton.checked = true;
                        radioButton.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        // Also trigger click event for additional compatibility
                        radioButton.click();

                        return {{ 
                            success: true, 
                            method: 'direct_selector',
                            xpath: radioXPath,
                            value: radioButton.value,
                            name: radioButton.name || 'unknown'
                        }};
                    }}
                }} catch (e) {{
                    // Move to the next strategy
                }}

                // Strategy 3: By label text
                try {{
                    const labels = Array.from(document.querySelectorAll('label'));
                    for (const label of labels) {{
                        if (label.textContent.trim().toLowerCase().includes('{selector}'.toLowerCase())) {{
                            let radioButton = null;

                            if (label.htmlFor) {{
                                radioButton = document.getElementById(label.htmlFor);
                            }} else {{
                                radioButton = label.querySelector('input[type="radio"]');
                            }}

                            if (radioButton && radioButton.type === 'radio') {{
                                const radioXPath = getXPath(radioButton);
                                radioButton.checked = true;
                                radioButton.dispatchEvent(new Event('change', {{ bubbles: true }}));

                                // Also trigger click event
                                radioButton.click();

                                return {{ 
                                    success: true, 
                                    method: 'label_text',
                                    xpath: radioXPath,
                                    value: radioButton.value,
                                    name: radioButton.name || 'unknown',
                                    labelText: label.textContent.trim()
                                }};
                            }}
                        }}
                    }}
                }} catch (e) {{
                    // Failed to find by label text
                }}

                return {{ 
                    success: false, 
                    message: `Radio button not found with selector: ${{'{selector}'}} and value: ${{'{value}'}}` 
                }};
            }} catch (e) {{
                return {{ 
                    success: false, 
                    message: `Error checking radio button: ${{e.message}}` 
                }};
            }}
        }})();
        """

        self.web_view.page().runJavaScript(js_script, self._handle_check_radio_result)

    def _handle_check_radio_result(self, result):
        """Handle the result of a radio button selection operation"""
        if result.get('success'):
            method = result.get('method')
            if method == 'label_text':
                self.browser.chat_window.add_message(
                    f"✓ Selected radio button with label '{result.get('labelText')}'\n" +
                    f"  Value: {result.get('value')}\n" +
                    f"  Name: {result.get('name')}\n" +
                    f"  XPath: {result.get('xpath')}",
                    Role.WEB_BROWSER
                )
            else:
                self.browser.chat_window.add_message(
                    f"✓ Selected radio button\n" +
                    f"  Value: {result.get('value')}\n" +
                    f"  Name: {result.get('name')}\n" +
                    f"  Found by: {method}\n" +
                    f"  XPath: {result.get('xpath')}",
                    Role.WEB_BROWSER
                )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to select radio button: {result.get('message')}",
                Role.WEB_BROWSER
            )

    def check_checkbox(self, selector, check=True):
        """Check or uncheck a checkbox"""
        js_script = f"""
        (function() {{
            try {{
                // Function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return "/none";
                    if (element.id) return `//*[@id="${{element.id}}"]`;

                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;
                        if (!current || current.tagName === 'BODY' || current === document) break;
                    }}

                    return path || "/unknown";
                }}

                // Try various methods to find the checkbox
                let checkbox = null;
                let method = '';

                // Method 1: Direct CSS selector
                try {{
                    checkbox = document.querySelector('{selector}');
                    if (checkbox && checkbox.type === 'checkbox') {{
                        method = 'css_selector';
                    }}
                }} catch (e) {{
                    // Invalid selector, continue with other methods
                }}

                // Method 2: By ID
                if (!checkbox || checkbox.type !== 'checkbox') {{
                    checkbox = document.getElementById('{selector}');
                    if (checkbox && checkbox.type === 'checkbox') {{
                        method = 'id';
                    }}
                }}

                // Method 3: By name
                if (!checkbox || checkbox.type !== 'checkbox') {{
                    const elements = document.getElementsByName('{selector}');
                    for (const el of elements) {{
                        if (el.type === 'checkbox') {{
                            checkbox = el;
                            method = 'name';
                            break;
                        }}
                    }}
                }}

                // Method 4: By label text
                if (!checkbox || checkbox.type !== 'checkbox') {{
                    const labels = Array.from(document.querySelectorAll('label'));
                    for (const label of labels) {{
                        if (label.textContent.trim().toLowerCase().includes('{selector}'.toLowerCase())) {{
                            if (label.htmlFor) {{
                                const cb = document.getElementById(label.htmlFor);
                                if (cb && cb.type === 'checkbox') {{
                                    checkbox = cb;
                                    method = 'label_text';
                                    break;
                                }}
                            }} else {{
                                const cb = label.querySelector('input[type="checkbox"]');
                                if (cb) {{
                                    checkbox = cb;
                                    method = 'label_contains';
                                    break;
                                }}
                            }}
                        }}
                    }}
                }}

                if (checkbox && checkbox.type === 'checkbox') {{
                    const checkboxXPath = getXPath(checkbox);

                    // Don't change state if already in desired state
                    if (checkbox.checked !== {str(check).lower()}) {{
                        checkbox.checked = {str(check).lower()};
                        checkbox.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        // Also click for compatibility with some frameworks
                        checkbox.click();
                    }}

                    const labelText = (() => {{
                        // Try to find associated label text
                        if (checkbox.id) {{
                            const label = document.querySelector(`label[for="${{checkbox.id}}"]`);
                            if (label) return label.textContent.trim();
                        }}

                        // Look for parent label
                        let parent = checkbox.parentElement;
                        while (parent && parent.tagName !== 'BODY') {{
                            if (parent.tagName === 'LABEL') {{
                                return parent.textContent.trim();
                            }}
                            parent = parent.parentElement;
                        }}

                        return '';
                    }})();

                    return {{ 
                        success: true, 
                        method: method,
                        xpath: checkboxXPath,
                        checked: checkbox.checked,
                        label: labelText,
                        id: checkbox.id || '',
                        name: checkbox.name || ''
                    }};
                }}

                return {{ 
                    success: false, 
                    message: `Checkbox not found with selector: ${{'{selector}'}}` 
                }};
            }} catch (e) {{
                return {{ 
                    success: false, 
                    message: `Error checking checkbox: ${{e.message}}` 
                }};
            }}
        }})();
        """

        self.web_view.page().runJavaScript(js_script, self._handle_check_checkbox_result)

    def _handle_check_checkbox_result(self, result):
        """Handle the result of a checkbox selection operation"""
        if result.get('success'):
            state = "Checked" if result.get('checked') else "Unchecked"
            label_info = f" '{result.get('label')}'" if result.get('label') else ""
            self.browser.chat_window.add_message(
                f"✓ {state} checkbox{label_info}\n" +
                f"  Found by: {result.get('method')}\n" +
                f"  ID: {result.get('id') or 'none'}\n" +
                f"  Name: {result.get('name') or 'none'}\n" +
                f"  XPath: {result.get('xpath')}",
                Role.WEB_BROWSER
            )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to set checkbox: {result.get('message')}",
                Role.WEB_BROWSER
            )

    def click_custom_element(self, selector, attribute=None, value=None):
        """Click a custom element like a star rating, dropdown item, etc."""
        js_script = f"""
        (function() {{
            try {{
                // Function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return "/none";
                    if (element.id) return `//*[@id="${{element.id}}"]`;

                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;
                        if (!current || current.tagName === 'BODY' || current === document) break;
                    }}

                    return path || "/unknown";
                }}

                let element = null;
                let method = '';

                // Try as CSS selector
                try {{
                    // If attribute and value provided, make a more specific selector
                    if ('{attribute}' && '{value}') {{
                        const attrSelector = `${{'{selector}'}}[${{'{attribute}'}}="${{'{value}'}}"]`;
                        element = document.querySelector(attrSelector);
                        if (element) {{
                            method = 'attribute_selector';
                        }}
                    }} else {{
                        element = document.querySelector('{selector}');
                        if (element) {{
                            method = 'css_selector';
                        }}
                    }}
                }} catch (e) {{
                    // Invalid selector, continue with other methods
                }}

                // Try by ID
                if (!element) {{
                    element = document.getElementById('{selector}');
                    if (element) {{
                        method = 'id';
                    }}
                }}

                // For custom elements like star ratings, try to find by aria-label
                if (!element && '{value}') {{
                    element = document.querySelector(`[${{'{attribute}' || 'aria-label'}}="${{'{value}'}}"]`);
                    if (element) {{
                        method = 'aria_attribute';
                    }}
                }}

                // Special handling for common patterns

                // Star ratings (often buttons with star symbols)
                if (!element && '{selector}'.toLowerCase().includes('star')) {{
                    const stars = Array.from(document.querySelectorAll('button, [role="button"]')).filter(el => {{
                        return el.textContent.includes('★') || 
                               el.getAttribute('aria-label')?.toLowerCase().includes('star');
                    }});

                    // If value is a number 1-5, try to find that star
                    if ('{value}' && stars.length > 0) {{
                        const starValue = parseInt('{value}');
                        if (!isNaN(starValue) && starValue > 0 && starValue <= stars.length) {{
                            element = stars[starValue - 1];
                            method = 'star_rating';
                        }}
                    }}
                }}

                // Find by text content if other methods fail
                if (!element && '{value}') {{
                    const allElements = document.querySelectorAll('{selector}' || '*');
                    for (const el of allElements) {{
                        if (el.textContent.trim().toLowerCase() === '{value}'.toLowerCase()) {{
                            element = el;
                            method = 'text_content';
                            break;
                        }}
                    }}
                }}

                if (element) {{
                    const elementXPath = getXPath(element);

                    // Get useful information about the element
                    const tagName = element.tagName.toLowerCase();
                    const text = element.textContent.trim();
                    const role = element.getAttribute('role') || '';

                    // Scroll into view
                    element.scrollIntoView({{ behavior: 'auto', block: 'center' }});

                    // Click the element
                    element.click();

                    return {{ 
                        success: true, 
                        method: method,
                        xpath: elementXPath,
                        tag: tagName,
                        text: text,
                        role: role,
                        selector: '{selector}'
                    }};
                }}

                return {{ 
                    success: false, 
                    message: `Custom element not found with selector: ${{'{selector}'}}${{'{attribute}' ? ` and ${{'{attribute}'}}="${{'{value}'}}"` : ''}}` 
                }};
            }} catch (e) {{
                return {{ 
                    success: false, 
                    message: `Error clicking custom element: ${{e.message}}` 
                }};
            }}
        }})();
        """

        self.web_view.page().runJavaScript(js_script, self._handle_click_custom_element_result)

    def _handle_click_custom_element_result(self, result):
        """Handle the result of a custom element click operation"""
        if result.get('success'):
            self.browser.chat_window.add_message(
                f"✓ Clicked custom element\n" +
                f"  Text: {result.get('text') or 'none'}\n" +
                f"  Tag: {result.get('tag')}\n" +
                f"  Role: {result.get('role') or 'none'}\n" +
                f"  Found by: {result.get('method')}\n" +
                f"  XPath: {result.get('xpath')}",
                Role.WEB_BROWSER
            )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to click custom element: {result.get('message')}",
                Role.WEB_BROWSER
            )

    def click_element(self, selector):
        """Click an element using JavaScript in QWebEngineView"""
        js_script = f"""
        (function() {{
            // Helper function to find elements by text or other attributes
            function findClickableElement(selector) {{
                // Try direct CSS selector first
                try {{
                    const element = document.querySelector(selector);
                    if (element) return {{ element, method: 'css_selector' }};
                }} catch (e) {{
                    // Invalid selector, continue with other methods
                }}

                // Try by visible text content
                const allElements = document.querySelectorAll('a, button, [role="button"], .btn, input[type="button"], input[type="submit"]');
                for (const el of allElements) {{
                    if (el.textContent && el.textContent.toLowerCase().includes(selector.toLowerCase())) {{
                        return {{ element: el, method: 'text_content' }};
                    }}
                }}

                // Try by aria-label, title, etc.
                const labelSelectors = [
                    `[aria-label*="{selector}" i]`,
                    `[title*="{selector}" i]`,
                    `[alt*="{selector}" i]`,
                    `[data-testid*="{selector}" i]`
                ];

                for (const labelSelector of labelSelectors) {{
                    try {{
                        const element = document.querySelector(labelSelector);
                        if (element) return {{ element, method: 'attribute', selector: labelSelector }};
                    }} catch (e) {{
                        // Invalid selector, continue
                    }}
                }}

                return {{ element: null, method: 'none' }};
            }}

            // Function to get XPath of an element
            function getXPath(element) {{
                if (!element) return null;

                // If it has an ID, use that
                if (element.id) {{
                    return `//*[@id="${{element.id}}"]`;
                }}

                // Otherwise build an XPath
                let path = '';
                let current = element;

                while (current && current.nodeType === 1) {{
                    let index = 1;
                    let sibling = current.previousSibling;

                    while (sibling) {{
                        if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                            index++;
                        }}
                        sibling = sibling.previousSibling;
                    }}

                    const tagName = current.tagName.toLowerCase();
                    const pathIndex = (index > 1) ? `[${{index}}]` : '';
                    path = `/${{tagName}}${{pathIndex}}${{path}}`;

                    current = current.parentNode;
                }}

                return path;
            }}

            const result = findClickableElement('{selector}');
            if (result.element) {{
                const xpath = getXPath(result.element);
                result.element.click();
                return {{ 
                    success: true, 
                    selector: '{selector}', 
                    method: result.method,
                    xpath: xpath,
                    tag: result.element.tagName
                }};
            }}

            return {{ success: false, selector: '{selector}', message: 'Element not found' }};
        }})();
        """

        # Execute JavaScript and handle result with a callback
        self.web_view.page().runJavaScript(js_script, self._handle_click_result)

    def _handle_click_result(self, result):
        """Handle the result of a click operation"""
        if result.get('success'):
            self.browser.chat_window.add_message(
                f"✓ Clicked element '{result.get('selector')}' (found by {result.get('method')})\n" +
                f"  XPath: {result.get('xpath')}",
                Role.WEB_BROWSER
            )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to click element '{result.get('selector')}': {result.get('message')}",
                Role.WEB_BROWSER
            )

    def submit_form(self, selector="form"):
        """Submit a form using JavaScript in QWebEngineView"""
        js_script = f"""
        (function() {{
            // Find and submit the form or click a submit button
            try {{
                // Improved function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return "/none";  // Return a clear indicator when element is null

                    // If it has an ID, use that
                    if (element.id) return `//*[@id="${{element.id}}"]`;

                    // Otherwise build an XPath
                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;

                        // Break if we've reached the body or document
                        if (!current || current.tagName === 'BODY' || current === document) break;
                    }}

                    return path || "/unknown";  // Return a fallback if path is empty
                }}

                // PRIORITY CHANGE: First look for submit buttons since we want to click them
                // Look for submit buttons with increasing specificity
                const buttonSelectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    '.form-submit-button',
                    'button.submit',
                    'button.submit-button',
                    'button.primary:not([role="reset"])',
                    'button:contains("Submit")',
                    'button:contains("Send")',
                    'button:contains("Save")'
                ];

                // Try each selector
                for (const buttonSelector of buttonSelectors) {{
                    try {{
                        const buttons = document.querySelectorAll(buttonSelector);
                        if (buttons.length > 0) {{
                            // Click the first visible button
                            for (const btn of buttons) {{
                                const style = window.getComputedStyle(btn);
                                if (style.display !== 'none' && style.visibility !== 'hidden' && btn.offsetParent !== null) {{
                                    const rect = btn.getBoundingClientRect();
                                    if (rect.width > 0 && rect.height > 0) {{
                                        // Important: Get the XPath BEFORE clicking
                                        const buttonXPath = getXPath(btn);
                                        const buttonText = btn.textContent.trim() || btn.value || "Submit Button";

                                        // Now click the button
                                        btn.click();

                                        return {{ 
                                            success: true, 
                                            method: 'submit_button_click', 
                                            buttonText: buttonText,
                                            xpath: buttonXPath,
                                            element: buttonSelector
                                        }};
                                    }}
                                }}
                            }}
                        }}
                    }} catch (e) {{
                        // Skip invalid selectors or errors
                        console.log("Button selector error:", e);
                    }}
                }}

                // Manual search for any button that looks like a submit button
                const allButtons = Array.from(document.querySelectorAll('button, input[type="button"], [role="button"]'));
                const submitKeywords = ['submit', 'send', 'save', 'continue', 'next', 'finish', 'complete', 'done'];

                for (const btn of allButtons) {{
                    const buttonText = (btn.textContent || btn.value || '').toLowerCase();
                    const matchesKeyword = submitKeywords.some(keyword => buttonText.includes(keyword));

                    // Check if any attribute or class suggests it's a submit button
                    const hasSubmitClass = btn.className.toLowerCase().includes('submit') || 
                                          btn.className.toLowerCase().includes('primary');

                    if (matchesKeyword || hasSubmitClass) {{
                        try {{
                            // Important: Get the XPath BEFORE clicking
                            const buttonXPath = getXPath(btn);
                            const displayText = btn.textContent.trim() || btn.value || "Button";
                            const keyword = matchesKeyword ? 
                                submitKeywords.find(k => buttonText.includes(k)) : 'class-based';

                            // Now click the button
                            btn.click();

                            return {{ 
                                success: true, 
                                method: 'keyword_button_click', 
                                buttonText: displayText,
                                keyword: keyword,
                                xpath: buttonXPath
                            }};
                        }} catch (e) {{
                            console.log("Button click error:", e);
                        }}
                    }}
                }}

                // Try with the custom selector if provided
                if ('{selector}' !== 'form') {{
                    const customElement = document.querySelector('{selector}');
                    if (customElement) {{
                        // Is it a form?
                        if (customElement.tagName === 'FORM') {{
                            customElement.submit();
                            return {{ 
                                success: true, 
                                method: 'custom_form_submit', 
                                formId: customElement.id || 'unnamed',
                                xpath: getXPath(customElement)
                            }};
                        }}

                        // Is it a button or clickable element?
                        else if (customElement.tagName === 'BUTTON' || 
                                 customElement.tagName === 'INPUT' ||
                                 customElement.getAttribute('role') === 'button') {{

                            // Get XPath before clicking
                            const elementXPath = getXPath(customElement);
                            const elementText = customElement.textContent.trim() || customElement.value || "Custom Element";

                            // Click the element
                            customElement.click();

                            return {{ 
                                success: true, 
                                method: 'custom_element_click', 
                                elementText: elementText,
                                xpath: elementXPath,
                                selector: '{selector}'
                            }};
                        }}
                    }}
                }}

                // Try to submit any form as a last resort
                const form = document.querySelector('form');
                if (form) {{
                    try {{
                        const formXPath = getXPath(form);
                        form.submit();
                        return {{ 
                            success: true, 
                            method: 'form_submit', 
                            formId: form.id || 'unnamed',
                            xpath: formXPath
                        }};
                    }} catch (e) {{
                        // Form submission error
                        console.log("Form submit error:", e);
                    }}
                }}

                // If we got here, we didn't find any submit button or form
                return {{ success: false, message: 'No submit button or form found' }};
            }} catch (e) {{
                return {{ success: false, message: `Error during form submission: ${{e.message}}` }};
            }}
        }})();
        """

        # Execute JavaScript and handle result with a callback
        self.web_view.page().runJavaScript(js_script, self._handle_submit_result)

    def _handle_submit_result(self, result):
        """Handle the result of a form submission"""
        if result.get('success'):
            method = result.get('method', '')

            if method == 'submit_button_click':
                self.browser.chat_window.add_message(
                    f"✓ Clicked submit button '{result.get('buttonText')}'\n" +
                    f"  XPath: {result.get('xpath')}\n" +
                    f"  Selector: {result.get('element')}",
                    Role.WEB_BROWSER
                )
            elif method == 'keyword_button_click':
                self.browser.chat_window.add_message(
                    f"✓ Clicked button with text '{result.get('buttonText')}'\n" +
                    f"  XPath: {result.get('xpath')}\n" +
                    f"  Keyword match: {result.get('keyword')}",
                    Role.WEB_BROWSER
                )
            elif method == 'custom_element_click':
                self.browser.chat_window.add_message(
                    f"✓ Clicked custom element '{result.get('elementText')}'\n" +
                    f"  XPath: {result.get('xpath')}\n" +
                    f"  Selector: {result.get('selector')}",
                    Role.WEB_BROWSER
                )
            elif method == 'form_submit':
                self.browser.chat_window.add_message(
                    f"✓ Form submitted programmatically\n" +
                    f"  Form ID: {result.get('formId')}\n" +
                    f"  XPath: {result.get('xpath')}",
                    Role.WEB_BROWSER
                )
            elif method == 'custom_form_submit':
                self.browser.chat_window.add_message(
                    f"✓ Custom form submitted programmatically\n" +
                    f"  Form ID: {result.get('formId')}\n" +
                    f"  XPath: {result.get('xpath')}",
                    Role.WEB_BROWSER
                )
            else:
                self.browser.chat_window.add_message(
                    f"✓ Form submitted via {method}\n" +
                    f"  XPath: {result.get('xpath', 'Unknown')}",
                    Role.WEB_BROWSER
                )
        else:
            self.browser.chat_window.add_message(
                f"✗ Failed to submit form: {result.get('message')}",
                Role.WEB_BROWSER
            )

    def debug_element(self, selector):
        """Debug element properties using JavaScript in QWebEngineView"""
        js_script = f"""
        (function() {{
            try {{
                // Function to get XPath of an element
                function getXPath(element) {{
                    if (!element) return null;

                    // If it has an ID, use that
                    if (element.id) {{
                        return `//*[@id="${{element.id}}"]`;
                    }}

                    // Otherwise build an XPath
                    let path = '';
                    let current = element;

                    while (current && current.nodeType === 1) {{
                        let index = 1;
                        let sibling = current.previousSibling;

                        while (sibling) {{
                            if (sibling.nodeType === 1 && sibling.tagName === current.tagName) {{
                                index++;
                            }}
                            sibling = sibling.previousSibling;
                        }}

                        const tagName = current.tagName.toLowerCase();
                        const pathIndex = (index > 1) ? `[${{index}}]` : '';
                        path = `/${{tagName}}${{pathIndex}}${{path}}`;

                        current = current.parentNode;
                    }}

                    return path;
                }}

                const element = document.querySelector('{selector}');
                if (!element) {{
                    return {{ found: false, message: 'Element not found' }};
                }}

                // Get all attributes
                const attributes = {{}};
                for (const attr of element.attributes) {{
                    attributes[attr.name] = attr.value;
                }}

                // Get computed styles
                const styles = {{}};
                const computed = window.getComputedStyle(element);
                ['display', 'visibility', 'position', 'z-index', 'pointer-events'].forEach(
                    prop => styles[prop] = computed[prop]
                );

                return {{
                    found: true,
                    tagName: element.tagName,
                    id: element.id,
                    className: element.className,
                    type: element.type,
                    value: element.value,
                    checked: element.checked,
                    disabled: element.disabled,
                    readOnly: element.readOnly,
                    attributes: attributes,
                    styles: styles,
                    rect: {{
                        top: element.getBoundingClientRect().top,
                        right: element.getBoundingClientRect().right,
                        bottom: element.getBoundingClientRect().bottom,
                        left: element.getBoundingClientRect().left,
                        width: element.getBoundingClientRect().width,
                        height: element.getBoundingClientRect().height
                    }},
                    isVisible: element.offsetWidth > 0 && element.offsetHeight > 0,
                    html: element.outerHTML.substring(0, 500), // Limit HTML to 500 chars
                    xpath: getXPath(element)
                }};
            }} catch (e) {{
                return {{ found: false, message: 'Error: ' + e.message }};
            }}
        }})();
        """

        # Execute JavaScript and handle result with a callback
        self.web_view.page().runJavaScript(js_script, self._handle_debug_result)

    def _handle_debug_result(self, element_info):
        """Handle the result of a debug operation"""
        if element_info.get('found', False):
            result = "Element Debug Info:\n"
            result += f"TagName: {element_info.get('tagName')}\n"
            result += f"ID: {element_info.get('id')}\n"
            result += f"Class: {element_info.get('className')}\n"
            result += f"Type: {element_info.get('type')}\n"
            result += f"Value: {element_info.get('value')}\n"
            result += f"Disabled: {element_info.get('disabled')}\n"
            result += f"ReadOnly: {element_info.get('readOnly')}\n"
            result += f"Visible: {element_info.get('isVisible')}\n"
            result += f"XPath: {element_info.get('xpath')}\n"

            # Attributes
            result += "\nAttributes:\n"
            for name, value in element_info.get('attributes', {}).items():
                result += f"  {name}: {value}\n"

            # Styles
            result += "\nStyles:\n"
            for name, value in element_info.get('styles', {}).items():
                result += f"  {name}: {value}\n"

            # HTML preview
            result += f"\nHTML Preview:\n{element_info.get('html', '')}"

            self.browser.chat_window.add_message(result, Role.WEB_BROWSER)
        else:
            self.browser.chat_window.add_message(
                f"Could not find element: {element_info.get('message')}",
                Role.WEB_BROWSER
            )


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sage Browser")
        self.setup_ui()
        self.setup_browser_commands()

        # Initialize WebView automator instead of PlaywrightController
        self.web_automator = WebViewAutomator(self)

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
        self.web_view.setUrl(QUrl("https://docs.google.com/forms/d/e/1FAIpQLSfytBk_bpiAWDSiYkPbf7KS0rJAj2kbETbfSh0xVkJroMpoOw/viewform"))
        self.web_view.urlChanged.connect(self.update_url)

        browser_layout.addLayout(nav_layout)
        browser_layout.addWidget(self.web_view)

        # Chat section
        self.chat_window = ChatWindow()
        self.chat_window.message_sent.connect(self.handle_chat_message)
        self.chat_window.browser_command.connect(self.handle_browser_command)

        # Add widgets to splitter
        splitter.addWidget(browser_widget)
        splitter.addWidget(self.chat_window)

        # Set initial sizes (70% browser, 30% chat)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

        # Set window size
        self.resize(1200, 800)

    def setup_browser_commands(self):
        """Set up additional browser command functionality"""
        pass

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

    def handle_browser_command(self, command, params):
        """Handle browser commands from the chat window"""
        if command == "goto":
            qurl = QUrl(params["url"])
            if not qurl.scheme():
                qurl.setScheme("http")
            self.web_view.setUrl(qurl)

        elif command == "back":
            self.web_view.back()

        elif command == "forward":
            self.web_view.forward()

        elif command == "reload":
            self.web_view.reload()

        elif command == "fillform":
            # Use WebViewAutomator for form filling
            self.web_automator.fill_form(params["data"])

        elif command == "click":
            # Use WebViewAutomator for clicking
            self.web_automator.click_element(params["selector"])

        elif command == "type":
            # Use WebViewAutomator for typing (single field)
            field_data = {params["selector"]: params["text"]}
            self.web_automator.fill_form(field_data)

        elif command == "submit":
            # Use WebViewAutomator for form submission
            self.web_automator.submit_form(params.get("selector", "form"))

        elif command == "debug":
            # Debug element properties
            self.web_automator.debug_element(params["selector"])

    def closeEvent(self, event):
        """Clean up resources when the browser is closed"""
        super().closeEvent(event)